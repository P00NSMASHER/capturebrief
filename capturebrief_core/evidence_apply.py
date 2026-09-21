from __future__ import annotations

import copy
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from .authority import validate_current_action_receipts
from .history import validate_history_receipts
from .model import history_set_digest, parse_dt, valid_sha256
from .source_policy import classify_sam_url


class EvidenceApplyError(ValueError):
    pass


def _replace_source(case: dict[str, Any], source: dict[str, Any]) -> None:
    sources = list(case.setdefault("sources", []))
    sid = str(source.get("source_id") or "")
    if not sid:
        raise EvidenceApplyError("source_id is required")
    for idx, existing in enumerate(sources):
        if str(existing.get("source_id") or "") == sid:
            sources[idx] = source
            case["sources"] = sources
            return
    sources.append(source)
    case["sources"] = sources


def _slug(value: Any) -> str:
    raw = str(value or "UNKNOWN").strip().upper()
    return re.sub(r"[^A-Z0-9._-]+", "-", raw).strip("-") or "UNKNOWN"


def _resource_id_from_url(url: Any) -> str | None:
    if not isinstance(url, str) or not url:
        return None
    path = urlparse(url).path
    marker = "/resources/files/"
    if marker not in path:
        return None
    rid = path.split(marker, 1)[1].split("/", 1)[0].strip()
    return rid or None


