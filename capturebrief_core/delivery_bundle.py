"""Build a buyer-safe, hash-manifested CaptureBrief delivery bundle."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .decision_trace import canonical, digest
from .delivery_readiness import evaluate_delivery_readiness
from .render import render_markdown
from .trace_render import render_trace_html, render_trace_markdown
from .watch_baseline import build_watch_baseline

BUNDLE_SCHEMA = "1.0"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _aware(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _public_source_manifest(case: dict[str, Any]) -> dict[str, Any]:
    trace = case.get("decision_trace") or {}
    snapshots = []
    for row in trace.get("snapshots") or []:
        if not isinstance(row, dict):
            continue
        snapshots.append({
            key: row.get(key)
            for key in (
                "snapshot_id", "source_id", "source_key", "kind", "title", "url",
                "version_label", "document_sha256", "text_sha256", "observed_at",
                "published_at", "capture_method",
            )
        })
    rules = []
    for row in trace.get("rule_versions") or []:
        if not isinstance(row, dict):
            continue
        rules.append({
            key: row.get(key)
            for key in (
                "rule_version_id", "rule_key", "namespace", "citation", "edition",
                "agency", "effective_from", "effective_until", "revision_ref",
            )
        })
    snapshots.sort(key=lambda x: (str(x.get("source_key") or ""), str(x.get("version_label") or ""), str(x.get("snapshot_id") or "")))
    rules.sort(key=lambda x: (str(x.get("rule_key") or ""), str(x.get("edition") or ""), str(x.get("rule_version_id") or "")))
    return {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "snapshots": snapshots,
        "rule_versions": rules,
    }


def build_delivery_files(case: dict[str, Any], *, now: datetime | None = None) -> dict[str, bytes]:
    """Return buyer-safe files from one case snapshot and one evaluation time."""
    case = copy.deepcopy(case)
    readiness = evaluate_delivery_readiness(case, now=now)
    if not readiness.eligible:
        raise ValueError("case is not delivery-ready: " + ",".join(readiness.blocker_codes))
    now = readiness.checked_at
    audit = readiness.audit
    trace = readiness.trace

    brief = render_markdown(case, audit, now=now)
    trace_md = render_trace_markdown(case, now=now)
    trace_html = render_trace_html(case, now=now)
    source_manifest = _public_source_manifest(case)
    summary = {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "current_posture": case.get("current_posture"),
        "release_state": audit.release_state,
        "currentness_verdict": audit.currentness_verdict,
        "current_action_id": audit.current_action_id,
        "trace_state": trace.get("trace_state"),
        "decision_at": trace.get("decision_at"),
        "evaluated_at": now.isoformat().replace("+00:00", "Z"),
        "case_sha256": trace.get("case_sha256"),
        "assumptions": trace.get("assumptions") or [],
        "limitations": trace.get("limitations") or [],
        "external_send_authorized": False,
    }
    return {
        "brief.md": brief.encode("utf-8"),
        "decision-evidence.md": trace_md.encode("utf-8"),
        "decision-evidence.html": trace_html.encode("utf-8"),
        "decision-summary.json": _json_bytes(summary),
        "source-version-manifest.json": _json_bytes(source_manifest),
        "watch-baseline.json": _json_bytes(build_watch_baseline(case, now=now)),
    }


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, files[name])
    # Ensure the completed archive reaches the filesystem before publication.
    # Windows requires a writable handle for FlushFileBuffers (os.fsync).
    # The archive is complete; r+b changes only the handle mode.
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _publish_completed_zip(temp_path: Path, target: Path, *, overwrite: bool) -> None:
    """Publish a completed archive without exposing a partially written target.

    overwrite=False uses a hard-link publication step because link creation is
    atomic and fails if another writer created the destination first.
    overwrite=True is an explicit replacement request and uses os.replace,
    which is atomic on the same filesystem.
    """
    if overwrite:
        os.replace(temp_path, target)
        return
    try:
        os.link(temp_path, target)
    except FileExistsError:
        raise FileExistsError(f"refusing to overwrite existing bundle: {target}") from None
    else:
        temp_path.unlink()


def build_delivery_bundle(
    case: dict[str, Any],
    output_zip: str | Path,
    *,
    now: datetime | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a deterministic ZIP and return the receipt for the bytes built.

    The complete ZIP is staged in the destination directory. Its digest is
    calculated before atomic publication, so a later replacement of the output
    path cannot substitute another writer's bytes into this build's receipt.
    A receipt is not proof that the path has never changed since publication.
    """
    case = copy.deepcopy(case)
    now = _aware(now if now is not None else datetime.now(timezone.utc))
    target = Path(output_zip)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing bundle: {target}")

    files = build_delivery_files(case, now=now)
    file_rows = [
        {"path": name, "sha256": digest(data), "bytes": len(data)}
        for name, data in sorted(files.items())
    ]
    manifest = {
        "schema_version": BUNDLE_SCHEMA,
        "case_id": case.get("case_id"),
        "family_id": case.get("family_id"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "case_sha256": digest(canonical(case)),
        "release_state": "READY_FOR_HUMAN_RELEASE",
        "trace_state": "TRACE_COMPLETE",
        "files": file_rows,
        "contains_raw_case": False,
        "contains_restricted_source_bytes": False,
        "external_send_authorized": False,
    }
    files["delivery-manifest.json"] = _json_bytes(manifest)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        _write_zip(temp_path, files)
        built_bytes = temp_path.read_bytes()
        bundle_sha256 = digest(built_bytes)
        bundle_bytes = len(built_bytes)
        _publish_completed_zip(temp_path, target, overwrite=overwrite)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    result = dict(manifest)
    result["bundle_path"] = str(target)
    result["bundle_sha256"] = bundle_sha256
    result["bundle_bytes"] = bundle_bytes
    result["receipt_scope"] = "BUILT_ARTIFACT_NOT_CURRENT_PATH_STATE"
    return result
