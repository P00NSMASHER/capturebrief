"""Offline integrity verification of an existing CaptureBrief delivery archive.

Requires a separately retained SHA-256; a hash found inside the ZIP cannot act
as its own trust anchor. This reads bounded bytes, never extracts or executes
contents, and grants no authority to release, send, or make a bid decision.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_BUNDLE_BYTES = 32 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
PAYLOAD_FILES = frozenset({
    "brief.md", "decision-evidence.md", "decision-evidence.html",
    "decision-summary.json", "source-version-manifest.json", "watch-baseline.json",
})
ARCHIVE_FILES = PAYLOAD_FILES | {"delivery-manifest.json"}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _time(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.utcoffset() is not None else None
    except (ValueError, AttributeError, TypeError):
        return None


def _object(raw: bytes) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result
    def reject_constant(_value):
        raise ValueError("non-finite JSON constant")
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                        parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def _read_regular_file(path: str | Path) -> bytes:
    # Nonblocking open prevents a supplied FIFO from hanging verification.
    # O_NOFOLLOW rejects symlinks on platforms that provide it.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("regular file required")
        if info.st_size > MAX_BUNDLE_BYTES:
            raise ValueError("archive exceeds input limit")
        raw = stream.read(MAX_BUNDLE_BYTES + 1)
        if len(raw) > MAX_BUNDLE_BYTES:
            raise ValueError("archive exceeds input limit")
        return raw


def verify_delivery_bundle(
    bundle_path: str | Path, *, expected_sha256: str,
    expected_case_id: str | None = None,
    expected_case_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify bytes and packaging contracts, not evidence truth or currentness.

    A fresh empty error list is necessary for success. Malformed inputs produce
    a non-success report instead of trusting an embedded READY label. Input and
    output files are never changed. Source text/HTML is never executed.
    """
    errors: list[str] = []
    result: dict[str, Any] = {
        "schema_version": "1.0", "verification_state": "FAILED",
        "integrity_verified": False, "expected_sha256": expected_sha256,
        "bundle_sha256": None, "bundle_bytes": None, "verified_file_count": 0,
        "errors": errors, "external_send_authorized": False,
        "source_currentness_rechecked": False, "content_review_performed": False,
        "reference_origin_authenticated": False,
        "verification_scope": "READ_BYTES_MATCH_CALLER_SUPPLIED_DIGEST_AND_PACKAGE_CONTRACT",
    }
    if not _sha(expected_sha256):
        errors.append("EXPECTED_BUNDLE_SHA256_INVALID")
        return result
    if expected_case_sha256 is not None and not _sha(expected_case_sha256):
        errors.append("EXPECTED_CASE_SHA256_INVALID")
        return result
    if expected_case_id is not None and (not isinstance(expected_case_id, str) or not expected_case_id.strip()):
        errors.append("EXPECTED_CASE_ID_INVALID")
        return result
    try:
        raw = _read_regular_file(bundle_path)
    except (OSError, ValueError, TypeError):
        errors.append("BUNDLE_UNREADABLE_OR_OVER_LIMIT")
        return result
    result.update(bundle_sha256=_digest(raw), bundle_bytes=len(raw))
    if result["bundle_sha256"] != expected_sha256:
        errors.append("BUNDLE_SHA256_MISMATCH")
        return result

    payload: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [entry.filename for entry in infos]
            if len(names) != len(set(names)):
                errors.append("DUPLICATE_ARCHIVE_MEMBER")
            if len(names) != len(ARCHIVE_FILES) or set(names) != ARCHIVE_FILES:
                errors.append("ARCHIVE_FILE_SET_MISMATCH")
            if errors:
                return result
            if sum(entry.file_size for entry in infos) > MAX_EXPANDED_BYTES:
                errors.append("EXPANDED_ARCHIVE_OVER_LIMIT")
                return result
            for entry in infos:
                mode = entry.external_attr >> 16
                if (entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                        or entry.flag_bits & 1
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    errors.append("UNSUPPORTED_ARCHIVE_MEMBER")
                    return result
                if entry.file_size < 0 or entry.file_size > MAX_MEMBER_BYTES:
                    errors.append("ARCHIVE_MEMBER_OVER_LIMIT")
                    return result
                with archive.open(entry) as stream:
                    data = stream.read(MAX_MEMBER_BYTES + 1)
                if len(data) != entry.file_size or len(data) > MAX_MEMBER_BYTES:
                    errors.append("ARCHIVE_MEMBER_SIZE_MISMATCH")
                    return result
                payload[entry.filename] = data
    except (OSError, ValueError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile, zlib.error):
        errors.append("ARCHIVE_READ_FAILED")
        return result

    try:
        docs = {name: _object(data) for name, data in payload.items() if name.endswith(".json")}
        manifest = docs["delivery-manifest.json"]
        summary = docs["decision-summary.json"]
        sources = docs["source-version-manifest.json"]
        baseline = docs["watch-baseline.json"]
        rows = manifest.get("files")
        if not isinstance(rows, list) or len(rows) != len(PAYLOAD_FILES):
            raise ValueError("invalid payload manifest")
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
                raise ValueError("invalid manifest row")
            name = row["path"]
            if not isinstance(name, str) or name not in PAYLOAD_FILES or name in indexed:
                raise ValueError("invalid manifest path")
            indexed[name] = row
            if not _sha(row["sha256"]) or type(row["bytes"]) is not int or row["bytes"] < 0:
                raise ValueError("invalid manifest fingerprint")
            if row["sha256"] != _digest(payload[name]) or row["bytes"] != len(payload[name]):
                errors.append("PAYLOAD_FINGERPRINT_MISMATCH")
        if set(indexed) != PAYLOAD_FILES:
            raise ValueError("incomplete payload manifest")
        for doc in docs.values():
            if doc.get("schema_version") != "1.0":
                errors.append("PACKAGE_SCHEMA_UNSUPPORTED")
            for field in ("case_id", "family_id"):
                value = manifest.get(field)
                if not isinstance(value, str) or not value.strip() or doc.get(field) != value:
                    errors.append("PACKAGE_IDENTITY_MISMATCH")
        case_sha = manifest.get("case_sha256")
        if not _sha(case_sha) or any(doc.get("case_sha256") != case_sha for doc in (summary, baseline)):
            errors.append("PACKAGE_CASE_HASH_MISMATCH")
        if expected_case_id is not None and manifest.get("case_id") != expected_case_id:
            errors.append("EXPECTED_CASE_ID_MISMATCH")
        if expected_case_sha256 is not None and case_sha != expected_case_sha256:
            errors.append("EXPECTED_CASE_SHA256_MISMATCH")
        for doc in (manifest, summary):
            if (doc.get("release_state") != "READY_FOR_HUMAN_RELEASE"
                    or doc.get("trace_state") != "TRACE_COMPLETE"):
                errors.append("PACKAGE_RELEASE_LABEL_INVALID")
            if doc.get("external_send_authorized") is not False:
                errors.append("PACKAGE_SEND_BOUNDARY_INVALID")
        timestamp = _time(manifest.get("generated_at"))
        if timestamp is None or _time(summary.get("evaluated_at")) != timestamp or _time(baseline.get("created_at")) != timestamp:
            errors.append("PACKAGE_EVALUATION_TIME_MISMATCH")
        if manifest.get("contains_raw_case") is not False or manifest.get("contains_restricted_source_bytes") is not False:
            errors.append("PACKAGE_PRIVACY_DECLARATION_INVALID")
        if (baseline.get("contains_raw_case") is not False
                or baseline.get("contains_source_text") is not False
                or baseline.get("automatic_decision_change") is not False):
            errors.append("BASELINE_BOUNDARY_INVALID")
        body = {key: value for key, value in baseline.items() if key != "baseline_sha256"}
        if baseline.get("baseline_sha256") != _digest(_canonical(body)):
            errors.append("BASELINE_SHA256_MISMATCH")
        if not isinstance(sources.get("snapshots"), list) or not isinstance(sources.get("rule_versions"), list):
            errors.append("SOURCE_MANIFEST_INVALID")
        result.update(case_id=manifest.get("case_id"), family_id=manifest.get("family_id"), case_sha256=case_sha)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        errors.append("PACKAGE_MANIFEST_INVALID")

    result["errors"] = sorted(set(errors))
    if not result["errors"]:
        result.update(verification_state="VERIFIED_INTEGRITY", integrity_verified=True,
                      verified_file_count=len(PAYLOAD_FILES))
    return result