def apply_history_receipt(case: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Apply semantically valid Data Services membership without claiming currentness."""
    if str(receipt.get("source_surface") or "").upper() != "SAM_DATA_SERVICES":
        raise EvidenceApplyError("history receipt must come from SAM_DATA_SERVICES")
    actions = sorted({str(x) for x in receipt.get("action_ids", []) if str(x)})
    if not actions:
        raise EvidenceApplyError("history receipt contains no action IDs")

    verdict, findings = validate_history_receipts(actions, [receipt])
    if verdict != "HISTORY_COMPLETE":
        codes = ",".join(sorted({finding.code for finding in findings}))
        raise EvidenceApplyError(
            f"history receipt does not satisfy the approved-source contract: {codes}"
        )

    out = copy.deepcopy(case)
    packet = out.setdefault("packet", {})
    new_digest = receipt["history_set_sha256"]

    prior = list(packet.get("prior_history_receipts") or [])
    for old in packet.get("history_receipts") or []:
        if old.get("history_set_sha256") != new_digest:
            prior.append(old)
    packet["prior_history_receipts"] = prior
    packet["history_action_ids"] = actions
    packet["history_receipts"] = [copy.deepcopy(receipt)]

    payload = receipt.get("evidence_payload") or {}
    family = payload.get("family") or {}
    packet["history_scope"] = copy.deepcopy(payload.get("scope") or {})
    packet["history_status"] = receipt.get("status")

    if family.get("solicitation_number"):
        out["family_id"] = (
            f"SAM-{_slug(family.get('solicitation_number'))}-"
            f"{_slug(family.get('aac_code'))}"
        )

    _replace_source(out, {
        "source_id": f"sam-data-services-{receipt['evidence_payload_sha256'][:12]}",
        "url": receipt.get("source_url"),
        "authority": "SUPPORTING",
        "artifact_state": "PUBLIC",
        "observed_at": receipt.get("observed_at"),
        "content_sha256": receipt.get("evidence_payload_sha256"),
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
        "automation_mode": "APPROVED_EXTRACT",
    })

    active_current = []
    prior_current = list(packet.get("prior_current_action_receipts") or [])
    for current in out.get("current_action_receipts") or []:
        if (
            current.get("history_set_sha256") == new_digest
            and current.get("asserted_action_id") in actions
        ):
            active_current.append(current)
        else:
            prior_current.append(current)
    out["current_action_receipts"] = active_current
    packet["prior_current_action_receipts"] = prior_current

    if packet.get("current_action_id") not in actions:
        packet.pop("current_action_id", None)
        packet.pop("current_api_observation", None)
        if str(packet.get("family_status") or "UNKNOWN").upper() == "ACTIVE":
            packet["family_status"] = "UNKNOWN"

    return out


def _upsert_artifact(
    packet: dict[str, Any],
    artifact: dict[str, Any],
    *,
    prefer_new: bool = False,
) -> None:
    artifacts = list(packet.get("artifacts") or [])
    aid = str(artifact.get("artifact_id") or "")
    for idx, existing in enumerate(artifacts):
        if str(existing.get("artifact_id") or "") != aid:
            continue
        if prefer_new:
            merged = dict(existing)
            merged.update({k: v for k, v in artifact.items() if v is not None})
        else:
            merged = dict(artifact)
            merged.update({k: v for k, v in existing.items() if v not in (None, "")})
            for key in ("resource_url", "source_object_state", "source_contract"):
                if artifact.get(key) is not None:
                    merged[key] = artifact[key]
        artifacts[idx] = merged
        packet["artifacts"] = artifacts
        return
    artifacts.append(artifact)
    packet["artifacts"] = artifacts


def apply_current_api_evidence(
    case: dict[str, Any],
    current_receipt: dict[str, Any],
    api_observation: dict[str, Any],
) -> dict[str, Any]:
    """Bind a documented latest-active API observation to an established history set."""
    out = copy.deepcopy(case)
    packet = out.setdefault("packet", {})
    history_ids = [str(x) for x in packet.get("history_action_ids") or []]
    if not history_ids:
        raise EvidenceApplyError("apply history evidence before current-action evidence")

    record = api_observation.get("record") or {}
    action_id = str(record.get("noticeId") or "")
    if not action_id or action_id != str(current_receipt.get("asserted_action_id") or ""):
        raise EvidenceApplyError(
            "API observation and current receipt do not identify the same action"
        )
    if action_id not in set(history_ids):
        raise EvidenceApplyError("current action is outside the observed history set")
    if str(api_observation.get("source_contract") or "") != "SAM_GET_OPPORTUNITIES_V2":
        raise EvidenceApplyError(
            "API observation is not from the documented Opportunities v2 contract"
        )
    if str(api_observation.get("automation_mode") or "") != "APPROVED_API":
        raise EvidenceApplyError("API observation is not marked APPROVED_API")
    if not valid_sha256(api_observation.get("payload_sha256")):
        raise EvidenceApplyError("API observation payload digest is invalid")

    observed = parse_dt(current_receipt.get("observed_at"))
    if not observed:
        raise EvidenceApplyError("current receipt observation time is invalid")
    verdict, verified_action, findings = validate_current_action_receipts(
        history_ids,
        "ACTIVE",
        [current_receipt],
        now=observed,
    )
    if verdict != "CURRENT_VERIFIED" or verified_action != action_id:
        codes = ",".join(sorted({finding.code for finding in findings}))
        raise EvidenceApplyError(
            f"current receipt does not satisfy the approved-source contract: {codes}"
        )

    packet["family_status"] = "ACTIVE"
    packet["current_action_id"] = action_id
    packet["current_api_observation"] = copy.deepcopy(api_observation)
    out["current_action_receipts"] = [copy.deepcopy(current_receipt)]

    _replace_source(out, {
        "source_id": f"sam-current-api-{_slug(action_id)}",
        "url": api_observation.get("source_url"),
        "authority": "CONTROLLING_CURRENT",
        "artifact_state": "PUBLIC",
        "observed_at": api_observation.get("observed_at"),
        "content_sha256": api_observation.get("payload_sha256"),
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
    })

    link_records = []
    for link in api_observation.get("resource_links") or []:
        source_class = classify_sam_url(str(link))
        resource_id = _resource_id_from_url(link)
        link_records.append({
            "url": link,
            "source_class": source_class,
            "resource_id": resource_id,
            "automation_allowed": source_class == "SAM_API_RESOURCE_LINK",
        })
        if resource_id and source_class == "SAM_API_RESOURCE_LINK":
            _upsert_artifact(packet, {
                "artifact_id": resource_id,
                "name": f"SAM resource {resource_id[:12]}",
                "state": "UNKNOWN",
                "required_for_analysis": False,
                "sha256": None,
                "source_object_state": "VERIFIED_SOURCE_OBJECT",
                "byte_state": "BYTES_NOT_YET_CHECKED",
                "resource_url": link,
                "source_contract": "SAM_GET_OPPORTUNITIES_RESOURCE_LINK",
            })
    packet["current_resource_links"] = link_records
    return out


def apply_byte_receipt(
    case: dict[str, Any],
    receipt: dict[str, Any],
    *,
    artifact_id: str | None = None,
    name: str | None = None,
    required_for_analysis: bool | None = None,
) -> dict[str, Any]:
    """Promote one approved API resource after verified byte capture."""
    if str(receipt.get("source_contract") or "") != "SAM_GET_OPPORTUNITIES_RESOURCE_LINK":
        raise EvidenceApplyError(
            "byte receipt is not bound to a documented API resource link"
        )
    if str(receipt.get("automation_mode") or "") != "APPROVED_API":
        raise EvidenceApplyError("byte receipt is not marked APPROVED_API")
    if (
        receipt.get("byte_state") != "BYTES_VERIFIED_HASHED"
        or not valid_sha256(receipt.get("sha256"))
    ):
        raise EvidenceApplyError("byte receipt does not contain a verified SHA-256")
    if not parse_dt(receipt.get("observed_at")):
        raise EvidenceApplyError("byte receipt observation time is invalid")

    aid = artifact_id or _resource_id_from_url(receipt.get("source_url"))
    if not aid:
        raise EvidenceApplyError("artifact_id cannot be derived from the byte receipt")

    out = copy.deepcopy(case)
    packet = out.setdefault("packet", {})
    existing = next(
        (
            artifact
            for artifact in packet.get("artifacts") or []
            if str(artifact.get("artifact_id") or "") == aid
        ),
        None,
    )
    artifact = {
        "artifact_id": aid,
        "name": name
        or (existing or {}).get("name")
        or f"SAM resource {str(aid)[:12]}",
        "state": "PUBLIC",
        "required_for_analysis": (
            required_for_analysis
            if required_for_analysis is not None
            else bool((existing or {}).get("required_for_analysis", False))
        ),
        "sha256": receipt.get("sha256"),
        "source_object_state": "VERIFIED_SOURCE_OBJECT",
        "byte_state": "BYTES_VERIFIED_HASHED",
        "resource_url": receipt.get("source_url"),
        "source_contract": receipt.get("source_contract"),
        "byte_size": receipt.get("size"),
        "byte_observed_at": receipt.get("observed_at"),
    }
    _upsert_artifact(packet, artifact, prefer_new=True)

    _replace_source(out, {
        "source_id": f"sam-byte-{_slug(aid)}-{str(receipt['sha256'])[:12]}",
        "url": receipt.get("source_url"),
        "authority": "SUPPORTING",
        "artifact_state": "PUBLIC",
        "observed_at": receipt.get("observed_at"),
        "content_sha256": receipt.get("sha256"),
        "source_contract": receipt.get("source_contract"),
        "automation_mode": "APPROVED_API",
    })
    return out


def apply_approved_evidence(
    case: dict[str, Any],
    *,
    history_receipt: dict[str, Any] | None = None,
    current_receipt: dict[str, Any] | None = None,
    api_observation: dict[str, Any] | None = None,
    byte_receipts: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    out = copy.deepcopy(case)
    if history_receipt is not None:
        out = apply_history_receipt(out, history_receipt)
    if (current_receipt is None) != (api_observation is None):
        raise EvidenceApplyError(
            "current_receipt and api_observation must be supplied together"
        )
    if current_receipt is not None and api_observation is not None:
        out = apply_current_api_evidence(out, current_receipt, api_observation)
    for receipt in byte_receipts:
        out = apply_byte_receipt(out, receipt)
    return out
