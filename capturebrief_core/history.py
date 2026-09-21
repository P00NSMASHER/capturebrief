from __future__ import annotations

from typing import Any, Iterable

from .model import Finding, canonical_json, first_party_sam, history_set_digest, parse_dt, sha256_hex, valid_sha256
from .source_policy import classify_sam_url

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


def _validate_data_services_contract(receipt: dict[str, Any], receipt_actions: set[str], path: str) -> list[Finding]:
    findings: list[Finding] = []
    payload = receipt.get("evidence_payload")
    if not isinstance(payload, dict):
        return [Finding("HISTORY_DATA_SERVICES_PAYLOAD_MISSING", "BLOCK", "Data Services receipt lacks a structured evidence payload.", path)]

    if receipt.get("automation_mode") != "APPROVED_EXTRACT":
        findings.append(Finding("HISTORY_DATA_SERVICES_AUTOMATION_MODE_INVALID", "BLOCK", "Data Services receipt is not marked as approved extract automation.", path))
    if payload.get("source_contract") != "SAM_DATA_SERVICES_EXTRACT":
        findings.append(Finding("HISTORY_DATA_SERVICES_SOURCE_CONTRACT_INVALID", "BLOCK", "Data Services receipt source contract is invalid.", path))
    if payload.get("ordering_authoritative") is not False:
        findings.append(Finding("HISTORY_DATA_SERVICES_ORDERING_MUST_NOT_BE_AUTHORITATIVE", "BLOCK", "Data Services membership must not claim authoritative ordering.", path))
    if payload.get("current_action_authoritative") is not False:
        findings.append(Finding("HISTORY_DATA_SERVICES_CURRENTNESS_MUST_NOT_BE_AUTHORITATIVE", "BLOCK", "Data Services membership must not claim authoritative currentness.", path))

    actions = payload.get("actions")
    if not isinstance(actions, list):
        findings.append(Finding("HISTORY_DATA_SERVICES_ACTIONS_MISSING", "BLOCK", "Data Services payload does not retain action observations.", path))
    else:
        payload_ids: set[str] = set()
        for j, action in enumerate(actions):
            apath = f"{path}.evidence_payload.actions[{j}]"
            if not isinstance(action, dict):
                findings.append(Finding("HISTORY_DATA_SERVICES_ACTION_INVALID", "BLOCK", "Data Services action observation is not an object.", apath)); continue
            notice_id = str(action.get("notice_id", ""))
            if not notice_id:
                findings.append(Finding("HISTORY_DATA_SERVICES_NOTICE_ID_MISSING", "BLOCK", "Data Services action observation lacks Notice ID.", apath)); continue
            payload_ids.add(notice_id)
            observations = action.get("observations")
            if not isinstance(observations, list) or not observations:
                findings.append(Finding("HISTORY_DATA_SERVICES_OBSERVATION_MISSING", "BLOCK", "Data Services action has no retained row observation.", apath)); continue
            for k, observation in enumerate(observations):
                opath = f"{apath}.observations[{k}]"
                if not isinstance(observation, dict) or not valid_sha256(observation.get("row_sha256")):
                    findings.append(Finding("HISTORY_DATA_SERVICES_ROW_HASH_INVALID", "BLOCK", "Data Services row observation lacks a valid row SHA-256.", opath))
        if payload_ids != receipt_actions:
            findings.append(Finding("HISTORY_DATA_SERVICES_ACTION_SET_MISMATCH", "BLOCK", "Data Services payload action IDs differ from the receipt action set.", path))

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        findings.append(Finding("HISTORY_DATA_SERVICES_SCOPE_MISSING", "BLOCK", "Data Services receipt lacks explicit archive scope.", path))
    else:
        start, end = scope.get("start_fy"), scope.get("end_fy")
        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            findings.append(Finding("HISTORY_DATA_SERVICES_SCOPE_RANGE_INVALID", "BLOCK", "Data Services scope fiscal-year range is invalid.", path))
            expected_required: set[int] = set()
        else:
            expected_required = set(range(start, end + 1))
        required = {int(x) for x in scope.get("required_archive_fys", []) if isinstance(x, int)}
        supplied = {int(x) for x in scope.get("supplied_archive_fys", []) if isinstance(x, int)}
        missing = {int(x) for x in scope.get("missing_archive_fys", []) if isinstance(x, int)}
        if scope.get("scope_confirmed") is not True:
            findings.append(Finding("HISTORY_DATA_SERVICES_SCOPE_UNCONFIRMED", "BLOCK", "Data Services scope was not explicitly confirmed.", path))
        if required != expected_required:
            findings.append(Finding("HISTORY_DATA_SERVICES_REQUIRED_RANGE_MISMATCH", "BLOCK", "Required archive years do not match the declared scope range.", path))
        if missing or not required.issubset(supplied):
            findings.append(Finding("HISTORY_DATA_SERVICES_ARCHIVE_COVERAGE_INCOMPLETE", "BLOCK", "Not every required Data Services archive year is supplied.", path))
        if scope.get("active_extract_present") is not True:
            findings.append(Finding("HISTORY_DATA_SERVICES_ACTIVE_EXTRACT_MISSING", "BLOCK", "Complete Data Services receipt lacks the active extract.", path))

    snapshots = payload.get("source_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOTS_MISSING", "BLOCK", "Data Services receipt lacks source snapshot evidence.", path))
    else:
        active_count = 0
        archive_years: set[int] = set()
        for j, snapshot in enumerate(snapshots):
            spath = f"{path}.evidence_payload.source_snapshots[{j}]"
            if not isinstance(snapshot, dict):
                findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOT_INVALID", "BLOCK", "Data Services snapshot is not an object.", spath)); continue
            if classify_sam_url(str(snapshot.get("source_url", ""))) != "SAM_DATA_SERVICES_EXTRACT":
                findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOT_SOURCE_INVALID", "BLOCK", "Data Services snapshot source is not an approved extract URL.", spath))
            if not valid_sha256(snapshot.get("extract_sha256")):
                findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOT_HASH_INVALID", "BLOCK", "Data Services snapshot lacks a valid extract SHA-256.", spath))
            kind = str(snapshot.get("source_kind", "")).upper()
            if kind == "ACTIVE":
                active_count += 1
            elif kind == "ARCHIVE" and isinstance(snapshot.get("fiscal_year"), int):
                archive_years.add(int(snapshot["fiscal_year"]))
            else:
                findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOT_KIND_INVALID", "BLOCK", "Data Services snapshot kind/fiscal year is invalid.", spath))
        if active_count < 1:
            findings.append(Finding("HISTORY_DATA_SERVICES_ACTIVE_SNAPSHOT_MISSING", "BLOCK", "Data Services receipt retains no active extract snapshot.", path))
        if isinstance(scope, dict):
            required = {int(x) for x in scope.get("required_archive_fys", []) if isinstance(x, int)}
            if not required.issubset(archive_years):
                findings.append(Finding("HISTORY_DATA_SERVICES_SNAPSHOT_ARCHIVES_INCOMPLETE", "BLOCK", "Retained source snapshots do not cover every required archive year.", path))

    family = payload.get("family")
    if not isinstance(family, dict) or not str(family.get("solicitation_number") or "").strip():
        findings.append(Finding("HISTORY_DATA_SERVICES_FAMILY_INVALID", "BLOCK", "Data Services receipt lacks a solicitation-family identity.", path))
    else:
        seed = str(family.get("seed_notice_id") or "")
        if seed and seed not in receipt_actions:
            findings.append(Finding("HISTORY_DATA_SERVICES_SEED_OUTSIDE_SET", "BLOCK", "Data Services seed notice ID is outside the retained action set.", path))

    return findings


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
        if surface == "SAM_DATA_SERVICES":
            ds_findings = _validate_data_services_contract(receipt, receipt_actions, path)
            findings.extend(ds_findings)
            if any(x.severity == "BLOCK" for x in ds_findings):
                continue
        accepted.add((surface, expected_digest))

    verdict = "HISTORY_COMPLETE" if accepted and not any(x.severity == "BLOCK" for x in findings) else "HISTORY_UNRESOLVED"
    return verdict, findings
