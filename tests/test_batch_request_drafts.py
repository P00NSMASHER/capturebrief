"""Fictional buyer drafts only: private batch import, retries, and isolation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.request_draft import PAID_CLAIM
from scripts.batch_import_request_drafts import batch_import
from scripts.import_request_draft import import_request
from tests.test_request_draft import draft


class BatchDraftTests(unittest.TestCase):
    def roots(self, base):
        incoming = Path(base) / "private-inbox"
        output = Path(base) / "private-cases"
        incoming.mkdir()
        output.mkdir()
        return incoming, output

    def test_empty_private_inbox_has_explicit_no_requests_status(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            report = batch_import(incoming, output)
            self.assertEqual(report["status"], "BATCH_NO_REQUESTS")
            self.assertEqual(report["processed_txt"], 0)
            self.assertEqual(report["created"], 0)
            self.assertFalse(report["customer_release_authorized"])
            self.assertEqual(list(output.iterdir()), [])
            (incoming / "unrelated.pdf").write_bytes(b"%PDF invented only")
            ignored = batch_import(incoming, output)
            self.assertEqual(ignored["status"], "BATCH_NO_REQUESTS")
            self.assertEqual(ignored["ignored_non_txt"], 1)

    def test_multiple_valid_duplicates_invalid_and_non_text(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            buyer_a = draft(paid=True, company="Fictional Buyer A")
            buyer_b = draft(company="Fictional Buyer B")
            (incoming / "a.txt").write_text(buyer_a, encoding="utf-8")
            (incoming / "copy.txt").write_text(buyer_a, encoding="utf-8")
            (incoming / "b.txt").write_text(buyer_b, encoding="utf-8")
            (incoming / "invalid.txt").write_text("not a buyer draft", encoding="utf-8")
            (incoming / "unrelated.pdf").write_bytes(b"%PDF fictional")
            report = batch_import(incoming, output)
            self.assertEqual(report["status"], "BATCH_PARTIAL_REVIEW_REQUIRED")
            self.assertEqual(
                (report["created"], report["reused"], report["recovered"],
                 report["duplicates"], report["blocked"], report["ignored_non_txt"]),
                (2, 0, 0, 1, 1, 1),
            )
            self.assertEqual(len(list(output.glob("*.case.json"))), 2)
            self.assertEqual(len(list(output.glob("*.receipt.json"))), 2)
            self.assertNotIn("buyer@example.com", json.dumps(report))
            self.assertNotIn("Fictional Buyer", json.dumps(report))
            for item in output.glob("*.receipt.json"):
                receipt = json.loads(item.read_text(encoding="utf-8"))
                self.assertFalse(receipt["purchase_claim_verified"])
                self.assertFalse(receipt["case_release_authorized"])
                self.assertEqual(receipt["independent_payment_lookup"], "NOT_PERFORMED")
            self.assertFalse(report["customer_release_authorized"])
            self.assertFalse(report["external_send_authorized"])
            self.assertFalse(report["payment_verified"])
            self.assertFalse(any(output.glob("*.intake.lock")))

    def test_repeat_is_idempotent_and_missing_partner_is_recovered(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            message = draft(company="Fictional Customer Retry")
            (incoming / "one.txt").write_text(message, encoding="utf-8")
            original = batch_import(incoming, output)
            self.assertEqual(original["created"], 1)
            case_path = next(output.glob("*.case.json"))
            receipt_path = next(output.glob("*.receipt.json"))
            saved = (case_path.read_bytes(), receipt_path.read_bytes())
            retry = batch_import(incoming, output)
            self.assertEqual(retry["reused"], 1)
            self.assertEqual((case_path.read_bytes(), receipt_path.read_bytes()), saved)
            receipt_path.unlink()
            repaired = batch_import(incoming, output)
            self.assertEqual(repaired["recovered"], 1)
            self.assertEqual((case_path.read_bytes(), receipt_path.read_bytes()), saved)
            case_path.unlink()
            repaired_again = batch_import(incoming, output)
            self.assertEqual(repaired_again["recovered"], 1)
            self.assertEqual((case_path.read_bytes(), receipt_path.read_bytes()), saved)

    def test_mutating_original_between_fingerprint_and_import_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            src = incoming / "one.txt"
            src.write_text(draft(company="Buyer Before"), encoding="utf-8")
            def mutate_source_then_import(*args, **kwargs):
                src.write_text(draft(company="Buyer After"), encoding="utf-8")
                return import_request(*args, **kwargs)
            with patch("scripts.batch_import_request_drafts.import_request",
                       side_effect=mutate_source_then_import):
                report = batch_import(incoming, output)
            self.assertEqual(report["blocked"], 1)
            self.assertEqual(report["created"], 0)
            self.assertFalse(list(output.iterdir()))
            self.assertNotIn("Buyer Before", json.dumps(report))
            self.assertNotIn("Buyer After", json.dumps(report))

    def test_rejects_symlink_input_and_conflicting_saved_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            content = draft()
            (incoming / "real.txt").write_text(content, encoding="utf-8")
            link = incoming / "link.txt"
            try:
                link.symlink_to(incoming / "real.txt")
            except (OSError, NotImplementedError):
                self.skipTest("This runner cannot create a symlink")
            result = batch_import(incoming, output)
            self.assertEqual(result["created"], 1)
            self.assertEqual(result["blocked"], 1)
            receipt = next(output.glob("*.receipt.json"))
            receipt.write_text("tampered", encoding="utf-8")
            second = batch_import(incoming, output)
            self.assertEqual(second["blocked"], 2)
            self.assertEqual(receipt.read_text(encoding="utf-8"), "tampered")
            self.assertEqual(len(list(output.glob("*.case.json"))), 1)

    def test_limit_or_misconfigured_roots_block_before_publication(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            for n in range(4):
                (incoming / f"buyer-{n}.txt").write_text(
                    draft(company=f"Fictional Buyer {n}"), encoding="utf-8"
                )
            with self.assertRaises(ValueError):
                batch_import(incoming, output, max_files=3)
            with self.assertRaises(ValueError):
                batch_import(incoming, incoming)
            with self.assertRaises(ValueError):
                batch_import(incoming, output / "missing-dir")
            self.assertEqual(list(output.iterdir()), [])

    def test_expected_fingerprint_is_verified_before_any_case_publication(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            src = incoming / "one.txt"
            src.write_text(draft(), encoding="utf-8")
            wrong = hashlib.sha256(b"fictional other draft").hexdigest()
            with self.assertRaises(ValueError):
                import_request(
                    str(src), str(output / "case.json"), str(output / "receipt.json"),
                    expected_request_sha256=wrong,
                )
            self.assertFalse(list(output.iterdir()))
            original = hashlib.sha256(src.read_bytes()).hexdigest()
            created = import_request(
                str(src), str(output / "case.json"), str(output / "receipt.json"),
                expected_request_sha256=original,
            )
            self.assertEqual(created["request_sha256"], original)
            self.assertEqual(json.loads((output / "receipt.json").read_text())["request_sha256"], original)


    def test_batch_cli_outputs_review_summary_without_buyer_details(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            (incoming / "one.txt").write_text(
                draft(paid=True, company="Fictional Private Buyer"),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(Path(__file__).resolve().parents[1]
                    / "scripts" / "batch_import_request_drafts.py"),
                "--input-dir", str(incoming), "--output-dir", str(output),
            ]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            report = json.loads(first.stdout)
            self.assertEqual(report["created"], 1)
            self.assertFalse(report["payment_verified"])
            self.assertFalse(report["customer_release_authorized"])
            self.assertNotIn("Fictional Private Buyer", first.stdout)
            self.assertNotIn("buyer@example.com", first.stdout)
            self.assertNotIn(str(incoming), first.stdout)
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(json.loads(again.stdout)["reused"], 1)

    def test_batch_cli_partial_import_is_explicitly_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            (incoming / "valid.txt").write_text(draft(), encoding="utf-8")
            (incoming / "bad.txt").write_text("unstructured fictional text", encoding="utf-8")
            run = subprocess.run([
                sys.executable,
                str(Path(__file__).resolve().parents[1]
                    / "scripts" / "batch_import_request_drafts.py"),
                "--input-dir", str(incoming), "--output-dir", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result["created"], 1)
            self.assertEqual(result["blocked"], 1)
            self.assertEqual(result["status"], "BATCH_PARTIAL_REVIEW_REQUIRED")
            self.assertFalse(result["external_send_authorized"])




    def test_preview_validates_drafts_without_writing_cases(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            first = draft(paid=True, company="Fictional Preview A")
            (incoming / "one.txt").write_text(first, encoding="utf-8")
            (incoming / "clone.txt").write_text(first, encoding="utf-8")
            (incoming / "two.txt").write_text(
                draft(company="Fictional Preview B"), encoding="utf-8",
            )
            (incoming / "bad.txt").write_text("invalid fake buyer draft", encoding="utf-8")
            (incoming / "unrelated.pdf").write_bytes(b"%PDF fictional")
            before = [(p.name, p.read_bytes()) for p in incoming.iterdir()]
            result = batch_import(incoming, output, preview=True)
            self.assertEqual(result["status"], "BATCH_PREVIEW_PARTIAL_REVIEW_REQUIRED")
            self.assertTrue(result["preview_only"])
            self.assertEqual(result["preview_new"], 2)
            self.assertEqual(result["duplicates"], 1)
            self.assertEqual(result["blocked"], 1)
            self.assertEqual(result["ignored_non_txt"], 1)
            self.assertEqual(result["created"], 0)
            self.assertEqual(result["reused"], 0)
            self.assertEqual(result["recovered"], 0)
            self.assertEqual(list(output.iterdir()), [])
            self.assertEqual([(p.name, p.read_bytes()) for p in incoming.iterdir()], before)
            self.assertNotIn("Fictional Preview", json.dumps(result))
            self.assertNotIn("buyer@example.com", json.dumps(result))
            self.assertNotIn(str(incoming), json.dumps(result))
            self.assertFalse(result["payment_verified"])
            self.assertFalse(result["customer_release_authorized"])

    def test_preview_identifies_existing_and_partial_as_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            (incoming / "one.txt").write_text(draft(), encoding="utf-8")
            batch_import(incoming, output)
            case = next(output.glob("*.case.json"))
            receipt = next(output.glob("*.receipt.json"))
            untouched_case = case.read_bytes()
            untouched_receipt = receipt.read_bytes()
            existing = batch_import(incoming, output, preview=True)
            self.assertEqual(existing["preview_existing_unverified"], 1)
            self.assertEqual(existing["created"], 0)
            self.assertEqual(case.read_bytes(), untouched_case)
            self.assertEqual(receipt.read_bytes(), untouched_receipt)
            receipt.unlink()
            partial = batch_import(incoming, output, preview=True)
            self.assertEqual(partial["preview_partial_unverified"], 1)
            self.assertFalse(receipt.exists(), "Preview must never repair an incomplete pair")
            self.assertEqual(case.read_bytes(), untouched_case)
            # A tampered stored case must not be claimed 'verified' by preview.
            case.write_text("tampered existing case", encoding="utf-8")
            contaminated = batch_import(incoming, output, preview=True)
            self.assertEqual(contaminated["preview_partial_unverified"], 1)
            self.assertTrue(contaminated["preview_only"])
            self.assertEqual(case.read_text(encoding="utf-8"), "tampered existing case")

    def test_preview_empty_and_bounded_batch_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            self.assertEqual(
                batch_import(incoming, output, preview=True)["status"],
                "BATCH_PREVIEW_NO_REQUESTS",
            )
            self.assertFalse(list(output.iterdir()))
            for index in range(3):
                (incoming / f"item-{index}.txt").write_text(
                    draft(company=f"Fictional Preview {index}"), encoding="utf-8",
                )
            with self.assertRaises(ValueError):
                batch_import(incoming, output, preview=True, max_files=2)
            self.assertFalse(list(output.iterdir()))

    def test_preview_cli_is_dry_and_sanitized_with_explicit_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            incoming, output = self.roots(td)
            (incoming / "one.txt").write_text(
                draft(company="Fictional Preview CLI"), encoding="utf-8",
            )
            command = [
                sys.executable,
                str(Path(__file__).resolve().parents[1]
                    / "scripts" / "batch_import_request_drafts.py"),
                "--preview", "--input-dir", str(incoming),
                "--output-dir", str(output),
            ]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)
            self.assertTrue(report["preview_only"])
            self.assertEqual(report["preview_new"], 1)
            self.assertEqual(report["created"], 0)
            self.assertFalse(list(output.iterdir()))
            for secret in ("Fictional Preview CLI", "buyer@example.com", str(incoming)):
                self.assertNotIn(secret, run.stdout)
            (incoming / "bad.txt").write_text("unstructured fake", encoding="utf-8")
            mixed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(mixed.returncode, 3, mixed.stderr)
            self.assertEqual(json.loads(mixed.stdout)["blocked"], 1)
            self.assertFalse(list(output.iterdir()))


if __name__ == "__main__":
    unittest.main()
