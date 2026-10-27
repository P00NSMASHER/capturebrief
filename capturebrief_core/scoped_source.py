"""On-demand first-party SAM source observation for one private free-check case.

This stores an immutable *candidate* API observation, never a completed history,
payment, delivery or human review. Full-catalog FY2027 rules remain unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

from .atomic_io import ensure_exact_bytes, exclusive_path_lock
from .case_current import apply_current_api_observation, CaseCurrentError
from .current_api import (
    SEARCH_URL, fetch_latest_active, validate_api_observation,
    _approved_search_final_url, CurrentApiError,
)
from .history import validate_history_receipts
from .model import canonical_json, parse_dt, sha256_hex
from .request_draft import FREE_OFFER

REPO = Path(__file__).resolve().parents[1]
SCHEMA = "capturebrief-scoped-sam-candidate-v1"
CASE_NOTICE = re.compile(r"^/opp/([0-9a-f]{32})/view/?$", re.I)
NOTICE_ID = re.compile(r"^[0-9a-f]{32}$", re.I)
SAFE_SOLICITATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,99}$")
MAX_CASE_BYTES = 256 * 1024
MAX_CAPTURE_BYTES = 512 * 1024
MAX_API_BYTES = 2 * 1024 * 1024
MAX_CAPTURE_AGE = timedelta(hours=24)


class ScopedSourceBlocked(ValueError):
    """Bounded source inspection failed without authorizing customer action."""


class ScopedApiRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _approved_search_final_url(newurl):
            raise ScopedSourceBlocked("SAM API redirect outside the documented source")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _private_path(value: str | Path, *, directory: bool) -> Path:
    raw = Path(value).expanduser().absolute()
    for part in (raw, *raw.parents):
        junction = getattr(part, "is_junction", None)
        if part.is_symlink() or (junction is not None and junction()):
            raise ScopedSourceBlocked("Private evidence path may not traverse links")
    actual = raw.resolve(strict=directory)
    if actual == REPO or actual.is_relative_to(REPO):
        raise ScopedSourceBlocked("Customer evidence must stay outside the public repository")
    if any(p.name.casefold() in {".git", "gh-pages"} for p in (actual, *actual.parents)):
        raise ScopedSourceBlocked("Customer evidence path is not a private workspace")
    if any((p / ".git").exists() for p in (actual, *actual.parents) if p.is_dir()):
        raise ScopedSourceBlocked("Customer evidence may not be written to a Git checkout")
    if directory:
        if not actual.is_dir():
            raise ScopedSourceBlocked("Private evidence root is not a directory")
        if os.name != "nt" and actual.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ScopedSourceBlocked("Private evidence root must have owner-only permissions (0700)")
    elif not actual.is_file() or (os.name != "nt" and
                                   actual.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)):
        raise ScopedSourceBlocked("Private input must be a regular owner-only file")
    return actual


def private_root(value: str | Path) -> Path:
    """An already provisioned owner-only directory; not a storage-encryption assertion."""
    return _private_path(value, directory=True)


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ScopedSourceBlocked("Duplicate private case JSON key")
        obj[key] = value
    return obj


def read_private_case(path: str | Path) -> dict[str, Any]:
    source = _private_path(path, directory=False)
    if not 0 < source.stat().st_size <= MAX_CASE_BYTES:
        raise ScopedSourceBlocked("Private case has invalid bounded size")
    try:
        case = json.loads(source.read_bytes().decode("utf-8"), object_pairs_hook=_unique_fields)
    except (UnicodeError, ValueError) as exc:
        raise ScopedSourceBlocked("Private case is not valid JSON") from None
    if not isinstance(case, dict):
        raise ScopedSourceBlocked("Private case must be a JSON object")
    return case


def _intake_identity(case: dict[str, Any]) -> dict[str, Any]:
    """Stable across human enrichment but not across a changed customer request."""
    if not isinstance(case, dict) or case.get("case_schema_version") != "0.2":
        raise ScopedSourceBlocked("CaptureBrief case schema 0.2 is required")
    intake = case.get("intake")
    assumptions = case.get("assumptions")
    if not isinstance(intake, dict) or not isinstance(assumptions, list) or len(assumptions) != 1:
        raise ScopedSourceBlocked("Exactly one original free-check assumption is required")
    if (intake.get("requested_offer") != FREE_OFFER
            or intake.get("public_only_confirmation") is not True
            or intake.get("record_time_basis") != "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"):
        raise ScopedSourceBlocked("An intact private free-check intake is required")
    url = intake.get("public_opportunity")
    try:
        split = urlsplit(url)
        notice = CASE_NOTICE.fullmatch(split.path)
        canonical = (split.scheme == "https" and (split.hostname or "").lower() == "sam.gov"
                     and split.port in (None, 443) and split.username is None
                     and split.password is None and not split.query and not split.fragment)
    except (ValueError, TypeError, AttributeError):
        raise ScopedSourceBlocked("An exact public SAM opportunity URL is required") from None
    if not canonical or not notice:
        raise ScopedSourceBlocked("An exact public SAM opportunity URL is required")
    selected = assumptions[0]
    if not isinstance(selected, dict) or selected.get("assumption_id") != "A1":
        raise ScopedSourceBlocked("Original assumption identity is invalid")
    original = {
        "case_id": case.get("case_id"), "submitted_at": intake.get("submitted_at"),
        "requested_offer": intake.get("requested_offer"), "company": intake.get("company"),
        "work_email": intake.get("email"), "public_opportunity": url,
        "original_assumption_id": "A1", "original_assumption": selected.get("text"),
        "current_posture": case.get("current_posture"),
    }
    if not all(isinstance(v, str) and bool(v.strip()) for v in original.values()):
        raise ScopedSourceBlocked("The original private request is incomplete")
    return {"identity": sha256_hex(canonical_json(original)),
            "selected_notice_id": notice.group(1).lower(),
            "case_tag": sha256_hex(original["case_id"])[:24]}


def _time(value: Any) -> datetime:
    at = parse_dt(value)
    if at is None:
        raise ScopedSourceBlocked("Source observation lacks a timezone-aware time")
    return at.astimezone(timezone.utc)


def _clock(now: datetime | None) -> datetime:
    t = now or datetime.now(timezone.utc)
    if not isinstance(t, datetime) or t.utcoffset() is None:
        raise ScopedSourceBlocked("Inspection time must include timezone")
    return t.astimezone(timezone.utc)


def _source_projection(raw: dict[str, Any], *, solicitation_number: str, checked: datetime) -> dict[str, Any]:
    validate_api_observation(raw)
    record = raw["record"]
    source_at = _time(raw["observed_at"])
    if not timedelta(0) <= checked - source_at <= timedelta(minutes=5):
        raise ScopedSourceBlocked("Current public-source observation is stale or in the future")
    notice = str(record.get("noticeId") or "").lower()
    if not NOTICE_ID.fullmatch(notice):
        raise ScopedSourceBlocked("API notice ID is not a canonical SAM notice identifier")
    if str(record.get("solicitationNumber") or "").strip().upper() != solicitation_number.upper():
        raise ScopedSourceBlocked("API record does not match the requested solicitation")
    if str(record.get("active") or "").strip().lower() != "yes":
        raise ScopedSourceBlocked("Current API record is not positively ACTIVE")
    if len(raw.get("resource_links", [])) > 100:
        raise ScopedSourceBlocked("Current source links exceed the bounded review limit")
    # Only fields needed by the trusted existing current-action application
    # survive, not arbitrary provider contact fields or the raw API key.
    trimmed = {
        "source_url": SEARCH_URL,
        "source_contract": raw["source_contract"],
        "automation_mode": raw["automation_mode"],
        "observed_at": raw["observed_at"],
        "payload_sha256": raw["payload_sha256"],
        "response_sha256": raw["response_sha256"],
        "pagination": copy.deepcopy(raw["pagination"]),
        "resource_links": copy.deepcopy(raw["resource_links"]),
        "record": {field: record.get(field) for field in (
            "noticeId", "solicitationNumber", "active", "postedDate"
        )},
    }
    return trimmed


def _sealed_capture(case: dict[str, Any], observation: dict[str, Any],
                    solicitation_number: str) -> dict[str, Any]:
    identity = _intake_identity(case)
    raw = {
        "schema": SCHEMA,
        "case_identity_sha256": identity["identity"],
        "selected_notice_id": identity["selected_notice_id"],
        "solicitation_number": solicitation_number,
        "api_observation": observation,
        "source_claim": "BOUNDED_CURRENT_API_CANDIDATE_ONLY",
        "human_history_review_verified": False,
        "full_catalog_approved": False,
        "private_backup_recovery_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
        "payment_authorized": False,
    }
    return {**raw, "capture_sha256": sha256_hex(canonical_json(raw))}


def observe_scoped_case(
    case: dict[str, Any], *, solicitation_number: str, posted_from: str,
    posted_to: str, api_key: str, private_dir: str | Path,
    now: datetime | None = None, fetcher: Callable[..., dict[str, Any]] = fetch_latest_active,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Fetch only the selected current solicitation, retain an immutable private receipt.

    A source capture is not historical completeness. No full archive, R2, payment,
    customer contact, human review, or automatic delivery operation occurs.
    """
    identity = _intake_identity(case)
    root = private_root(private_dir)
    if (not isinstance(solicitation_number, str) or
            not SAFE_SOLICITATION.fullmatch(solicitation_number) or
            solicitation_number != solicitation_number.strip()):
        raise ScopedSourceBlocked("An explicit bounded solicitation number is required")
    if not api_key:
        raise ScopedSourceBlocked("SAM_API_KEY must be present in the private environment")
    kwargs: dict[str, Any] = {
        "solicitation_number": solicitation_number,
        "posted_from": posted_from,
        "posted_to": posted_to,
        "api_key": api_key,
        "timeout": 30.0,
        "max_response_bytes": MAX_API_BYTES,
    }
    if opener is not None:
        kwargs["opener"] = opener
    try:
        raw = fetcher(**kwargs)
        # Record the evaluation clock after the provider response; the source
        # observation is made during fetch, not before it begins.
        checked = _clock(now)
        observation = _source_projection(raw, solicitation_number=solicitation_number, checked=checked)
    except (CurrentApiError, ValueError, TypeError, KeyError, OSError) as exc:
        # The provider's original exception can contain credential-bearing URLs.
        raise ScopedSourceBlocked("Exact scoped SAM source observation failed") from None
    capture = _sealed_capture(case, observation, solicitation_number)
    blob = (json.dumps(capture, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(blob) > MAX_CAPTURE_BYTES:
        raise ScopedSourceBlocked("Scoped observation exceeds the private receipt bound")
    case_dir = root / ("case-" + identity["case_tag"])
    if case_dir.is_symlink() or (case_dir.exists() and not case_dir.is_dir()):
        raise ScopedSourceBlocked("Private case folder is not a regular directory")
    case_dir.mkdir(mode=0o700, exist_ok=True)
    if os.name != "nt" and case_dir.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ScopedSourceBlocked("Private case folder must be owner-only")
    filename = "sam-current-" + capture["capture_sha256"] + ".json"
    with exclusive_path_lock(case_dir / ".scoped-observation", timeout_seconds=5):
        ensure_exact_bytes(case_dir / filename, blob, mode=0o600)
    return {
        "status": "SCOPED_SAM_SOURCE_OBSERVED_REVIEW_REQUIRED",
        "case_tag": identity["case_tag"],
        "capture_sha256": capture["capture_sha256"],
        "private_observation_file": filename,
        "api_record_matches_solicitation": True,
        "selected_notice_matches_latest_api": (
            identity["selected_notice_id"] ==
            str(observation["record"]["noticeId"]).lower()
        ),
        "history_completion_verified": False,
        "private_backup_recovery_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
        "payment_authorized": False,
    }


def verify_scoped_capture(
    case: dict[str, Any], capture: dict[str, Any], *, now: datetime | None = None,
) -> dict[str, Any]:
    """Integrity + case-binding check, NOT independent provider authentication."""
    identity = _intake_identity(case)
    if not isinstance(capture, dict) or capture.get("schema") != SCHEMA:
        raise ScopedSourceBlocked("Scoped source capture schema is unsupported")
    required = {
        "schema", "case_identity_sha256", "selected_notice_id", "solicitation_number",
        "api_observation", "source_claim", "human_history_review_verified",
        "full_catalog_approved", "private_backup_recovery_verified",
        "customer_release_authorized", "external_send_authorized",
        "payment_authorized", "capture_sha256",
    }
    if set(capture) != required:
        raise ScopedSourceBlocked("Scoped source capture has unexpected fields")
    core = {key: value for key, value in capture.items() if key != "capture_sha256"}
    if capture["capture_sha256"] != sha256_hex(canonical_json(core)):
        raise ScopedSourceBlocked("Scoped source capture integrity check failed")
    if capture["case_identity_sha256"] != identity["identity"] or (
            capture["selected_notice_id"] != identity["selected_notice_id"]):
        raise ScopedSourceBlocked("Scoped source belongs to a different original request")
    for flag in ("human_history_review_verified", "full_catalog_approved",
                 "private_backup_recovery_verified", "customer_release_authorized",
                 "external_send_authorized", "payment_authorized"):
        if capture.get(flag) is not False:
            raise ScopedSourceBlocked("Scoped source may not assert release authority")
    if capture.get("source_claim") != "BOUNDED_CURRENT_API_CANDIDATE_ONLY":
        raise ScopedSourceBlocked("Scoped observation makes an unsupported source claim")
    obs = capture.get("api_observation")
    if not isinstance(obs, dict):
        raise ScopedSourceBlocked("Scoped source is missing its validated API projection")
    validate_api_observation(obs)
    _source_projection(obs, solicitation_number=capture["solicitation_number"],
                       checked=_time(obs["observed_at"]))
    age = _clock(now) - _time(obs["observed_at"])
    if age < timedelta(0) or age > MAX_CAPTURE_AGE:
        raise ScopedSourceBlocked("Scoped source has expired or is future-dated")
    return obs


def _bound_history_review_source(
    case: dict[str, Any], capture: dict[str, Any], *,
    private_dir: str | Path, now: datetime,
) -> None:
    """Verify that the manual complete-history claim references retained bytes.

    Hashes and user-supplied review identifiers are NOT proof of independent
    reviewer identity or of official publisher authenticity. Both must be
    separately checked by the operator prior to any customer release.
    """
    original = _intake_identity(case)
    case_dir = private_root(private_root(private_dir) / ("case-" + original["case_tag"]))
    reviews = [
        r for r in (case.get("packet") or {}).get("history_receipts") or []
        if r.get("source_surface") == "SAM_HISTORY"
    ]
    if len(reviews) != 1:
        raise ScopedSourceBlocked("Exactly one reviewed first-party SAM_HISTORY receipt is required")
    receipt = reviews[0]
    payload = receipt.get("evidence_payload")
    review = payload.get("manual_review") if isinstance(payload, dict) else None
    if not isinstance(review, dict) or set(review) != {
        "scope", "source_sha256", "reviewer_id", "reviewed_at", "review_reference"
    }:
        raise ScopedSourceBlocked("Operator manual-history provenance is incomplete")
    if (review["scope"] != "COMPLETE_ACTION_SET"
            or not isinstance(review["reviewer_id"], str)
            or not 3 <= len(review["reviewer_id"].strip()) <= 100
            or not isinstance(review["review_reference"], str)
            or not 3 <= len(review["review_reference"].strip()) <= 200
            or not re.fullmatch(r"[0-9a-f]{64}", str(review["source_sha256"]))):
        raise ScopedSourceBlocked("Manual history review scope, identity or hash is invalid")
    reviewed = _time(review["reviewed_at"])
    captured_at = _time(receipt.get("observed_at"))
    if not captured_at <= reviewed <= now or now - reviewed > timedelta(days=7):
        raise ScopedSourceBlocked("Manual history review is future-dated, stale, or predates source observation")
    expected_name = "public-source-" + review["source_sha256"] + ".bin"
    source = _private_path(case_dir / expected_name, directory=False)
    receipt_file = _private_path(case_dir / (expected_name + ".receipt.json"), directory=False)
    if not 0 < source.stat().st_size <= 50 * 1024 * 1024:
        raise ScopedSourceBlocked("Manual history source original exceeds reviewed bounds")
    with source.open("rb") as stream:
        raw = stream.read(50 * 1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != review["source_sha256"]:
        raise ScopedSourceBlocked("Manual history source bytes do not match retained review")
    if not 0 < receipt_file.stat().st_size <= 16 * 1024:
        raise ScopedSourceBlocked("Manual history source receipt is too large")
    try:
        source_receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError):
        raise ScopedSourceBlocked("Retained history source receipt is unreadable") from None
    if (source_receipt.get("schema") != "capturebrief-scoped-review-source-v1"
            or source_receipt.get("case_identity_sha256") != original["identity"]
            or source_receipt.get("source_sha256") != review["source_sha256"]
            or source_receipt.get("source_bytes") != len(raw)
            or source_receipt.get("source_url") != receipt.get("source_url")
            or source_receipt.get("capture_mode") != "OPERATOR_SUPPLIED_FOR_INDEPENDENT_REVIEW"
            or source_receipt.get("publisher_authenticity_verified") is not False
            or source_receipt.get("history_completeness_verified") is not False
            or source_receipt.get("customer_release_authorized") is not False):
        raise ScopedSourceBlocked("Reviewed source provenance or release boundary is inconsistent")


def bind_reviewed_scoped_case(
    case: dict[str, Any], capture: dict[str, Any], *,
    private_dir: str | Path, now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply existing strict current-action rules only after distinct reviewed history.

    The separate manifest, reference, Decision Evidence, backup, human review,
    and free-report release gates are intentionally NOT satisfied by this call.
    """
    checked = _clock(now)
    obs = verify_scoped_capture(case, capture, now=checked)
    packet = case.get("packet") or {}
    action_ids = [str(x).lower() for x in packet.get("history_action_ids") or []]
    chosen = _intake_identity(case)["selected_notice_id"]
    current = str(obs["record"]["noticeId"]).lower()
    if chosen not in action_ids or current not in action_ids:
        raise ScopedSourceBlocked("Original and current notices must both belong to reviewed family history")
    history_state, _ = validate_history_receipts(
        packet.get("history_action_ids") or [], packet.get("history_receipts") or []
    )
    if history_state != "HISTORY_COMPLETE":
        raise ScopedSourceBlocked("Complete human-reviewed first-party family history required")
    _bound_history_review_source(case, capture, private_dir=private_dir, now=checked)
    # SAM_HISTORY is a manual source of reviewed evidence, not automatically
    # inferred from the single current API record.
    if not any(r.get("source_surface") == "SAM_HISTORY" and
               isinstance(r.get("evidence_payload"), dict) and
               isinstance(r["evidence_payload"].get("family"), dict) and
               r["evidence_payload"]["family"].get("solicitation_number", "").strip().upper()
                 == capture["solicitation_number"].upper()
               for r in packet.get("history_receipts") or []):
        raise ScopedSourceBlocked("A separate matching human-supervised SAM_HISTORY receipt is required")
    try:
        updated, transition = apply_current_api_observation(case, obs)
    except (CaseCurrentError, CurrentApiError, ValueError, TypeError, KeyError):
        raise ScopedSourceBlocked("Scoped current action cannot be bound to reviewed case") from None
    return updated, {
        "status": "CURRENT_API_BOUND_REMAINING_EVIDENCE_REVIEW_REQUIRED",
        "capture_sha256": capture["capture_sha256"],
        "current_action_observed": True,
        "history_review_claim_present": True,
        "manifests_and_reference_closure_still_required": True,
        "independent_backup_recovery_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def retain_review_source(
    case: dict[str, Any], *, original_file: str | Path, source_url: str,
    private_dir: str | Path, observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Retain ONE operator-supplied public document privately for scoped review.

    Source URL provenance and completeness remain unverified. The reviewer must
    independently confirm original publisher bytes, version and applicability.
    This does not fabricate an action history, attachment manifest or citation.
    """
    identity = _intake_identity(case)
    root = private_root(private_dir)
    source = _private_path(original_file, directory=False)
    if source == root or source.is_relative_to(root):
        raise ScopedSourceBlocked("Original input must not alias the scoped retention tree")
    if not 0 < source.stat().st_size <= 50 * 1024 * 1024:
        raise ScopedSourceBlocked("One reviewed document must be 1-50 MiB")
    try:
        url = urlsplit(source_url)
        host = (url.hostname or "").lower()
        valid = (url.scheme == "https" and url.username is None and
                 url.password is None and url.port in (None, 443) and
                 not url.fragment and not url.query and host in {
                     "sam.gov", "www.sam.gov", "acquisition.gov",
                     "www.acquisition.gov", "gsa.gov", "www.gsa.gov"
                 })
    except (TypeError, ValueError):
        raise ScopedSourceBlocked("Source must use an approved public government HTTPS host") from None
    if not valid:
        raise ScopedSourceBlocked("Source must use an approved public government HTTPS host")
    observed = _clock(observed_at)
    # Double bounded read; operator-owned path may mutate during collection.
    first = source.stat()
    with source.open("rb") as handle:
        original = handle.read(50 * 1024 * 1024 + 1)
    last = source.stat()
    if (not original or len(original) > 50 * 1024 * 1024 or
            first.st_size != len(original) or first.st_mtime_ns != last.st_mtime_ns):
        raise ScopedSourceBlocked("Reviewed document changed while being retained")
    digest = hashlib.sha256(original).hexdigest()
    case_dir = root / ("case-" + identity["case_tag"])
    if case_dir.is_symlink() or (case_dir.exists() and not case_dir.is_dir()):
        raise ScopedSourceBlocked("Scoped case folder is not a regular private directory")
    case_dir.mkdir(mode=0o700, exist_ok=True)
    if os.name != "nt" and case_dir.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ScopedSourceBlocked("Scoped case folder must have owner-only permissions")
    # Scope-specific names are derived from content digests, not buyer filenames.
    name = "public-source-" + digest + ".bin"
    receipt = {
        "schema": "capturebrief-scoped-review-source-v1",
        "case_identity_sha256": identity["identity"],
        "source_url": source_url,
        "source_sha256": digest,
        "source_bytes": len(original),
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "capture_mode": "OPERATOR_SUPPLIED_FOR_INDEPENDENT_REVIEW",
        "publisher_authenticity_verified": False,
        "history_completeness_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
        "retained_filename": name,
    }
    bytes_receipt = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    with exclusive_path_lock(case_dir / ".review-source", timeout_seconds=5):
        ensure_exact_bytes(case_dir / name, original, mode=0o400)
        ensure_exact_bytes(case_dir / (name + ".receipt.json"), bytes_receipt, mode=0o600)
    return {
        "status": "PUBLIC_DOCUMENT_RETAINED_SOURCE_REVIEW_REQUIRED",
        "case_tag": identity["case_tag"], "source_sha256": digest,
        "source_bytes": len(original),
        "publisher_authenticity_verified": False,
        "history_completeness_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }
