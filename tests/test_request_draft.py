"""Cross-boundary tests: browser-generated request -> strict private case -> no send."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.audit import audit_case
from capturebrief_core.atomic_io import ArtifactLockedError, exclusive_path_lock
from capturebrief_core.intake import IntakeError
from capturebrief_core.model import canonical_json
from capturebrief_core.request_draft import (
    MAX_REQUEST_TEXT,
    PAID_CLAIM, PAID_END, PAID_SUBJECT, SCOPE_CLAIM, SCOPE_END,
    SCOPE_SUBJECT, create_unverified_case, parse_customer_draft,
)
from scripts.import_request_draft import REPOSITORY, import_request

NOW = datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc)
SAM = "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view"


def draft(*, paid=False, envelope=True, assumptions=None, company="Example Federal",
          email="buyer@example.com", public_url=SAM) -> str:
    claim = PAID_CLAIM if paid else SCOPE_CLAIM
    subject = PAID_SUBJECT if paid else SCOPE_SUBJECT
    assumptions = assumptions if assumptions is not None else [
        "The original deadline is unchanged.",
        "Only current solicitation versions are relevant.",
    ]
    lines = (
        (["To: jayp19386@gmail.com", "Subject: " + subject, ""] if envelope else [])
        + [
            "Hello CaptureBrief,", "",
            "Purchase status (customer-reported, not verified): " + claim,
            "Company: " + company,
            "Work email: " + email,
            "Public opportunity link: " + public_url,
            "Current posture: HOLD", "",
            "Assumptions to check:",
        ]
        + [f"{i}. {text}" for i, text in enumerate(assumptions, 1)]
        + ["", "I confirm this request contains only public, non-sensitive information.",
           "", PAID_END if paid else SCOPE_END]
    )
    return "\n".join(lines)


class RequestDraftTests(unittest.TestCase):
    def test_browser_clipboard_draft_builds_only_unproven_core_case(self):
        parsed = parse_customer_draft(draft())
        self.assertTrue(parsed.envelope_present)
        self.assertEqual(parsed.purchase_claim, SCOPE_CLAIM)
        case, claim = create_unverified_case(
            draft(), submitted_at=NOW.isoformat()
        )
        self.assertEqual(case["intake"]["company"], "Example Federal")
        self.assertEqual(case["intake"]["email"], "buyer@example.com")
        self.assertEqual(case["intake"]["public_opportunity"], SAM)
        self.assertEqual([x["evidence_state"] for x in case["assumptions"]],
                         ["UNPROVEN", "UNPROVEN"])
        self.assertEqual(case["packet"]["history_action_ids"], [])
        self.assertEqual(case["sources"], [])
        self.assertFalse(claim["ready_to_start_work"])
        self.assertFalse(claim["purchase_claim_verified"])
        self.assertEqual(audit_case(case, now=NOW).release_state, "FAIL_CLOSED")

    def test_paid_customer_claim_is_not_verified_even_without_envelope(self):
        case, status = create_unverified_case(draft(paid=True, envelope=False),
                                             submitted_at=NOW.isoformat())
        self.assertEqual(status["purchase_claim"], PAID_CLAIM)
        self.assertFalse(status["purchase_claim_verified"])
        self.assertFalse(status["sender_authenticated"])
        self.assertFalse(status["message_delivery_verified"])
        self.assertFalse(status["external_send_authorized"])
        self.assertNotIn("paid", case["intake"])

    def test_accepts_CRLF_and_utf8_bom(self):
        parsed = parse_customer_draft("\ufeff" + draft().replace("\n", "\r\n") + "\r\n")
        self.assertEqual(parsed.intake["company"], "Example Federal")

    def test_five_500_character_assumptions_survive_full_pipeline(self):
        lines = [chr(65+i) * 500 for i in range(5)]
        parsed = parse_customer_draft(draft(assumptions=lines))
        self.assertEqual([parsed.intake[f"assumption_{i}"] for i in range(1, 6)], lines)
        case, _ = create_unverified_case(draft(assumptions=lines), submitted_at=NOW.isoformat())
        self.assertEqual([x["text"] for x in case["assumptions"]], lines)

    def test_forged_headers_and_payment_contradictions_rejected(self):
        samples = (
            draft().replace("To: jayp19386@gmail.com", "To: attacker@example.com"),
            draft().replace("Subject: " + SCOPE_SUBJECT, "Subject: " + PAID_SUBJECT),
            draft(paid=True).replace(PAID_END, SCOPE_END),
            draft().replace(SCOPE_CLAIM, "PAYMENT_CONFIRMED"),
            "Subject: " + SCOPE_SUBJECT + "\n\n" + draft(envelope=False),
        )
        for raw in samples:
            with self.subTest(raw=raw[:40]), self.assertRaises(IntakeError):
                parse_customer_draft(raw)

    def test_missing_fields_and_newline_injection_rejected(self):
        samples = (
            draft(company=""),
            draft(email=""),
            draft().replace("Work email: buyer@example.com\n", ""),
            draft().replace("Company: Example Federal", "Company: Foo\nWork email: fake@example.com"),
            draft().replace("Current posture: HOLD", "Current posture: APPROVED"),
            draft().replace("Public opportunity link:", "Private link:"),
            draft() + "\nApproved to release.",
            draft().replace("I confirm this request contains only public, non-sensitive information.", "No"),
        )
        for raw in samples:
            with self.subTest(raw=raw[:50]), self.assertRaises(IntakeError):
                create_unverified_case(raw)

    def test_unverified_urls_are_validated_by_original_core(self):
        for url in ("ftp://host/item", "https://user:pass@sam.gov/opp/demo",
                    "http://localhost/private", "https://company.local/secret"):
            with self.subTest(url=url), self.assertRaises(IntakeError):
                create_unverified_case(draft(public_url=url))

    def test_assumption_order_duplicate_limit_and_blank_rejected(self):
        cases = (
            draft(assumptions=[]),
            draft(assumptions=["Dup", "  dup  "]),
            draft(assumptions=["x" * 501]),
            draft(assumptions=["A", "B", "C", "D", "E", "F"]),
            draft().replace("2. Only current", "4. Only current"),
        )
        for raw in cases:
            with self.subTest(length=len(raw)), self.assertRaises(IntakeError):
                create_unverified_case(raw)

    def test_rejects_oversized_or_binary_content(self):
        for raw in (draft() + "x" * MAX_REQUEST_TEXT, draft() + "\x00"):
            with self.assertRaises(IntakeError):
                parse_customer_draft(raw)

    def test_private_operator_import_is_idempotent_and_contains_no_auto_approval(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            incoming, case_path, receipt_path = [root / p for p in
                                                 ("inbox.txt", "case.json", "receipt.json")]
            incoming.write_text(draft(paid=True))
            first = import_request(str(incoming), str(case_path), str(receipt_path),
                                   imported_at=NOW)
            again = import_request(str(incoming), str(case_path), str(receipt_path),
                                   imported_at=NOW)
            self.assertEqual(first, again)
            saved_case = json.loads(case_path.read_text())
            saved_receipt = json.loads(receipt_path.read_text())
            self.assertEqual(saved_receipt["case_sha256"], hashlib.sha256(canonical_json(saved_case)).hexdigest())
            self.assertEqual(saved_receipt["case_file_sha256"], hashlib.sha256(case_path.read_bytes()).hexdigest())
            self.assertEqual(saved_receipt["independent_payment_lookup"], "NOT_PERFORMED")
            self.assertFalse(saved_receipt["case_release_authorized"])
            self.assertFalse(saved_receipt["sender_authenticated"])
            self.assertTrue(saved_receipt["operator_review_required"])
            self.assertEqual(saved_case["intake"]["record_time_basis"],
                             "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT")
            self.assertNotIn("buyer@example.com", json.dumps(saved_receipt))
            if os.name != "nt":
                self.assertEqual(case_path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)

    def test_default_time_retries_reuse_existing_case_and_receipt(self):
        # Operator CLIs omit --imported-at in normal use. Retrying identical
        # customer text must NOT create a new case ID or conflict with itself.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_file, case_file, receipt_file = (
                root / "buyer.txt", root / "case.json", root / "receipt.json"
            )
            input_file.write_text(draft(paid=True), encoding="utf-8")
            first = import_request(
                str(input_file), str(case_file), str(receipt_file),
                imported_at=NOW,
            )
            case_bytes, receipt_bytes = case_file.read_bytes(), receipt_file.read_bytes()
            # Deliberately OMIT imported_at on retry, as a real operator does.
            second = import_request(str(input_file), str(case_file), str(receipt_file))
            self.assertEqual(first, second)
            self.assertEqual(case_file.read_bytes(), case_bytes)
            self.assertEqual(receipt_file.read_bytes(), receipt_bytes)
            self.assertFalse(json.loads(receipt_bytes)["purchase_claim_verified"])

    def test_partial_case_or_receipt_recovery_reuses_original_timestamp(self):
        # Recover from interrupted two-file publication. Never invent a new
        # case identity, silently rewrite the intact artifact or promote claims.
        for missing in ("receipt", "case"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                src, case_file, receipt_file = (
                    root / "buyer.txt", root / "case.json", root / "receipt.json"
                )
                src.write_text(draft(), encoding="utf-8")
                original = import_request(
                    str(src), str(case_file), str(receipt_file), imported_at=NOW,
                )
                expected = (case_file.read_bytes(), receipt_file.read_bytes())
                (receipt_file if missing == "receipt" else case_file).unlink()
                restored = import_request(str(src), str(case_file), str(receipt_file))
                self.assertEqual(restored, original)
                self.assertEqual(
                    (case_file.read_bytes(), receipt_file.read_bytes()), expected
                )

    def test_changed_request_or_tampered_artifact_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src, case_file, receipt_file = (
                root / "buyer.txt", root / "case.json", root / "receipt.json"
            )
            src.write_text(draft(), encoding="utf-8")
            import_request(str(src), str(case_file), str(receipt_file), imported_at=NOW)
            old_case, old_receipt = case_file.read_bytes(), receipt_file.read_bytes()
            src.write_text(draft(company="Different Buyer"), encoding="utf-8")
            with self.assertRaises(ValueError):
                import_request(str(src), str(case_file), str(receipt_file))
            self.assertEqual(case_file.read_bytes(), old_case)
            self.assertEqual(receipt_file.read_bytes(), old_receipt)
            src.write_text(draft(), encoding="utf-8")
            receipt_file.write_text("tampered")
            with self.assertRaises(ValueError):
                import_request(str(src), str(case_file), str(receipt_file))
            self.assertEqual(case_file.read_bytes(), old_case)
            self.assertEqual(receipt_file.read_text(), "tampered")


    def test_concurrent_importers_share_one_case_identity(self):
        """A duplicated simultaneous inbox job must not create conflicting case IDs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, case, receipt = (
                root / "request.txt", root / "case.json", root / "receipt.json"
            )
            source.write_text(draft(paid=True), encoding="utf-8")
            first_at_write = threading.Event()
            release_first = threading.Event()
            outcomes: dict[str, dict] = {}
            failures: list[BaseException] = []
            from scripts import import_request_draft as module
            original_writer = module.ensure_exact_bytes

            def delayed_first_writer(path, data, **kwargs):
                if threading.current_thread().name == "first-import" and Path(path) == case:
                    first_at_write.set()
                    if not release_first.wait(5):
                        raise AssertionError("Parallel test writer was never released")
                return original_writer(path, data, **kwargs)

            def run(label):
                try:
                    outcomes[label] = import_request(
                        str(source), str(case), str(receipt),
                    )
                except BaseException as exc:
                    failures.append(exc)

            with patch("scripts.import_request_draft.ensure_exact_bytes",
                       side_effect=delayed_first_writer):
                first = threading.Thread(target=run, args=("first",),
                                         name="first-import")
                second = threading.Thread(target=run, args=("second",),
                                          name="second-import")
                first.start()
                try:
                    self.assertTrue(
                        first_at_write.wait(12),
                        "First import never reached case publication; worker error types: "
                        + ",".join(type(exc).__name__ for exc in failures),
                    )
                    second.start()
                    time.sleep(0.15)
                finally:
                    release_first.set()
                    first.join(timeout=8)
                    if second.ident is not None:
                        second.join(timeout=8)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(outcomes["first"], outcomes["second"])
            saved_case = json.loads(case.read_text(encoding="utf-8"))
            saved_receipt = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(saved_case["case_id"], saved_receipt["case_id"])
            self.assertEqual(
                saved_receipt["case_file_sha256"],
                hashlib.sha256(case.read_bytes()).hexdigest(),
            )
            self.assertFalse(saved_receipt["purchase_claim_verified"])
            self.assertEqual(list(root.glob("*.intake.lock")), [])

    def test_locked_intake_path_refuses_a_second_import_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            request, case, receipt = (
                root / "request.txt", root / "case.json", root / "receipt.json"
            )
            request.write_text(draft(), encoding="utf-8")
            with exclusive_path_lock(case, suffix=".intake.lock",
                                     timeout_seconds=0.05):
                with self.assertRaises(ArtifactLockedError):
                    import_request(
                        str(request), str(case), str(receipt),
                        lock_timeout_seconds=0.05,
                    )
                self.assertFalse(case.exists())
                self.assertFalse(receipt.exists())
            self.assertFalse(case.with_name(case.name + ".intake.lock").exists())

    def test_private_destination_rejects_public_repo_and_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            incoming = root / "draft.txt"
            incoming.write_text(draft())
            with self.assertRaisesRegex(ValueError, "outside public source"):
                import_request(str(incoming), str(REPOSITORY / "customer-data.json"),
                               str(root / "receipt.json"), imported_at=NOW)
            case_path, receipt_path = root / "case.json", root / "receipt.json"
            import_request(str(incoming), str(case_path), str(receipt_path), imported_at=NOW)
            case_path.write_text("tampered")
            with self.assertRaises(ValueError):
                import_request(str(incoming), str(case_path), str(receipt_path),
                               imported_at=NOW)
            self.assertEqual(case_path.read_text(), "tampered")

    def test_cli_does_not_log_buyer_email_and_uses_private_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "draft.txt"
            input_path.write_text(draft(), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "scripts/import_request_draft.py", str(input_path),
                 "--case-output", str(root / "case.json"),
                 "--receipt-output", str(root / "receipt.json"),
                 "--imported-at", NOW.isoformat()],
                cwd=REPOSITORY, capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertNotIn("buyer@example.com", run.stdout)
            self.assertNotIn("Example Federal", run.stdout)
            self.assertFalse(json.loads(run.stdout)["payment_verified"])


if __name__ == "__main__":
    unittest.main()
