"""Offline operator-queue tests using only made-up CaptureBrief buyer drafts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.batch_import_request_drafts import batch_import
from scripts.review_private_cases import review_private_cases
from tests.test_request_draft import draft

NOW = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)


class PrivateCaseReviewQueueTests(unittest.TestCase):
    def roots(self, folder):
        root = Path(folder)
        incoming, cases = root / "inbox", root / "cases"
        incoming.mkdir()
        cases.mkdir()
        return incoming, cases

    def test_two_real_core_review_plans_without_raw_buyer_details(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            (inbox / "one.txt").write_text(draft(paid=True, company="Fictional Queue A"), encoding="utf-8")
            (inbox / "two.txt").write_text(draft(company="Fictional Queue B",
                            email="queue-other@example.com"), encoding="utf-8")
            self.assertEqual(batch_import(inbox, cases)["created"], 2)
            snapshots = {p.name: p.read_bytes() for p in cases.iterdir()}
            report = review_private_cases(cases, now=NOW)
            self.assertEqual(report["status"], "PRIVATE_CASE_REVIEW_PENDING")
            self.assertEqual(report["verified_intake_pairs"], 2)
            self.assertEqual(report["blocked"], 0)
            self.assertEqual(report["missing_partner"], 0)
            self.assertEqual(len(report["cases"]), 2)
            for row in report["cases"]:
                self.assertEqual(row["state"], "UNVERIFIED_INTAKE_REVIEW_REQUIRED")
                self.assertGreater(row["open_tasks"], 0)
                self.assertIn(row["next_effort_stage"],
                              {"HISTORY_CURRENT", "REFERENCE_REVIEW", "PACKET_BYTES", "ASSUMPTION_REVIEW", "DELIVERY", "OTHER"})
                self.assertFalse(row["payment_verified"])
                self.assertFalse(row["release_authorized"])
                self.assertFalse(row["external_send_authorized"])
                self.assertEqual(row["related_same_buyer_and_opportunity"], 0)
                self.assertNotIn("case_id", row)
                self.assertNotIn("company", row)
                self.assertNotIn("email", row)
            self.assertEqual(snapshots, {p.name: p.read_bytes() for p in cases.iterdir()})
            output = json.dumps(report)
            for forbidden in ("queue-other@example.com", "buyer@example.com",
                              "Fictional Queue", "https://sam.gov/opp/",
                              str(cases), "CB-"):
                self.assertNotIn(forbidden, output)
            self.assertFalse(report["any_customer_payment_verified"])
            self.assertFalse(report["any_external_send_authorized"])
            self.assertFalse(report["any_customer_release_authorized"])

    def test_related_edited_requests_are_flagged_but_never_merged(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            same_buyer = draft(company="Fictional Same Buyer",
                               assumptions=["The closing time is correct."])
            revised = draft(company="Fictional Same Buyer",
                            assumptions=["The closing time has changed."])
            (inbox / "one.txt").write_text(same_buyer, encoding="utf-8")
            (inbox / "two.txt").write_text(revised, encoding="utf-8")
            imported = batch_import(inbox, cases)
            self.assertEqual(imported["created"], 2, "Changed requests must not auto-merge")
            queue = review_private_cases(cases, now=NOW)
            self.assertEqual(queue["verified_intake_pairs"], 2)
            self.assertEqual(queue["possible_related_case_pairs"], 1)
            self.assertEqual(
                [v["related_same_buyer_and_opportunity"] for v in queue["cases"]],
                [1, 1],
            )
            self.assertEqual(len(list(cases.glob("*.case.json"))), 2)

    def test_tampered_case_receipt_and_missing_pair_all_block_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            for idx in range(3):
                (inbox / f"r{idx}.txt").write_text(
                    draft(company=f"Fictional Tamper {idx}"), encoding="utf-8"
                )
            self.assertEqual(batch_import(inbox, cases)["created"], 3)
            targets = sorted(cases.glob("*.case.json"))
            one = targets[0]
            two = targets[1]
            three = targets[2]
            one.write_text('{"case_id":"FORGED_PAID"}', encoding="utf-8")
            receipt_two = two.with_name(two.name.replace(".case.json", ".receipt.json"))
            rec = json.loads(receipt_two.read_text(encoding="utf-8"))
            rec["purchase_claim_verified"] = True
            receipt_two.write_text(json.dumps(rec), encoding="utf-8")
            receipt_three = three.with_name(three.name.replace(".case.json", ".receipt.json"))
            receipt_three.unlink()
            snapshots = {p.name: p.read_bytes() for p in cases.iterdir()}
            report = review_private_cases(cases, now=NOW)
            self.assertEqual(report["verified_intake_pairs"], 0)
            self.assertEqual(report["blocked"], 2)
            self.assertEqual(report["missing_partner"], 1)
            self.assertEqual(report["status"], "PRIVATE_CASE_REVIEW_BLOCKED")
            self.assertEqual(snapshots, {p.name: p.read_bytes() for p in cases.iterdir()})
            self.assertFalse(any(p.name.endswith(".intake.lock") for p in cases.iterdir()))

    def test_active_import_lock_blocks_claiming_case_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            (inbox / "buyer.txt").write_text(draft(), encoding="utf-8")
            batch_import(inbox, cases)
            case = next(cases.glob("*.case.json"))
            lock = case.with_name(case.name + ".intake.lock")
            lock.write_text("fictional in-progress operation", encoding="utf-8")
            report = review_private_cases(cases, now=NOW)
            self.assertEqual(report["verified_intake_pairs"], 0)
            self.assertEqual(report["blocked"], 1)
            self.assertEqual(report["status"], "PRIVATE_CASE_REVIEW_BLOCKED")
            self.assertTrue(lock.exists(), "Read-only reviewer must not remove a lock")

    def test_orphan_case_or_receipt_and_wrong_names_are_never_silent(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            (inbox / "buyer.txt").write_text(draft(), encoding="utf-8")
            batch_import(inbox, cases)
            case = next(cases.glob("*.case.json"))
            receipt = next(cases.glob("*.receipt.json"))
            receipt.unlink()
            (cases / "request-not-a-sha.case.json").write_text("fake", encoding="utf-8")
            result = review_private_cases(cases)
            self.assertEqual(result["missing_partner"], 1)
            self.assertGreaterEqual(result["ignored_non_case_entries"], 1)
            self.assertEqual(result["verified_intake_pairs"], 0)
            self.assertTrue(case.exists())

    def test_empty_bounded_invalid_path_and_cli_read_only_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox, cases = self.roots(temp)
            self.assertEqual(review_private_cases(cases)["status"], "PRIVATE_CASE_REVIEW_EMPTY")
            for idx in range(3):
                (inbox / f"{idx}.txt").write_text(
                    draft(company=f"Fictional Queue {idx}"), encoding="utf-8"
                )
            batch_import(inbox, cases)
            with self.assertRaises(ValueError):
                review_private_cases(cases, max_cases=2)
            before = {p.name: p.read_bytes() for p in cases.iterdir()}
            command = [sys.executable,
                       str(Path(__file__).resolve().parents[1] / "scripts" / "review_private_cases.py"),
                       "--cases-dir", str(cases), "--now", NOW.isoformat()]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)
            self.assertEqual(report["verified_intake_pairs"], 3)
            self.assertNotIn("buyer@example.com", run.stdout)
            self.assertNotIn(str(cases), run.stdout)
            self.assertEqual(before, {p.name: p.read_bytes() for p in cases.iterdir()})
