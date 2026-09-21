from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlparse

from .authority import validate_current_action_receipts
from .current_api import make_current_action_receipt
from .history import validate_history_receipts
from .model import parse_dt
from .source_policy import classify_sam_url


class CaseCurrentError(RuntimeError):
    pass


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def _history_solicitation_numbers(case: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for receipt in (case.get("packet") or {}).get("history_receipts") or []:
        family = (receipt.get("evidence_payload") or {}).get("family") or {}
        value = _norm(family.get("solicitation_number"))
        if value:
            out.add(value)
    return out


def _resource_id(resource_url: str) -> str:
    if classify_sam_url(resource_url) != "SAM_API_RESOURCE_LINK":
        raise CaseCurrentError("current API observation contains a non-approved resource link")
    path = urlparse(resource_url).path
    parts = [part for part in path.split("/") if part]
    try:
        idx = parts.index("files")
        resource_id = parts[idx + 1]
    except (ValueError, IndexError) as exc:
        raise CaseCurrentError("approved resource link does not expose a resource ID") from exc
    if not resource_id:
        raise CaseCurrentError("approved resource link has an empty resource ID")
    return resource_id


def apply_current_api_observation(
    case: dict[str, Any],
    api_observation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a documented latest-active SAM API observation to a history-resolved case.

    This transition is intentionally strict: history must already be complete, the API Notice ID
    must belong to that history set, and the API solicitation family must agree with retained
    history evidence. Customer assumptions are never linked or marked supported by this step.
    """
    result = copy.deepcopy(case)
    packet = result.setdefault("packet", {})
    history_ids = [str(x) for x in packet.get("history_action_ids") or []]
    history_verdict, history_findings = validate_history_receipts(
        history_ids,
        packet.get("history_receipts") or [],
    )
    if history_verdict != "HISTORY_COMPLETE":
        codes = sorted({f.code for f in history_findings})
        raise CaseCurrentError(f"current API evidence cannot be applied before complete history: {codes}")

    if api_observation.get("source_contract") != "SAM_GET_OPPORTUNITIES_V2":
        raise CaseCurrentError("API observation source contract is not SAM_GET_OPPORTUNITIES_V2")
    if api_observation.get("automation_mode") != "APPROVED_API":
        raise CaseCurrentError("API observation is not marked APPROVED_API")

    record = api_observation.get("record") or {}
    api_sol = _norm(record.get("solicitationNumber"))
    if not api_sol:
        raise CaseCurrentError("API observation lacks solicitationNumber")
    history_sols = _history_solicitation_numbers(result)
    if history_sols and api_sol not in history_sols:
        raise CaseCurrentError(
            f"API solicitation family {api_sol} disagrees with history family {sorted(history_sols)}"
        )
    active = str(record.get("active") if record.get("active") is not None else "").strip().lower()
    if active in {"no", "false", "0"}:
        raise CaseCurrentError("latest-active API observation explicitly reports the record inactive")

    receipt = make_current_action_receipt(
        api_observation,
        history_action_ids=history_ids,
    )
    observed = parse_dt(receipt.get("observed_at"))
    if not observed:
        raise CaseCurrentError("current receipt observation time is invalid")

    verdict, action_id, findings = validate_current_action_receipts(
        history_ids,
        "ACTIVE",
        [receipt],
        now=observed,
    )
    if verdict != "CURRENT_VERIFIED" or not action_id:
        codes = sorted({f.code for f in findings})
        raise CaseCurrentError(f"approved current-action receipt failed validation: {codes}")

    links = [str(link) for link in api_observation.get("resource_links") or []]
    resources = [(_resource_id(link), link) for link in links]

    packet["family_status"] = "ACTIVE"
    packet["current_action_id"] = action_id
    packet["current_api_observation"] = {
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "notice_id": action_id,
        "solicitation_number": record.get("solicitationNumber"),
        "observed_at": api_observation.get("observed_at"),
        "api_payload_sha256": api_observation.get("payload_sha256"),
        "resource_link_count": len(resources),
    }
    packet["current_resource_links"] = links

    current_receipts = list(result.get("current_action_receipts") or [])
    receipt_digest = receipt.get("evidence_payload_sha256")
    if not any(r.get("evidence_payload_sha256") == receipt_digest for r in current_receipts):
        current_receipts.append(receipt)
    result["current_action_receipts"] = current_receipts

    source = {
        "source_id": "sam-current-api",
        "url": api_observation.get("source_url"),
        "authority": "CONTROLLING_CURRENT",
        "artifact_state": "PUBLIC",
        "observed_at": api_observation.get("observed_at"),
        "content_sha256": api_observation.get("payload_sha256"),
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
    }
    sources = list(result.get("sources") or [])
    replaced = False
    for idx, existing in enumerate(sources):
        if existing.get("source_id") == source["source_id"]:
            sources[idx] = source
            replaced = True
            break
    if not replaced:
        sources.append(source)
    result["sources"] = sources

    artifacts = list(packet.get("artifacts") or [])
    by_id = {str(item.get("artifact_id")): idx for idx, item in enumerate(artifacts) if item.get("artifact_id")}
    for resource_id, link in resources:
        discovered = {
            "artifact_id": resource_id,
            "name": f"SAM current resource {resource_id}",
            "state": "PUBLIC",
            "required_for_analysis": False,
            "sha256": None,
            "byte_state": "BYTES_NOT_YET_CHECKED",
            "source_object_state": "VERIFIED_SOURCE_OBJECT",
            "resource_url": link,
            "source_action_id": action_id,
            "source_ids": ["sam-current-api"],
            "discovered_via": "SAM_GET_OPPORTUNITIES_V2",
        }
        if resource_id in by_id:
            existing = artifacts[by_id[resource_id]]
            merged = {**discovered, **existing}
            merged["resource_url"] = link
            merged["source_action_id"] = action_id
            existing_sources = list(existing.get("source_ids") or [])
            if "sam-current-api" not in existing_sources:
                existing_sources.append("sam-current-api")
            merged["source_ids"] = existing_sources
            artifacts[by_id[resource_id]] = merged
        else:
            by_id[resource_id] = len(artifacts)
            artifacts.append(discovered)
    packet["artifacts"] = artifacts

    transition = {
        "status": "CURRENT_VERIFIED",
        "current_action_id": action_id,
        "solicitation_number": record.get("solicitationNumber"),
        "resource_ids": [rid for rid, _ in resources],
        "resource_links": links,
        "receipt": receipt,
    }
    return result, transition
