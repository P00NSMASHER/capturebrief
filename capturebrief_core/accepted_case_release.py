"""Offline, fail-closed release verification for one REAL accepted CaptureBrief case.

This module never fetches SAM.gov, sends a message, approves private storage,
creates an approver identity, or handles a signing/recovery key. The owner
provisions a private trusted Ed25519 signer roster independently. A signed
statement of human/off-device activity is evidence of the named custodian's
attestation, not a substitute for the real activity.

This release check is deliberately stricter than a technical report build.
A demo ZIP, a GSA latest-active observation, or a cryptographic hash alone
cannot satisfy an accepted customer's source/recovery/release obligations.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from .delivery_readiness import evaluate_delivery_readiness

SCHEMA = "capturebrief-accepted-case-release-v1"
TRUST_SCHEMA = "capturebrief-private-release-signers-v1"
RECOVERY_SCHEMA = "capturebrief-independent-restoration-v1"
ROLES = (
    "SOURCE_REVIEWER", "STORAGE_OWNER", "RECOVERY_CUSTODIAN",
    "BUSINESS_VERIFIER", "REPORT_REVIEWER", "DELIVERY_APPROVER",
)
REQUIRED_KINDS = {
    "CASE", "HISTORY", "RESOURCE_INVENTORY", "BUSINESS_EVIDENCE",
    "INBOUND_RECEIPT", "SCOPE_AGREEMENT", "REPORT",
    "REPORT_RECEIPT", "REGISTRY_SNAPSHOT", "AUTHORIZATION_LEDGER_SNAPSHOT",
    "OFFDEVICE_BACKUP",
    "RECOVERY_RECEIPT", "MESSAGE_BODY",
}
SINGLETON_KINDS = REQUIRED_KINDS
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX32 = re.compile(r"^[0-9a-f]{32,64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$")
MAX_JSON = 512 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


class AcceptedCaseBlocked(ValueError):
    """An accepted-case claim cannot be independently authorized for delivery."""


def _reject_private_path_links(path: Path) -> None:
    """Reject symlink/junction components, including otherwise invisible parents.

    In particular, checking only the final file or root path misses
    /private/alias/case.json where alias is a symlink to a public checkout.
    """
    for segment in (path, *path.parents):
        junction = getattr(segment, "is_junction", None)
        if segment.is_symlink() or (callable(junction) and junction()):
            raise AcceptedCaseBlocked("Private evidence path must not traverse a link or junction")
        if os.name == "nt":
            # Path.is_junction is only available starting in Python 3.12.
            # Our Windows release runners use Python 3.11, where lstat()
            # exposes name-surrogate junctions via the reparse-point bit.
            # Reject ALL reparse points, not only the familiar junction tag.
            try:
                attributes = getattr(os.lstat(segment), "st_file_attributes", 0)
            except FileNotFoundError:
                continue  # Missing files still fail the later existence checks.
            except OSError:
                raise AcceptedCaseBlocked("Private evidence path is not safely inspectable") from None
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise AcceptedCaseBlocked("Private evidence path traverses a Windows reparse point")


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256(obj: bytes) -> str:
    return hashlib.sha256(obj).hexdigest()


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 48:
        raise AcceptedCaseBlocked("Missing bounded timezone-aware evidence time")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AcceptedCaseBlocked("Evidence time is not valid ISO-8601") from None
    if at.utcoffset() is None:
        raise AcceptedCaseBlocked("Evidence time has no timezone")
    return at.astimezone(timezone.utc)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AcceptedCaseBlocked("Duplicate JSON key in private evidence")
        result[key] = value
    return result


def _json_file(path: Path) -> dict[str, Any]:
    _reject_private_path_links(path.expanduser().absolute())
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_JSON:
        raise AcceptedCaseBlocked("Private manifest or key roster unavailable or oversized")
    try:
        result = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=_unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise AcceptedCaseBlocked("Private JSON evidence is malformed") from None
    if not isinstance(result, dict):
        raise AcceptedCaseBlocked("Private JSON evidence must be an object")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise AcceptedCaseBlocked("Private case, approval or trust roster must be owner-only")
    return result


def _root(path: str | Path) -> Path:
    root = Path(path).expanduser().absolute()
    _reject_private_path_links(root)
    if not root.is_dir():
        raise AcceptedCaseBlocked("Approved private root must be a real existing directory")
    if os.name != "nt" and (root.stat().st_mode & 0o077):
        raise AcceptedCaseBlocked("Private root must be owner-only on POSIX")
    resolved = root.resolve(strict=True)
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise AcceptedCaseBlocked("Private customer data must not be stored in a Git checkout")
    return resolved


def _file(root: Path, relative: str, expected: str, *, limit: int = MAX_FILE) -> bytes:
    if not isinstance(relative, str) or not relative or len(relative) > 240:
        raise AcceptedCaseBlocked("Private file has no bounded relative path")
    normalized = PurePosixPath(relative)
    if (normalized.is_absolute() or relative != normalized.as_posix()
            or any(c in ("..", ".", "") for c in relative.split("/"))
            or ":" in relative or "\\" in relative):
        raise AcceptedCaseBlocked("Private evidence path escapes the approved root")
    path = root.joinpath(*normalized.parts)
    if not path.is_relative_to(root) or any(p.is_symlink() for p in (path, *path.parents)
                                            if p.is_relative_to(root)):
        raise AcceptedCaseBlocked("Private evidence path follows a link")
    if not path.is_file():
        raise AcceptedCaseBlocked("Private evidence original is missing")
    before = path.stat()
    if not 0 < before.st_size <= limit or not stat.S_ISREG(before.st_mode):
        raise AcceptedCaseBlocked("Private evidence file is empty or oversized")
    if os.name != "nt" and (before.st_mode & 0o077):
        raise AcceptedCaseBlocked("Private evidence file is not owner-only")
    h = hashlib.sha256()
    chunks: list[bytes] = []
    with path.open("rb") as stream:
        while True:
            piece = stream.read(1024 * 1024)
            if not piece:
                break
            chunks.append(piece)
            h.update(piece)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise AcceptedCaseBlocked("Private original changed during verification")
    if not isinstance(expected, str) or not HEX64.fullmatch(expected) or h.hexdigest() != expected:
        raise AcceptedCaseBlocked("Private original fingerprint differs from evidence receipt")
    return b"".join(chunks)


def _official(url: Any, *, sam_only: bool = False) -> bool:
    if not isinstance(url, str) or len(url) > 1000:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        return False
    return (parsed.scheme == "https" and bool(host)
            and not parsed.username and not parsed.password and not parsed.fragment
            and not port and not re.search(r"(api.?key|token|signature|credential)=", parsed.query, re.I)
            and ((host == "sam.gov" or host.endswith(".sam.gov")) if sam_only
                 else (host.endswith(".gov") or host == "acquisition.gov")))


def _sam_record_reference(row: dict[str, Any], *, action_id: str,
                          resource_id: str | None = None) -> None:
    """Bind recognizable first-party notice/resource URLs to their exact IDs.

    Archived SAM Data Services extracts use a collection URL, so those require
    an independently reviewed explicit record_locator. A URL and a digest do
    not themselves prove provider authenticity or complete family history.
    """
    source_url = row.get("source_url")
    if not _official(source_url, sam_only=True):
        raise AcceptedCaseBlocked("Official SAM original source URL is missing")
    parsed = urlsplit(source_url)
    if (parsed.hostname or "").casefold().rstrip(".") != "sam.gov":
        raise AcceptedCaseBlocked("History/resource original needs first-party SAM.gov provenance")
    path = parsed.path.rstrip("/")
    notice = re.fullmatch(r"/(?:workspace/contract/)?opp/([^/]+)/view", path, re.I)
    if notice:
        if notice.group(1).casefold() != action_id.casefold():
            raise AcceptedCaseBlocked("SAM original points to a different historical action")
        return
    resource = re.fullmatch(
        r"/api/prod/opps/v3/opportunities/resources/files/([^/]+)/download",
        path, re.I,
    )
    if resource and resource_id:
        if resource.group(1).casefold() != resource_id.casefold():
            raise AcceptedCaseBlocked("SAM download URL identifies another resource")
        return
    if path.casefold().startswith("/data-services/contract%20opportunities/"):
        expected = resource_id if resource_id is not None else action_id
        if row.get("record_locator") == expected:
            return
        raise AcceptedCaseBlocked("Data Services original lacks an exact reviewed record locator")
    raise AcceptedCaseBlocked("Unrecognized or unrelated SAM original evidence location")


def _files(manifest: dict[str, Any], root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    rows = manifest.get("files")
    if not isinstance(rows, list) or not 12 <= len(rows) <= 100:
        raise AcceptedCaseBlocked("Complete bounded private case inventory is required")
    indexed: dict[str, dict[str, Any]] = {}
    loaded: dict[str, bytes] = {}
    seen_paths: set[str] = set()
    kinds: dict[str, int] = {}
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise AcceptedCaseBlocked("Invalid private source file inventory")
        fid, kind, rel, digest = (row.get(k) for k in ("id", "kind", "path", "sha256"))
        if (not isinstance(fid, str) or not SAFE_ID.fullmatch(fid) or fid in indexed
                or not isinstance(kind, str) or kind not in REQUIRED_KINDS | {
                    "ACTION_ORIGINAL", "RESOURCE_ORIGINAL", "INCORPORATED_RULE"}
                or rel in seen_paths):
            raise AcceptedCaseBlocked("Duplicate, unknown or ambiguous private source original")
        data = _file(root, rel, digest)
        total += len(data)
        if total > MAX_TOTAL:
            raise AcceptedCaseBlocked("Case evidence exceeds bounded offline review allowance")
        indexed[fid] = row
        loaded[fid] = data
        seen_paths.add(rel)
        kinds[kind] = kinds.get(kind, 0) + 1
    if any(kinds.get(k) != 1 for k in SINGLETON_KINDS):
        raise AcceptedCaseBlocked("Required customer, source, registry, report or recovery original missing")
    if kinds.get("ACTION_ORIGINAL", 0) == 0:
        raise AcceptedCaseBlocked("Latest-active API cannot substitute for retained historical originals")
    return indexed, loaded


def _kind(files: dict[str, dict[str, Any]], fid: Any, expected: str) -> None:
    if not isinstance(fid, str) or fid not in files or files[fid]["kind"] != expected:
        raise AcceptedCaseBlocked("Source review references the wrong retained original kind")


def _source_closure(case: dict[str, Any], manifest: dict[str, Any],
                    files: dict[str, dict[str, Any]], now: datetime) -> None:
    closure = manifest.get("source_closure")
    if not isinstance(closure, dict):
        raise AcceptedCaseBlocked("Independent family history and incorporated-source review missing")
    if (closure.get("scope") != "HUMAN_REVIEWED_COMPLETE_ACTION_SET"
            or closure.get("collection_mode") != "PERMITTED_FIRST_PARTY_SAM_OR_DATA_SERVICES"
            or closure.get("includes_cancellations_deletions") is not True
            or closure.get("missing_or_unavailable") != []):
        raise AcceptedCaseBlocked("History is incomplete or falsely based on current API alone")
    _kind(files, closure.get("history_file"), "HISTORY")
    _kind(files, closure.get("resource_inventory_file"), "RESOURCE_INVENTORY")
    if not _official(files[closure["history_file"]].get("source_url"), sam_only=True):
        raise AcceptedCaseBlocked("Family history original must be retained from official SAM.gov")
    if not _official(files[closure["resource_inventory_file"]].get("source_url"), sam_only=True):
        raise AcceptedCaseBlocked("Resource/tombstone inventory must be a reviewed official SAM.gov snapshot")
    # The GSA Opportunities v2 API supplies only latest active. A signed
    # history/attachment inventory from that API host cannot certify versions.
    for fid in (closure["history_file"], closure["resource_inventory_file"]):
        if urlsplit(files[fid]["source_url"]).hostname.casefold().rstrip(".") != "sam.gov":
            raise AcceptedCaseBlocked("Latest-active API host is not authoritative history")
    actions = closure.get("actions")
    expected = case.get("packet", {}).get("history_action_ids")
    if (not isinstance(actions, list) or not actions or len(actions) > 60
            or not isinstance(expected, list) or not expected):
        raise AcceptedCaseBlocked("Missing complete original-to-current family action set")
    seen: set[str] = set()
    used_action_originals: set[str] = set()
    published_actions: list[tuple[str, datetime]] = []
    for action in actions:
        if not isinstance(action, dict) or action.get("type") not in {
            "SOLICITATION", "AMENDMENT", "MODIFICATION", "CANCELLATION", "REINSTATEMENT", "OTHER"
        }:
            raise AcceptedCaseBlocked("Historical action type is missing or unsupported")
        notice = action.get("notice_id")
        if not isinstance(notice, str) or not SAFE_ID.fullmatch(notice) or notice in seen:
            raise AcceptedCaseBlocked("Duplicate or unbounded official action identity")
        seen.add(notice)
        original = action.get("original_file")
        _kind(files, original, "ACTION_ORIGINAL")
        if original in used_action_originals:
            raise AcceptedCaseBlocked("One retained action original cannot represent multiple notices")
        used_action_originals.add(original)
        _sam_record_reference(files[original], action_id=notice)
        if action["type"] == "AMENDMENT" and not (
            isinstance(action.get("amendment_number"), str)
            and action["amendment_number"].strip()):
            raise AcceptedCaseBlocked("Amendment identity/version is missing")
        published_at = timestamp(action.get("published_at"))
        if published_at > now:
            raise AcceptedCaseBlocked("History action publication is future-dated")
        published_actions.append((action["type"], published_at))
    # A reviewed family must contain the original solicitation. Treat OTHER
    # as potentially pre-solicitation rather than assuming the list is sorted,
    # but an amendment, modification, cancellation or reinstatement cannot
    # originate before the earliest retained solicitation in its family.
    original_dates = [at for kind, at in published_actions if kind == "SOLICITATION"]
    if not original_dates:
        raise AcceptedCaseBlocked("Reviewed action family lacks an original solicitation")
    earliest_original = min(original_dates)
    if any(kind in {"AMENDMENT", "MODIFICATION", "CANCELLATION", "REINSTATEMENT"}
           and at < earliest_original for kind, at in published_actions):
        raise AcceptedCaseBlocked("Historical dependent action predates solicitation")
    if (len(seen) != len(expected) or seen != set(expected)
            or case.get("packet", {}).get("family_status") is None):
        raise AcceptedCaseBlocked("Actual case history differs from reviewed original set")
    resources = closure.get("resources")
    if not isinstance(resources, list) or len(resources) > 100:
        raise AcceptedCaseBlocked("Deleted-inclusive resource inventory missing")
    seen_resources: set[str] = set()
    used_resource_originals: set[str] = set()
    for item in resources:
        if not isinstance(item, dict) or item.get("state") not in {
            "CURRENT", "SUPERSEDED", "DELETED_WITH_RETAINED_ORIGINAL"
        }:
            raise AcceptedCaseBlocked("Resource was omitted or deleted with no retained original")
        resource = item.get("resource_id")
        if (not isinstance(resource, str) or not SAFE_ID.fullmatch(resource)
                or resource in seen_resources or item.get("action_id") not in seen):
            raise AcceptedCaseBlocked("Resource does not belong uniquely to the reviewed history")
        seen_resources.add(resource)
        original = item.get("original_file")
        _kind(files, original, "RESOURCE_ORIGINAL")
        if original in used_resource_originals:
            raise AcceptedCaseBlocked("One retained resource original cannot represent multiple attachment IDs")
        used_resource_originals.add(original)
        _sam_record_reference(files[original], action_id=item["action_id"],
                              resource_id=resource)
    required = {
        str(x.get("artifact_id")) for x in case.get("packet", {}).get("artifacts", [])
        if isinstance(x, dict) and x.get("required_for_analysis") is True
    }
    if not required.issubset(seen_resources):
        raise AcceptedCaseBlocked("A required case artifact is missing from full resource review")
    rules = closure.get("incorporated_sources")
    if not isinstance(rules, list) or len(rules) > 100:
        raise AcceptedCaseBlocked("Incorporated regulations/source editions are unreviewed")
    case_rules = case.get("decision_trace", {}).get("rule_versions") or []
    expected_rule_ids = {
        x.get("rule_version_id") for x in case_rules if isinstance(x, dict)
    }
    rule_ids: set[str] = set()
    for item in rules:
        if not isinstance(item, dict) or item.get("applicability") not in {
            "APPLIES", "DOES_NOT_APPLY"
        }:
            raise AcceptedCaseBlocked("Incorporated-source applicability is unresolved")
        rid = item.get("rule_version_id")
        if (not isinstance(rid, str) or rid in rule_ids
                or not isinstance(item.get("basis_locator"), str)
                or not item["basis_locator"].strip()
                or not isinstance(item.get("edition"), str)
                or not item["edition"].strip()):
            raise AcceptedCaseBlocked("Incorporated rule edition or exact basis is missing")
        rule_ids.add(rid)
        _kind(files, item.get("original_file"), "INCORPORATED_RULE")
        if not _official(files[item["original_file"]].get("source_url")):
            raise AcceptedCaseBlocked("Incorporated source lacks an official government original")
        version = next((r for r in case_rules if r.get("rule_version_id") == rid), None)
        if not isinstance(version, dict) or item.get("edition") != version.get("edition"):
            raise AcceptedCaseBlocked("Incorporated source edition differs from exact Decision Evidence")
    if expected_rule_ids != rule_ids:
        raise AcceptedCaseBlocked("Not every incorporated rule edition was reviewed")


def _restore_and_identity(manifest: dict[str, Any], files: dict[str, dict[str, Any]],
                          data: dict[str, bytes], now: datetime) -> None:
    storage, business, report, delivery = (
        manifest.get(k) for k in ("private_storage", "business", "report", "delivery")
    )
    if any(not isinstance(x, dict) for x in (storage, business, report, delivery)):
        raise AcceptedCaseBlocked("Accepted case lacks private custody, business or release approval")
    for fid, kind in (
        (storage.get("backup_file"), "OFFDEVICE_BACKUP"),
        (storage.get("recovery_receipt_file"), "RECOVERY_RECEIPT"),
        (storage.get("authorization_ledger_snapshot_file"), "AUTHORIZATION_LEDGER_SNAPSHOT"),
        (business.get("identity_file"), "BUSINESS_EVIDENCE"),
        (business.get("inbound_receipt_file"), "INBOUND_RECEIPT"),
        (business.get("signed_scope_file"), "SCOPE_AGREEMENT"),
        (report.get("report_file"), "REPORT"),
        (report.get("report_receipt_file"), "REPORT_RECEIPT"),
        (delivery.get("body_file"), "MESSAGE_BODY"),
    ):
        _kind(files, fid, kind)
    # A signed list of filenames is not proof that the one-use send ledger
    # was actually preserved. Reuse the WAL-consistent snapshot's canonical
    # SQLite/schema/nonce verifier before accepting its restore receipt.
    try:
        from scripts.snapshot_authorization_ledger import _validate_bytes as check_nonce_snapshot
        check_nonce_snapshot(data[storage["authorization_ledger_snapshot_file"]], now=now)
    except (ImportError, OSError, ValueError):
        raise AcceptedCaseBlocked(
            "Signed case lacks a valid, independently recoverable one-use authorization ledger snapshot"
        ) from None
    try:
        report_receipt = json.loads(data[report["report_receipt_file"]], object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise AcceptedCaseBlocked("Report receipt cannot be independently read") from None
    if (not isinstance(report_receipt, dict)
            or report_receipt.get("case_sha256") != manifest["case_sha256"]
            or report_receipt.get("report_sha256", report_receipt.get("bundle_sha256"))
                 != files[report["report_file"]]["sha256"]):
        raise AcceptedCaseBlocked("Report receipt does not match the actual completed bytes and case")
    if (storage.get("approved_by_owner") is not True
            or storage.get("encrypted_at_rest") is not True
            or storage.get("private_acl_checked") is not True
            or storage.get("separate_recovery_key_custody") is not True
            or not isinstance(storage.get("approval_reference"), str)
            or len(storage["approval_reference"].strip()) < 6
            or not isinstance(storage.get("offdevice_provider_receipt"), str)
            or len(storage["offdevice_provider_receipt"].strip()) < 6
            or not isinstance(storage.get("key_custodian_id"), str)
            or len(storage["key_custodian_id"].strip()) < 3
            or not isinstance(storage.get("primary_device_id"), str)
            or not isinstance(storage.get("restore_device_id"), str)
            or storage["primary_device_id"] == storage["restore_device_id"]):
        raise AcceptedCaseBlocked("Approved customer-private environment and independent key custody unproven")
    try:
        proof = json.loads(data[storage["recovery_receipt_file"]], object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise AcceptedCaseBlocked("Independently produced recovery receipt is corrupt") from None
    if not isinstance(proof, dict) or proof.get("schema") != RECOVERY_SCHEMA:
        raise AcceptedCaseBlocked("Independent recovery proof has an unknown schema")
    original_backup = files[storage["backup_file"]]["sha256"]
    if (proof.get("offdevice_backup_sha256") != original_backup
            or proof.get("restore_device_id") != storage["restore_device_id"]
            or proof.get("primary_device_id") != storage["primary_device_id"]
            or proof.get("key_custodian_id") != storage["key_custodian_id"]
            or proof.get("restoration_method") != "NEW_DEVICE_RETRIEVAL_AND_DECRYPTION"
            or proof.get("restored_and_verified") is not True
            or proof.get("restored_files") != {
                x["id"]: x["sha256"] for x in manifest["files"]
                if x["kind"] not in {"OFFDEVICE_BACKUP", "RECOVERY_RECEIPT"}
            }):
        raise AcceptedCaseBlocked("Off-device restored full case does not match every retained original")
    recovered_at = timestamp(proof.get("restored_at"))
    if timestamp(storage.get("recovery_completed_at")) != recovered_at:
        raise AcceptedCaseBlocked("Recovery custodian signoff time differs from original restore receipt")
    if recovered_at > now or now - recovered_at > timedelta(days=30):
        raise AcceptedCaseBlocked("Independent restoration evidence is stale or future-dated")
    email = business.get("verified_recipient")
    if (business.get("method") != "INDEPENDENT_REGISTRY_AND_CONTROLLED_CHANNEL"
            or business.get("identity_verified") is not True
            or business.get("scope_accepted") is not True
            or not isinstance(business.get("canonical_business_key"), str)
            or not business["canonical_business_key"].startswith(("registry:", "domain:"))
            or not isinstance(email, str) or not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{3,200}", email)
            or business.get("verified_at") is None):
        raise AcceptedCaseBlocked("Real business identity, inbound receipt and agreed scope unverified")
    verified_at = timestamp(business["verified_at"])
    if verified_at > now:
        raise AcceptedCaseBlocked("Business verification is future-dated")
    if (report.get("full_human_review") is not True
            or report.get("unresolved_material_conclusions") != []
            or report.get("reviewed_at") is None):
        raise AcceptedCaseBlocked("Completed report has no real human review of its actual bytes")
    reviewed_at = timestamp(report["reviewed_at"])
    if not verified_at <= reviewed_at <= now:
        raise AcceptedCaseBlocked("Report was reviewed before customer verification or in the future")
    if (delivery.get("manual_only") is not True or delivery.get("max_sends") != 1
            or delivery.get("external_send_approved") is not True
            or delivery.get("recipient") != email
            or not isinstance(delivery.get("authorization_nonce"), str)
            or not HEX32.fullmatch(delivery["authorization_nonce"])
            or delivery.get("subject") is None
            or not isinstance(delivery.get("subject"), str)
            or not 1 <= len(delivery["subject"]) <= 200
            or delivery.get("attachment_file") != report["report_file"]):
        raise AcceptedCaseBlocked("Explicit unique per-recipient and per-report delivery approval absent")
    expires = timestamp(delivery.get("expires_at"))
    if expires <= now or expires > now + timedelta(hours=24):
        raise AcceptedCaseBlocked("One-message authorization expired or has excessive duration")


def signature_payload(manifest_without_signatures: dict[str, Any],
                      role: str, key_id: str, signed_at: str) -> bytes:
    """Public signature domain; owner must use an EXTERNAL signing/custody process."""
    if role not in ROLES or not isinstance(key_id, str) or not SAFE_ID.fullmatch(key_id):
        raise AcceptedCaseBlocked("Unsupported release attestation role or signer")
    return b"CaptureBrief accepted-case release v1\x00" + canonical({
        "role": role, "key_id": key_id, "signed_at": signed_at,
        "manifest_sha256": sha256(canonical(manifest_without_signatures)),
    })


def verify_attestations(manifest: dict[str, Any], trusted_keys: dict[str, Any],
                        now: datetime) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        raise AcceptedCaseBlocked("Pinned cryptography dependency required for approval verification") from None
    if trusted_keys.get("schema") != TRUST_SCHEMA:
        raise AcceptedCaseBlocked("Private externally provisioned signer roster is missing")
    roster = trusted_keys.get("signers")
    attestations = manifest.get("attestations")
    if not isinstance(roster, list) or not isinstance(attestations, list):
        raise AcceptedCaseBlocked("Independent human and recovery signer roster is incomplete")
    lookup: dict[tuple[str, str], bytes] = {}
    for row in roster:
        if not isinstance(row, dict) or row.get("role") not in ROLES:
            raise AcceptedCaseBlocked("Unapproved signer role in private trust store")
        try:
            pub = base64.b64decode(row["public_key_base64"], validate=True)
        except (KeyError, ValueError, TypeError):
            raise AcceptedCaseBlocked("Invalid trusted public key") from None
        key = (row["role"], row.get("key_id"))
        if not isinstance(key[1], str) or not SAFE_ID.fullmatch(key[1]) or len(pub) != 32 or key in lookup:
            raise AcceptedCaseBlocked("Ambiguous or malformed trusted reviewer key")
        lookup[key] = pub
    unsigned = {k: v for k, v in manifest.items() if k != "attestations"}
    by_role: set[str] = set()
    distinct_keys: set[str] = set()
    distinct_public_keys: set[bytes] = set()
    prerequisite_time = max(
        timestamp(manifest["business"]["verified_at"]),
        timestamp(manifest["report"]["reviewed_at"]),
        timestamp(manifest["private_storage"]["recovery_completed_at"]),
    )
    for row in attestations:
        if not isinstance(row, dict) or set(row) != {
            "role", "key_id", "signed_at", "signature_base64"
        }:
            raise AcceptedCaseBlocked("Unsigned or malformed approval evidence")
        role, key_id = row["role"], row["key_id"]
        if (role in by_role or (role, key_id) not in lookup or key_id in distinct_keys
                or lookup[(role, key_id)] in distinct_public_keys):
            raise AcceptedCaseBlocked("Missing trusted signer or reused identity across independent roles")
        signed_at = timestamp(row["signed_at"])
        if signed_at > now or now - signed_at > timedelta(days=7):
            raise AcceptedCaseBlocked("Human approval was not fresh")
        if signed_at < prerequisite_time:
            raise AcceptedCaseBlocked("Signoff predates full report review or independent recovery")
        if role == "DELIVERY_APPROVER" and now - signed_at > timedelta(hours=24):
            raise AcceptedCaseBlocked("One-message authorization must be approved within 24 hours")
        try:
            sig = base64.b64decode(row["signature_base64"], validate=True)
            Ed25519PublicKey.from_public_bytes(lookup[(role, key_id)]).verify(
                sig, signature_payload(unsigned, role, key_id, row["signed_at"])
            )
        except (ValueError, TypeError, InvalidSignature):
            raise AcceptedCaseBlocked("Human/recovery release attestation signature did not verify") from None
        by_role.add(role)
        distinct_keys.add(key_id)
        distinct_public_keys.add(lookup[(role, key_id)])
    if by_role != set(ROLES):
        raise AcceptedCaseBlocked("Every independent business, source, recovery and delivery approval is required")


def inspect_accepted_case(
    case: dict[str, Any], manifest: dict[str, Any], *,
    private_root: str | Path, trusted_keys: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only gate. NEVER performs or confirms a customer send."""
    checked = now if now is not None else datetime.now(timezone.utc)
    if checked.utcoffset() is None:
        raise AcceptedCaseBlocked("Inspection clock must have a timezone")
    checked = checked.astimezone(timezone.utc)
    if not isinstance(case, dict) or not isinstance(manifest, dict):
        raise AcceptedCaseBlocked("Private case and release manifest must be objects")
    if manifest.get("schema") != SCHEMA or manifest.get("case_id") != case.get("case_id"):
        raise AcceptedCaseBlocked("Release evidence is for another case or schema")
    if manifest.get("family_id") != case.get("family_id"):
        raise AcceptedCaseBlocked("Release evidence is for a different solicitation family")
    if manifest.get("case_sha256") != sha256(canonical(case)):
        raise AcceptedCaseBlocked("Reviewed case was modified after evidence lock")
    root = _root(private_root)
    files, data = _files(manifest, root)
    case_files = [x for x in files.values() if x["kind"] == "CASE"]
    if sha256(data[case_files[0]["id"]]) != sha256(canonical(case)):
        # Raw file is allowed pretty-printed JSON, but must decode to exact
        # case object. It must not be a different case with a matching label.
        try:
            original = json.loads(data[case_files[0]["id"]], object_pairs_hook=_unique)
        except (ValueError, UnicodeError):
            raise AcceptedCaseBlocked("Retained original case is corrupt") from None
        if canonical(original) != canonical(case):
            raise AcceptedCaseBlocked("Retained original case is not the reviewed case")
    _source_closure(case, manifest, files, checked)
    _restore_and_identity(manifest, files, data, checked)
    verify_attestations(manifest, trusted_keys, checked)
    readiness = evaluate_delivery_readiness(case, now=checked)
    if not readiness.eligible:
        # Codes are safe operational metadata, not raw customer data.
        raise AcceptedCaseBlocked(
            "Full core history, sources and Decision Evidence remain blocked: "
            + ",".join(readiness.blocker_codes[:20])
        )
    return {
        "status": "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY",
        "case_tag": sha256(str(case["case_id"]).encode("utf-8"))[:16],
        "source_action_count": len(manifest["source_closure"]["actions"]),
        "reviewed_resource_count": len(manifest["source_closure"]["resources"]),
        "incorporated_source_count": len(manifest["source_closure"]["incorporated_sources"]),
        "independent_roles_verified": list(ROLES),
        "delivery_nonce_tag": sha256(manifest["delivery"]["authorization_nonce"].encode())[:12],
        "external_send_performed": False,
        "payment_performed": False,
        "real_customer_delivery_verified": False,
    }
