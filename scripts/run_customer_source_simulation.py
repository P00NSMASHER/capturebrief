"""TEST-only customer review on exact, privately indexed public SAM inputs.

No network, email, payment, live customer registry, source approval or LIVE
deliverable. Original sources stay private. Output cases explicitly carry
decision_trace.synthetic=true and must be refused by the actual release gate.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.atomic_io import ensure_exact_bytes
from capturebrief_core.data_services import issue_history_receipt_from_snapshots
from capturebrief_core.decision_trace import evaluate_decision_trace, freeze_text_snapshot, passage
from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from capturebrief_core.free_trial import build_free_check_report, inspect_free_check, reserve_free_check
from capturebrief_core.history_index import ACTIVE_MAX_AGE, ARCHIVE_MAX_AGE, APPROVED_FETCH, OPERATOR_FILE, _encoding
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.render import render_markdown
from capturebrief_core.request_draft import TO_LINE, FREE_SUBJECT, FREE_CLAIM, HEADER, CONFIRMATION, FREE_END
from scripts.audit_original_index_projection import audit_row_projection
from scripts.import_request_draft import import_request
from scripts.refresh_sam_source_candidate import MARKER, _bytes
from scripts.retain_compressed_sam_archive_candidate import _private_dir

SAFE_FIELDS = ("NoticeId", "Title", "Sol#", "PostedDate", "Type", "Active", "ResponseDeadLine")
TECH_WORDS = ("software", "cyber", "cloud", "network", "information technology")
DISCLAIMER = "SIMULATION ONLY — fictional customer and reviewer; real extract facts do not establish current-action authority."


def _source(candidate, slot, now):
    index = candidate / "candidate-source-index.sqlite"
    audit = audit_row_projection(index, slot=slot, snapshot_root=candidate / "originals")
    with closing(sqlite3.connect(index.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute("SELECT s.*,c.checked_at,c.collection_mode AS current_collection_mode FROM source_snapshots s JOIN current_sources c ON s.snapshot_id=c.snapshot_id WHERE c.slot=?", (slot,)).fetchone())
    receipts = []
    for path in (candidate / "observations").glob(slot.replace(":", "-") + "-*.json"):
        item = json.loads(path.read_text())
        if (item.get("source_sha256") == row["extract_sha256"]
                and item.get("observed_at") == row["checked_at"]):
            receipts.append(item)
    if len(receipts) != 1:
        raise ValueError("Need one exact current candidate transport observation")
    receipt = receipts[0]
    checked_at = datetime.fromisoformat(row["checked_at"].replace("Z", "+00:00"))
    maximum_age = ACTIVE_MAX_AGE if slot == "ACTIVE" else ARCHIVE_MAX_AGE
    if checked_at.utcoffset() is None or checked_at > now or now - checked_at > maximum_age:
        raise ValueError("Candidate source observation is stale or in the future")
    if (receipt.get("source_url") != row["source_url"]
            or receipt.get("source_bytes") != row["size_bytes"]
            or receipt.get("rows_indexed") != row["rows_scanned"]
            or type(receipt.get("synthetic_transport")) is not bool
            or row["current_collection_mode"] != (OPERATOR_FILE if receipt.get("synthetic_transport") else APPROVED_FETCH)
            or receipt.get("catalog_approved") is not False
            or receipt.get("production_index_updated") is not False):
        raise ValueError("Candidate source observation does not match the exact original")
    return row, receipt, audit


def _select(source, now, count):
    chosen = []
    with Path(source["local_path"]).open(encoding=_encoding(Path(source["local_path"])), newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), 1):
            if not re.fullmatch(r"[a-fA-F0-9]{32}", row.get("NoticeId", "")) or not row.get("Sol#"):
                continue
            if not any(word in row.get("Title", "").lower() for word in TECH_WORDS):
                continue
            if source["slot"] == "ACTIVE":
                try:
                    deadline = datetime.fromisoformat(row.get("ResponseDeadLine", "").replace("Z", "+00:00"))
                    if deadline.utcoffset() is None or deadline <= now:
                        continue
                except ValueError:
                    continue
                if row.get("Active") != "Yes" or "Solicitation" not in row.get("Type", ""):
                    continue
            chosen.append({"number": number, "fields": {key: row.get(key, "") for key in SAFE_FIELDS},
                           "row_sha256": sha256_hex(canonical_json(row)),
                           "aac_code": row.get("AAC Code", ""), "office": row.get("Office", "")})
            if len(chosen) == count:
                break
    if len(chosen) != count:
        raise ValueError("Current source lacks enough qualifying public technology notices")
    return chosen


def _draft(number, url, question):
    return (f"{TO_LINE}\nSubject: {FREE_SUBJECT}\n\n{HEADER}\n\n"
            f"Purchase status (customer-reported, not verified): {FREE_CLAIM}\n"
            f"Company: SIMULATED Federal IT Buyer {number}\nWork email: buyer-{number}@example.invalid\n"
            f"Public opportunity link: {url}\nCurrent posture: HOLD\n\n"
            f"Assumptions to check:\n1. {question}\n\n{CONFIRMATION}\n\n{FREE_END}")


def _case(root, number, source, selected, now):
    fields = selected["fields"]
    url = f"https://sam.gov/opp/{fields['NoticeId'].lower()}/view"
    question = (f"The current response deadline is {fields['ResponseDeadLine']}."
                if source["slot"] == "ACTIVE" else
                "This archived notice is the newest active action for this solicitation.")
    text = _draft(number, url, question)
    request_hash = hashlib.sha256(text.encode()).hexdigest()
    folder = root / f"SIM-{number:02d}"
    folder.mkdir(mode=0o700)
    request = folder / "SIMULATED-request.txt"
    request.write_text(text, encoding="utf-8")
    case_path, receipt_path = folder / "case.json", folder / "intake-receipt.json"
    import_request(str(request), str(case_path), str(receipt_path), imported_at=now)
    case, receipt = json.loads(case_path.read_text()), json.loads(receipt_path.read_text())
    identity = {"simulated": True, "business": f"SIM-BUSINESS-{number}",
                "actual_identity_review_performed": False}
    ensure_exact_bytes(folder / "SIMULATED-identity-review.json", _bytes(identity), mode=0o600)
    registry = root / "SIMULATION-ONLY-trials.sqlite"
    business = f"domain:simulated-{number}.example.invalid"
    reservation = reserve_free_check(registry, case=case, receipt=receipt,
                                    reviewed_business_key=business,
                                    identity_review_sha256=sha256_hex(canonical_json(identity)), observed_at=now)
    retry = reserve_free_check(registry, case=case, receipt=receipt,
                              reviewed_business_key=business,
                              identity_review_sha256=sha256_hex(canonical_json(identity)), observed_at=now)
    assert retry["status"] == "ALREADY_RESERVED_REVIEW_REQUIRED"
    assert reservation["amount_due_cents"] == 0
    finding = (f"The retained {source['slot']} CSV records ResponseDeadLine as {fields['ResponseDeadLine']}. "
               "It does not establish that this is the latest controlling deadline; no current API/action or complete amendment packet was verified."
               if source["slot"] == "ACTIVE" else
               "The notice is present in the retained FY2027 archive. Archive membership cannot establish the newest active action.")
    next_action = "Before relying on this answer, verify the current SAM API action, inspect all controlling amendments and attachments, and have the source packet reviewed."
    aid = case["assumptions"][0]["assumption_id"]
    source_id = f"SIM-SOURCE-{number}"
    evidence = {
        "source_id": source_id, "title": f"Official SAM {source['slot']} extract — selected row {selected['number']}",
        "url": source["source_url"], "authority": "SUPPORTING", "artifact_state": "PUBLIC",
        "observed_at": source["checked_at"], "content_sha256": source["extract_sha256"],
    }
    normalized = "\n".join(f"{key}: {fields[key]}" for key in SAFE_FIELDS)
    snapshot = freeze_text_snapshot(source=evidence, source_key=fields["NoticeId"], kind="CONTEXT",
        version_label=f"{source['slot']} observed {source['checked_at']}", text=normalized,
        capture_method="NATIVE_TEXT", captured_by="SIMULATED reviewer — automated test",
        mapping_note=f"Selected CSV fields only; original row {selected['number']} SHA256 {selected['row_sha256']}. No human review.")
    cite = {**passage(snapshot, 1, len(SAFE_FIELDS), locator=f"CSV data row {selected['number']}; selected named fields"), "role": "CONTEXT"}
    case["sources"] = [evidence]
    case["assumptions"][0].update({"evidence_state": "SOURCE_LIMITED", "decision_class": "VERIFY_NOW",
        "finding": finding, "source_ids": [source_id], "next_action": next_action,
        "owner": "SIMULATED proposal manager", "reopen_triggers": ["CURRENT_ACTION_CHANGE"]})
    match = {"notice_id": fields["NoticeId"], "solicitation_number": fields["Sol#"],
             "posted_date": fields["PostedDate"], "notice_type": fields["Type"], "active": fields["Active"],
             "aac_code": selected["aac_code"], "office": selected["office"], "link": url,
             "row_sha256": selected["row_sha256"]}
    history = issue_history_receipt_from_snapshots([{
        "source_kind": source["source_kind"], "fiscal_year": source["fiscal_year"],
        "source_url": source["source_url"], "extract_sha256": source["extract_sha256"],
        "rows_scanned": source["rows_scanned"], "matches": [match],
    }], solicitation_number=fields["Sol#"], observed_at=source["checked_at"], seed_notice_id=fields["NoticeId"])
    assert history["status"] == "OBSERVED_ONLY"
    case["packet"]["history_action_ids"] = history["action_ids"]
    case["packet"]["history_receipts"] = [history]
    case["decision_trace_required"] = True
    case["decision_trace"] = {"schema_version": "1.0", "synthetic": True, "family_id": case["family_id"],
        "decision_at": now.isoformat(), "snapshots": [snapshot], "rule_versions": [], "reviews": [{
            "assumption_id": aid, "evidence_state": "SOURCE_LIMITED", "finding": finding,
            "citations": [cite], "rule_scope": {"status": "NOT_RELEVANT", "rationale": "This test asks what metadata proves, not legal applicability."},
            "rule_links": [], "changes": [], "evidence_request": next_action,
            "reviewed_by": "SIMULATED reviewer; not human approval", "reviewed_at": now.isoformat(),
        }]}
    trace = evaluate_decision_trace(case, now=now, allow_synthetic=True)
    assert trace["trace_state"] == "ILLUSTRATIVE_TRACE_COMPLETE", trace["findings"]
    readiness = evaluate_delivery_readiness(case, now=now)
    assert "DELIVERY_SYNTHETIC_EVIDENCE" in readiness.blocker_codes and not readiness.eligible
    gate = inspect_free_check(case, database_path=registry, now=now)
    assert gate["reservation_scope_matches"] is True and gate["state"] == "BLOCKED_BY_CORE_EVIDENCE"
    forbidden = folder / "MUST-NOT-EXIST-live-report.md"
    try:
        build_free_check_report(case, forbidden, database_path=registry, now=now)
    except ValueError:
        pass
    else:
        raise AssertionError("Simulation was accepted by the LIVE free-report builder")
    assert not forbidden.exists()
    tampered = copy.deepcopy(case)
    tampered["decision_trace"]["reviews"][0]["citations"][0]["quote"] += " fabricated"
    changed_trace = evaluate_decision_trace(tampered, now=now, allow_synthetic=True)
    assert any(x["code"] == "TRACE_QUOTE_MISMATCH" for x in changed_trace["findings"])
    preview = (f"# SIMULATION ONLY — free-check customer preview {number}\n\n{DISCLAIMER}\n\n"
               f"## Public input\n\n**{fields['Title']}**  \n{url}\n\n"
               f"## Your question\n\n{question}\n\n## Bounded answer\n\n{finding}\n\n"
               f"## Next action\n\n{next_action}\n\n"
               "## Free and paid scope\n\nOne free assumption check per business. No card, charge, automatic upgrade, or included change watch. "
               "A separate explicit $149 purchase covers up to five assumptions and a 14-day targeted watch. "
               "This TEST preview has not completed source acceptance and is not a customer deliverable.\n\n"
               "## Technical evidence and unresolved checks\n\n" + render_markdown(case, now=now))
    ensure_exact_bytes(folder / "SIMULATED-preview.md", preview.encode(), mode=0o600)
    ensure_exact_bytes(folder / "SIMULATED-reviewed-case.json", _bytes(case), mode=0o600)
    feedback = {
        "simulated": True, "real_customer": False, "customer_satisfaction_measured": False,
        "personas": [
            {"role": "Small federal-IT bidder", "review": {
                "factual_accuracy_and_trace": "PASS: quoted fields match retained original row and exact hashes; no currentness inference.",
                "answered_question": ("OPEN: the recorded date is explained, but a controlling current deadline is not established."
                                      if source["slot"] == "ACTIVE" else
                                      "OPEN: archive membership is explained, but the newest active action is not established."),
                "next_action": "PASS: current API action and controlling amendments are named as the next evidence needed.",
                "free_paid_scope": "PASS: one free question, no card or automatic charge; optional $149 review/watch is separate.",
            }},
            {"role": "Proposal manager", "review": {
                "citation_trace": "PASS: original extract SHA256, selected row SHA256 and named-field locator are retained.",
                "currentness_disclosure": "PASS: ACTIVE/ARCHIVE membership is explicitly separated from latest-action authority.",
                "delivery_readiness": "OPEN: the team cannot treat this preview as cleared for a bid decision or customer delivery.",
                "clarity": "PASS for the opening answer; technical blocker appendix is for operator review and is longer than a final customer handoff.",
            }},
        ],
        "acceptance": "SIMULATED_REVIEW_REQUIRES_SOURCE_COMPLETION",
        "simulated_delivery": {"artifact_created": True, "preview_sha256": hashlib.sha256(preview.encode()).hexdigest(),
                               "provider_delivery_verified": False, "external_send_authorized": False},
        "production_builder_rejected": True, "customer_release_authorized": False,
    }
    ensure_exact_bytes(folder / "SIMULATED-customer-feedback.json", _bytes(feedback), mode=0o600)
    return {"scenario": f"SIM-{number:02d}", "source_slot": source["slot"], "source_original_sha256": source["extract_sha256"],
            "selected_row_sha256": selected["row_sha256"], "source_rows_independently_checked": source["rows_scanned"],
            "synthetic_case": True, "illustrative_trace_complete": True, "trial_retry_idempotent": True,
            "reservation_scope_matches": True, "quote_mutation_rejected": True,
            "production_builder_rejected": True, "production_blocker_codes": list(readiness.blocker_codes),
            "preview_sha256": feedback["simulated_delivery"]["preview_sha256"],
            "simulated_customer_acceptance": feedback["acceptance"], "customer_release_authorized": False}


def run(candidate_dir, output_dir, *, now=None):
    candidate = Path(candidate_dir).resolve(strict=True)
    if json.loads((candidate / "CANDIDATE-ONLY.json").read_text()) != MARKER:
        raise ValueError("A marked unapproved candidate source workspace is required")
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Simulation clock must include timezone")
    root = _private_dir(output_dir)
    if any(root.iterdir()) or root == candidate or root.is_relative_to(candidate):
        raise ValueError("Simulation output requires a separate empty private workspace")
    ensure_exact_bytes(root / "SIMULATION-ONLY.json", _bytes({"simulated": True, "live_customer_state": False}), mode=0o600)
    results, sources = [], []
    for slot, count in (("ACTIVE", 2), ("ARCHIVE:2027", 1)):
        source, receipt, audit = _source(candidate, slot, now)
        sources.append({"slot": slot, "original_sha256": source["extract_sha256"],
                        "original_bytes": source["size_bytes"], "rows_checked": audit["rows_checked"],
                        "synthetic_transport": receipt["synthetic_transport"]})
        for selected in _select(source, now, count):
            results.append(_case(root, len(results) + 1, source, selected, now))
    report = {"schema": "capturebrief-customer-source-simulation-v1", "simulated": True,
              "checked_at": now.isoformat(), "passed": True, "source_observations": sources,
              "real_public_transport_used": all(x["synthetic_transport"] is False for x in sources),
              "sources_independently_human_approved": False,
              "scenario_count": len(results), "customer_reviews_are_simulated": True,
              "not_customer_satisfaction_or_conversion_evidence": True, "results": results,
              "catalog_approved": False, "customer_delivery_verified": False,
              "customer_release_authorized": False, "external_messages_sent": 0,
              "payments_created": 0, "live_registry_updated": False}
    ensure_exact_bytes(root / "simulation-report.json", _bytes(report), mode=0o600)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.candidate_dir, args.output_dir)
    except Exception as error:
        print(json.dumps({"status": "SIMULATION_BLOCKED", "error_type": type(error).__name__,
                          "simulated": True, "customer_release_authorized": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
