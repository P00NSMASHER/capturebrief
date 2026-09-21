from __future__ import annotations

import copy
from typing import Any, Callable

from .case_artifacts import CaseArtifactError, apply_api_byte_receipt
from .current_api import (
    SEARCH_URL,
    CurrentApiError,
    download_resource_from_api_observation,
    validate_api_observation,
)
from .model import valid_sha256


class CaseCaptureError(RuntimeError):
    pass


def _retained_api_observation(case: dict[str, Any]) -> dict[str, Any]:
    packet = case.get("packet") or {}
    current = packet.get("current_api_observation") or {}
    if current.get("source_contract") != "SAM_GET_OPPORTUNITIES_V2":
        raise CaseCaptureError("case does not retain a documented current API observation")
    digest = current.get("api_payload_sha256")
    response_digest = current.get("api_response_sha256")
    if not valid_sha256(digest):
        raise CaseCaptureError("case current API observation lacks a valid payload digest")
    if not valid_sha256(response_digest):
        raise CaseCaptureError(
            "case current API observation predates raw-response proof; refresh current authority before capture"
        )
    links = [str(x) for x in packet.get("current_resource_links") or [] if str(x)]
    if int(current.get("resource_link_count") or 0) != len(links):
        raise CaseCaptureError("case current resource-link count disagrees with retained links")
    observation = {
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
        "source_url": SEARCH_URL,
        "observed_at": current.get("observed_at"),
        "payload_sha256": digest,
        "response_sha256": response_digest,
        "pagination": copy.deepcopy(current.get("pagination")),
        "resource_links": links,
        "record": {
            "noticeId": current.get("notice_id"),
            "solicitationNumber": current.get("solicitation_number"),
        },
    }
    try:
        validate_api_observation(observation)
    except CurrentApiError as exc:
        raise CaseCaptureError(f"retained current API observation is incomplete: {exc}") from exc
    return observation


def capture_current_artifact(
    case: dict[str, Any],
    artifact_id: str,
    *,
    max_bytes: int = 50 * 1024 * 1024,
    timeout: float = 30.0,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], bytes | None]:
    """Download and apply one approved current resource directly from retained case evidence."""
    result = copy.deepcopy(case)
    packet = result.get("packet") or {}
    artifact_id = str(artifact_id or "")
    matches = [
        item for item in packet.get("artifacts") or []
        if str(item.get("artifact_id")) == artifact_id
    ]
    if len(matches) != 1:
        raise CaseCaptureError("artifact_id must identify exactly one case artifact")
    artifact = matches[0]
    if artifact.get("source_object_state") != "VERIFIED_SOURCE_OBJECT":
        raise CaseCaptureError("artifact source object is not verified")
    if artifact.get("state") != "PUBLIC":
        raise CaseCaptureError("only public current artifacts may use approved automated capture")
    resource_url = str(artifact.get("resource_url") or "")
    if not resource_url:
        raise CaseCaptureError("artifact has no retained current API resource URL")

    if artifact.get("byte_state") == "BYTES_VERIFIED_HASHED" and valid_sha256(artifact.get("sha256")):
        return result, {
            "status": "ARTIFACT_ALREADY_CAPTURED",
            "artifact_id": artifact_id,
            "sha256": artifact.get("sha256"),
        }, None

    observation = _retained_api_observation(result)
    if resource_url not in observation["resource_links"]:
        raise CaseCaptureError("artifact URL is not present in the retained current API resource-link set")

    kwargs: dict[str, Any] = {
        "max_bytes": max_bytes,
        "timeout": timeout,
    }
    if opener is not None:
        kwargs["opener"] = opener
    try:
        receipt, content = download_resource_from_api_observation(
            observation,
            resource_url,
            **kwargs,
        )
        updated, applied = apply_api_byte_receipt(result, receipt)
    except (CurrentApiError, CaseArtifactError, ValueError) as exc:
        raise CaseCaptureError(str(exc)) from exc

    transition = {
        "status": "CURRENT_ARTIFACT_CAPTURED",
        "artifact_id": artifact_id,
        "sha256": receipt["sha256"],
        "size": receipt["size"],
        "byte_receipt_sha256": applied["receipt_sha256"],
        "source_contract": receipt["source_contract"],
    }
    return updated, transition, content
