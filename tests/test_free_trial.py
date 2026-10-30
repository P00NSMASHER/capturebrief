"""Meaningful free-trial boundaries: intake, entitlement, cost, privacy, release."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from capturebrief_core.free_trial import (
    MAX_COHORT_SIZE, TrialConflict, reserve_free_check, inspect_free_check, build_free_check_report,
)
from capturebrief_core.intake import IntakeError
from capturebrief_core.request_draft import (
    FREE_CLAIM, FREE_END, FREE_OFFER, FREE_SUBJECT,
    PAID_CLAIM, SCOPE_CLAIM, SCOPE_END, SCOPE_SUBJECT,
    create_unverified_case, parse_customer_draft,
)
from scripts.import_request_draft import import_request
from scripts.register_free_check import register_private_free_check
from tests.test_request_draft import draft

NOW = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
REVIEW = "1" * 64


def free_draft(*, company="Example Federal", assumptions=None):
    value = draft(company=company, assumptions=assumptions or ["The public deadline has not changed."])
    return (value.replace("To: jayp19386@gmail.com", "To: jay@retallyrecovery.com")
            .replace(SCOPE_SUBJECT, FREE_SUBJECT)
            .replace(SCOPE_CLAIM, FREE_CLAIM)
            .replace(SCOPE_END, FREE_END))


def private_pair(root, *, company="Example Federal", raw=None, imported_at=NOW):
    text = raw or free_draft(company=company)
    digest = hashlib.sha256(text.encode()).hexdigest()
    source = root / f"{digest}.txt"
    source.write_text(text, encoding="utf-8")
    case_file = root / f"request-{digest}.case.json"
    receipt_file = root / f"request-{digest}.receipt.json"
    import_request(str(source), str(case_file), str(receipt_file), imported_at=imported_at)
    return (json.loads(case_file.read_text()), json.loads(receipt_file.read_text()), case_file)


class FreeTrialTests(unittest.TestCase):
    def test_real_format_and_legacy_paid_and_scope_remain_accepted(self):
        parsed = parse_customer_draft(free_draft())
        self.assertEqual(parsed.purchase_claim, FREE_CLAIM)
        for raw in (draft(), draft(paid=True)):
            self.assertIn(parse_customer_draft(raw).purchase_claim, {SCOPE_CLAIM, PAID_CLAIM})
        case, claim = create_unverified_case(free_draft(), submitted_at=NOW.isoformat())
        self.assertEqual(case["intake"]["requested_offer"], FREE_OFFER)
        self.assertEqual(len(case["assumptions"]), 1)
        self.assertEqual(case["assumptions"][0]["evidence_state"], "UNPROVEN")
        self.assertFalse(claim["trial_eligibility_verified"])
        self.assertFalse(claim["trial_admission_authorized"])
        self.assertFalse(claim["automatic_upgrade_authorized"])
        self.assertEqual(inspect_free_check(case, now=NOW)["state"], "BLOCKED_NO_RESERVATION")

    def test_extra_assumptions_mismatched_offer_and_recipient_rejected(self):
        for raw in (
            free_draft(assumptions=["One", "Two"]),
            free_draft().replace(FREE_SUBJECT, SCOPE_SUBJECT),
            free_draft().replace(FREE_END, SCOPE_END),
            free_draft().replace("To: jay@retallyrecovery.com", "To: attacker@example.com"),
        ):
            with self.subTest(raw=raw[:55]), self.assertRaises(IntakeError):
                create_unverified_case(raw)

    def test_private_registration_is_no_charge_idempotent_and_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, path = private_pair(root)
            db = root / "trials.sqlite"
            first = reserve_free_check(db, case=case, receipt=receipt,
                reviewed_business_key="domain:EXAMPLE.COM.", identity_review_sha256=REVIEW,
                observed_at=NOW)
            again = reserve_free_check(db, case=case, receipt=receipt,
                reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW,
                observed_at=NOW + timedelta(hours=1))
            self.assertEqual(first["cohort_reserved"], 1)
            self.assertEqual(again["cohort_reserved"], 1)
            self.assertEqual(again["status"], "ALREADY_RESERVED_REVIEW_REQUIRED")
            self.assertEqual(first["amount_due_cents"], 0)
            for key in ("automatic_upgrade_authorized", "customer_release_authorized",
                        "external_send_authorized", "payment_verified", "watch_included"):
                self.assertFalse(first[key])
            with sqlite3.connect(db) as con:
                rows = str(con.execute("SELECT * FROM free_check_reservations").fetchall())
            for private in ("Example Federal", "buyer@example.com", "example.com", "sam.gov"):
                self.assertNotIn(private, rows + json.dumps(first))
            if os.name != "nt":
                self.assertEqual(db.stat().st_mode & 0o777, 0o600)

    def test_second_request_same_business_and_request_under_alias_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, r1, _ = private_pair(root)
            second, r2, _ = private_pair(root, company="Other Name")
            db = root / "trials.sqlite"
            reserve_free_check(db, case=first, receipt=r1, reviewed_business_key="domain:example.com",
                               identity_review_sha256=REVIEW, observed_at=NOW)
            for case, receipt, business in (
                (second, r2, "domain:example.com"),
                (first, r1, "registry:pa:some-other-entity"),
            ):
                with self.assertRaises(TrialConflict):
                    reserve_free_check(db, case=case, receipt=receipt,
                        reviewed_business_key=business, identity_review_sha256=REVIEW, observed_at=NOW)

    def test_ten_business_cohort_cap_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "trials.sqlite"
            for i in range(MAX_COHORT_SIZE + 1):
                case, receipt, _ = private_pair(root, company=f"Business {i}")
                kwargs = dict(case=case, receipt=receipt, reviewed_business_key=f"domain:business{i}.com",
                              identity_review_sha256=REVIEW, observed_at=NOW)
                if i < MAX_COHORT_SIZE:
                    self.assertEqual(reserve_free_check(db, **kwargs)["cohort_reserved"], i+1)
                else:
                    with self.assertRaises(TrialConflict):
                        reserve_free_check(db, **kwargs)

    def test_concurrent_retries_cannot_reserve_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            db = root / "trials.sqlite"
            results, errors = [], []
            barrier = threading.Barrier(2)
            def run():
                try:
                    barrier.wait(timeout=5)
                    results.append(reserve_free_check(db, case=case, receipt=receipt,
                        reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW,
                        observed_at=NOW))
                except Exception as error:
                    errors.append(error)
            threads = [threading.Thread(target=run) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=10)
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 2)
            self.assertEqual({r["cohort_reserved"] for r in results}, {1})

    def test_untrusted_receipts_paid_intake_and_case_edits_cannot_reserve(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            paid, paid_receipt, _ = private_pair(root, raw=draft(paid=True))
            changed = copy.deepcopy(case)
            changed["assumptions"][0]["evidence_state"] = "SUPPORTED"
            false_claim = {**receipt, "trial_admission_authorized": True}
            for value, evidence in ((paid, paid_receipt), (changed, receipt), (case, false_claim)):
                with self.assertRaises(ValueError):
                    reserve_free_check(root / "trials.sqlite", case=value, receipt=evidence,
                        reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW,
                        observed_at=NOW)
            self.assertFalse((root / "trials.sqlite").exists())

    def test_cli_bridge_verifies_saved_pair_and_keeps_release_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, path = private_pair(root)
            report = register_private_free_check(path, registry=root / "trials.sqlite",
                reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW)
            self.assertEqual(report["evidence_readiness"]["state"], "BLOCKED_BY_CORE_EVIDENCE")
            self.assertFalse(report["customer_release_authorized"])
            path.write_text(path.read_text() + " ", encoding="utf-8")
            with self.assertRaises(ValueError):
                register_private_free_check(path, registry=root / "other.sqlite",
                    reviewed_business_key="domain:other.com", identity_review_sha256=REVIEW)

    def test_review_identity_private_path_and_time_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            for kwargs in (
                {"reviewed_business_key": "buyer@example.com"},
                {"identity_review_sha256": "unknown"},
                {"observed_at": NOW - timedelta(seconds=1)},
            ):
                args = dict(case=case, receipt=receipt, reviewed_business_key="domain:example.com",
                            identity_review_sha256=REVIEW, observed_at=NOW)
                args.update(kwargs)
                with self.assertRaises(ValueError):
                    reserve_free_check(root / "trials.sqlite", **args)
            with self.assertRaises(ValueError):
                reserve_free_check(Path(__file__).resolve().parents[1] / "public.sqlite",
                    case=case, receipt=receipt, reviewed_business_key="domain:example.com",
                    identity_review_sha256=REVIEW, observed_at=NOW)

    def test_enriched_case_cannot_spend_reservation_on_changed_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            db = root / "trials.sqlite"
            reserve_free_check(db, case=case, receipt=receipt,
                reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW, observed_at=NOW)
            unchanged = inspect_free_check(case, database_path=db, now=NOW)
            self.assertTrue(unchanged["reservation_scope_matches"])
            self.assertEqual(unchanged["state"], "BLOCKED_BY_CORE_EVIDENCE")
            for field in ("company", "public_opportunity"):
                changed = copy.deepcopy(case)
                changed["intake"][field] = "different"
                check = inspect_free_check(changed, database_path=db, now=NOW)
                self.assertFalse(check["reservation_scope_matches"])
                self.assertEqual(check["state"], "BLOCKED_NO_RESERVATION")

    def test_unreviewed_trial_never_writes_a_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            db = root / "trials.sqlite"
            reserve_free_check(db, case=case, receipt=receipt,
                reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW, observed_at=NOW)
            output = root / "free.md"
            with self.assertRaises(ValueError):
                build_free_check_report(case, output, database_path=db, now=NOW)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name("free.md.receipt.json").exists())

    def test_existing_technical_fixture_builds_one_result_without_watch_or_charge(self):
        # This old test fixture exercises software packaging only. It is NOT
        # non-synthetic publisher/customer evidence or live-pursuit acceptance.
        fixture = json.loads((Path(__file__).resolve().parents[1] /
                             "fixtures/ready_trace_case.json").read_text())
        historical = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, receipt, _ = private_pair(root,
                raw=free_draft(assumptions=[fixture["assumptions"][0]["text"]]),
                imported_at=historical)
            db = root / "trials.sqlite"
            reserve_free_check(db, case=original, receipt=receipt,
                reviewed_business_key="domain:example.com", identity_review_sha256=REVIEW,
                observed_at=historical)
            fixture["case_id"] = original["case_id"]
            fixture["intake"] = original["intake"]
            output = root / "free.md"
            built = build_free_check_report(fixture, output, database_path=db, now=historical)
            self.assertEqual(built["report_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(built["assumption_count"], 1)
            self.assertEqual(built["amount_due_cents"], 0)
            self.assertFalse(built["watch_included"])
            self.assertFalse(built["customer_delivery_verified"])
            self.assertFalse(built["customer_release_authorized"])
            self.assertFalse(built["external_send_authorized"])
            self.assertNotIn("buyer@example.com", output.read_text())
            self.assertIn("No charge, automatic upgrade or included change watch", output.read_text())
            self.assertFalse((root / "watch-baseline.json").exists())
            repeated = build_free_check_report(fixture, output, database_path=db, now=historical)
            self.assertEqual(repeated, built)
            original_bytes = output.read_bytes()
            output.with_name("free.md.receipt.json").write_text("tampered")
            with self.assertRaises(ValueError):
                build_free_check_report(fixture, output, database_path=db, now=historical)
            self.assertEqual(output.read_bytes(), original_bytes)
            # Synthetic trace flag and original source corruption must still
            # block even after a matching trial reservation has been created.
            synthetic, corrupt = copy.deepcopy(fixture), copy.deepcopy(fixture)
            synthetic["decision_trace"]["synthetic"] = True
            corrupt["decision_trace"]["snapshots"][0]["text"] += "unsupported changed text"
            for bad in (synthetic, corrupt):
                with self.assertRaises(ValueError):
                    build_free_check_report(bad, root / "blocked.md", database_path=db, now=historical)


    def test_inspection_rejects_false_reservation_chronology(self):
        """A tampered or future-dated SQLite row is not an eligible trial."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case, receipt, _ = private_pair(root)
            db = root / "trials.sqlite"
            reserve_free_check(
                db, case=case, receipt=receipt,
                reviewed_business_key="domain:example.com",
                identity_review_sha256=REVIEW, observed_at=NOW,
            )
            healthy = inspect_free_check(case, database_path=db, now=NOW)
            self.assertTrue(healthy["reservation_scope_matches"])
            for invalid in (
                (NOW + timedelta(seconds=1)).isoformat(),
                (NOW - timedelta(seconds=1)).isoformat(),
                "2026-10-26T14:00:00",  # naive clock without UTC evidence
                "not-a-datetime",
            ):
                with self.subTest(reserved_at=invalid):
                    with sqlite3.connect(db) as conn:
                        conn.execute(
                            "UPDATE free_check_reservations SET reserved_at = ?",
                            (invalid,),
                        )
                    observed = inspect_free_check(case, database_path=db, now=NOW)
                    self.assertFalse(observed["reservation_scope_matches"])
                    self.assertEqual(observed["state"], "BLOCKED_NO_RESERVATION")
                    self.assertIn("FREE_CHECK_RESERVATION_REQUIRED", observed["blocker_codes"])


if __name__ == "__main__":
    unittest.main()
