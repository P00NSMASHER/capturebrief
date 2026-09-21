from __future__ import annotations

from typing import Any, Iterable

from .model import Finding, canonical_json, first_party_sam, history_set_digest, parse_dt, sha256_hex, valid_sha256

HISTORY_SURFACES = {"SAM_HISTORY", "SAM_DATA_SERVICES"}


def make_history_receipt(
    action_ids: Iterable[str],
    *,
    source_url: str,
    observed_at: str,
    source_surface: str,
    payload: Any,
) -> dict[str, Any]:
    actions = [str(x) for x in action_ids if str(x)]
    surface = str(source_surface).upper()
    if surface not in HISTORY_SURFACES:
        raise ValueError("unsupported history source surface")
    if not first_party_sam(source_url):
        raise ValueError("history source must be first-party sam.gov HTTPS")
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    return {
        "source_surface": surface,
        "source_url": source_url,
        "observed_at": observed_at,
        "status": "COMPLETE",
        "action_ids": actions,
        "history_set_sha256": history_set_digest(actions),
        "evidence_payload_sha256": sha256_hex(canonical_json(payload)),
        "evidence_payload": payload,
    }


def _payload_verified(receipt: dict[str, Any]) -> bool:
    digest = receipt.get("evidence_payload_sha256")
    if not valid_sha256(digest):
        return False
    if receipt.get("evidence_payload") is not None:
        return sha256_hex(canonical_json(receipt["evidence_payload"])) == digest
    return receipt.get("payload_hash_verified") is True


def validate_history_receipts(
    history_action_ids: Iterable[str],
    receipts: Iterable[dict[str, Any]],
) -> tuple[str, list[Finding]]:
    findings: list[Finding] = []
    history = {str(x) for x in history_action_ids if str(x)}
    expected_digest = history_set_digest(history)
    accepted: set[tuple[str, str]] = set()

    if not history:
        findings.append(Finding("HISTORY_SET_EMPTY", "BLOCK", "Observed action history is empty."))

    for i, receipt in enumerate(receipts):
        path = f"packet.history_receipts[{i}]"
        surface = str(receipt.get("source_surface", "")).upper()
        if surface not in HISTORY_SURFACES:
            findings.append(Finding("HISTORY_RECEIPT_SURFACE_INVALID", "BLOCK", "History receipt source surface is not accepted.", path)); continue
        if not first_party_sam(receipt.get("source_url")):
            findings.append(Finding("HISTORY_RECEIPT_NOT_FIRST_PARTY", "BLOCK", "History receipt source is not first-party sam.gov HTTPS.", path)); continue
        if not parse_dt(receipt.get("observed_at")):
            findings.append(Finding("HISTORY_RECEIPT_TIME_INVALID", "BLOCK", "History receipt lacks a timezone-aware observation timestamp.", path)); continue
        if receipt.get("status") != "COMPLETE":
            findings.append(Finding("HISTORY_RECEIPT_NOT_COMPLETE", "BLOCK", "History receipt is not marked complete.", path)); continue
        if not _payload_verified(receipt):
            findings.append(Finding("HISTORY_RECEIPT_PAYLOAD_UNVERIFIED", "BLOCK", "History receipt payload hash is missing or unverified.", path)); continue
        receipt_actions = {str(x) for x in receipt.get("action_ids", []) if str(x)}
        if receipt_actions != history or receipt.get("history_set_sha256") != expected_digest:
            findings.append(Finding("HISTORY_RECEIPT_SET_MISMATCH", "BLOCK", "History receipt action set does not match the case action set.", path)); continue
        accepted.add((surface, expected_digest))

    verdict = "HISTORY_COMPLETE" if accepted and not any(x.severity == "BLOCK" for x in findings) else "HISTORY_UNRESOLVED"
    return verdict, findings
