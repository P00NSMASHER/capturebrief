"""Offline attack and correctness tests for the per-pursuit SAM source lane."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from capturebrief_core.current_api import SEARCH_URL
from capturebrief_core.history import make_history_receipt
from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from capturebrief_core.scoped_source import (
    ScopedSourceBlocked, observe_scoped_case, verify_scoped_capture,
    bind_reviewed_scoped_case, retain_review_source, read_private_case,
)
from scripts.import_request_draft import import_request
from tests.test_free_trial import free_draft

NOW = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
ID = "c20a138049b94add92f0f32a41856585"
ALT_ID = "f20a138049b94add92f0f32a41856585"
SOL = "TEST-IT-2027-004"


def fixture(root: Path):
    request = root / "request.txt"
    case = root / "request.case.json"
    receipt = root / "request.receipt.json"
    request.write_text(
        free_draft(assumptions=["The response deadline has not changed."]),
        encoding="utf-8",
    )
    for file in (request,):
        file.chmod(0o600)
    import_request(str(request), str(case), str(receipt), imported_at=NOW)
    working = root / "private"
    working.mkdir(mode=0o700)
    return case, working, read_private_case(case)


def observed(*, action=ID, solicitation=SOL, active="Yes", stamp=None, private=None):
    return {
        "source_url": SEARCH_URL,
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
        "observed_at": (stamp or NOW).isoformat(),
        "payload_sha256": "a" * 64,
        "response_sha256": "b" * 64,
        "pagination": {"complete": True, "total_records": 1, "returned_records": 1,
                       "limit": 100, "offset": 0},
        "record": {
            "noticeId": action, "solicitationNumber": solicitation,
            "active": active, "postedDate": "10/27/2026",
            "private_contact": private,
        },
        "resource_links": [],
    }


def live_style_capture(case, working, *, api=None):
    def fetcher(**kwargs):
        assert kwargs["solicitation_number"] == SOL
        assert kwargs["api_key"] == "FAKE_SECRET"
        assert kwargs["max_response_bytes"] == 2 * 1024 * 1024
        return api or observed(private="CONTACT_MUST_NOT_BE_RETAINED")
    result = observe_scoped_case(
        case, solicitation_number=SOL, posted_from="10/20/2026",
        posted_to="10/27/2026", api_key="FAKE_SECRET", private_dir=working,
        now=NOW, fetcher=fetcher,
    )
    path = working / ("case-" + result["case_tag"]) / result["private_observation_file"]
    return result, path, json.loads(path.read_text(encoding="utf-8"))


class ScopedSAMTests(unittest.TestCase):
    def test_api_candidate_is_bounded_private_and_never_approves_history_or_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_file, root, case = fixture(Path(tmp))
            outcome, path, capture = live_style_capture(case, root)
            self.assertEqual(outcome["status"], "SCOPED_SAM_SOURCE_OBSERVED_REVIEW_REQUIRED")
            self.assertTrue(outcome["api_record_matches_solicitation"])
            self.assertTrue(outcome["selected_notice_matches_latest_api"])
            self.assertFalse(outcome["history_completion_verified"])
            self.assertFalse(outcome["customer_release_authorized"])
            self.assertFalse(outcome["external_send_authorized"])
            self.assertFalse(outcome["payment_authorized"])
            raw = path.read_text()
            for sensitive in ("CONTACT_MUST_NOT_BE_RETAINED", "FAKE_SECRET", "buyer@example.com"):
                self.assertNotIn(sensitive, raw)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o077, 0)
            self.assertEqual(verify_scoped_capture(case, capture, now=NOW)["record"]["noticeId"], ID)
            self.assertEqual(path.read_bytes(), path.read_bytes())
            newout, _, _ = live_style_capture(case, root)
            self.assertEqual(outcome, newout)
            self.assertFalse(any(p.name.endswith(".sqlite") for p in root.rglob("*")))
            self.assertFalse(any(p.name.endswith(".csv") for p in root.rglob("*")))

    def test_current_source_may_differ_from_original_but_remains_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root, case = fixture(Path(tmp))
            result, _, capture = live_style_capture(case, root, api=observed(action=ALT_ID))
            self.assertFalse(result["selected_notice_matches_latest_api"])
            self.assertFalse(result["history_completion_verified"])
            with self.assertRaisesRegex(ScopedSourceBlocked, "family history"):
                bind_reviewed_scoped_case(case, capture, private_dir=root, now=NOW)

    def test_stale_future_inactive_wrong_family_and_invalid_response_block(self):
        for bad in (
            observed(stamp=NOW - timedelta(minutes=6)),
            observed(stamp=NOW + timedelta(seconds=3)),
            observed(active="No"),
            observed(solicitation="OTHER-FAMILY"),
            {**observed(), "pagination": {"complete": False, "total_records": 1,
                                           "returned_records": 1, "limit": 100, "offset": 0}},
        ):
            with self.subTest(case=str(bad)[:70]), tempfile.TemporaryDirectory() as tmp:
                _, root, case = fixture(Path(tmp))
                with self.assertRaises(ScopedSourceBlocked):
                    live_style_capture(case, root, api=bad)
                self.assertFalse(any(root.iterdir()))

    def test_capture_is_bound_to_original_request_and_exact_unmodified_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root, case = fixture(Path(tmp))
            _, path, capture = live_style_capture(case, root)
            modified = copy.deepcopy(capture)
            modified["customer_release_authorized"] = True
            with self.assertRaises(ScopedSourceBlocked):
                verify_scoped_capture(case, modified, now=NOW)
            modified = copy.deepcopy(capture)
            modified["capture_sha256"] = "0" * 64
            with self.assertRaises(ScopedSourceBlocked):
                verify_scoped_capture(case, modified, now=NOW)
            changed_case = copy.deepcopy(case)
            changed_case["assumptions"][0]["text"] = "Different question entirely."
            with self.assertRaisesRegex(ScopedSourceBlocked, "different original request"):
                verify_scoped_capture(changed_case, capture, now=NOW)
            with self.assertRaises(ScopedSourceBlocked):
                verify_scoped_capture(case, capture, now=NOW + timedelta(hours=25))
            self.assertIn("buyer@example.com", json.dumps(case))
            self.assertNotIn("buyer@example.com", path.read_text())

    def test_history_must_be_separately_reviewed_before_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root, case = fixture(Path(tmp))
            _, _, candidate = live_style_capture(case, root)
            with self.assertRaises(ScopedSourceBlocked):
                bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)
            case["packet"]["history_action_ids"] = [ID]
            with self.assertRaises(ScopedSourceBlocked):
                bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)
            source_url = "https://sam.gov/opp/" + ID + "/view"
            review_original = Path(tmp) / "manual-history-page.txt"
            review_original.write_bytes(b"FAKE OFFLINE SAM history listing: one exact action " + ID.encode())
            review_original.chmod(0o600)
            retained = retain_review_source(
                case, original_file=review_original,
                source_url=source_url, private_dir=root, observed_at=NOW,
            )
            case["packet"]["history_receipts"] = [
                make_history_receipt(
                    [ID], source_url=source_url,
                    observed_at=NOW.isoformat(), source_surface="SAM_HISTORY",
                    payload={
                        "family": {"solicitation_number": SOL},
                        "manual_review": {
                            "scope": "COMPLETE_ACTION_SET",
                            "source_sha256": retained["source_sha256"],
                            "reviewer_id": "TEST_REVIEWER_NOT_REAL",
                            "reviewed_at": NOW.isoformat(),
                            "review_reference": "synthetic-offline-review-1",
                        },
                    },
                )
            ]
            updated, transition = bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)
            self.assertEqual(transition["status"], "CURRENT_API_BOUND_REMAINING_EVIDENCE_REVIEW_REQUIRED")
            self.assertFalse(transition["customer_release_authorized"])
            self.assertEqual(updated["packet"]["current_action_id"], ID)
            self.assertEqual(updated["packet"]["family_status"], "ACTIVE")
            self.assertEqual(updated["assumptions"][0]["evidence_state"], "UNPROVEN")
            self.assertFalse(evaluate_delivery_readiness(updated, now=NOW).eligible)
            self.assertEqual(updated["packet"]["manifest_receipts"], [])
            self.assertNotIn("FAKE_SECRET", json.dumps(updated))
            # Retained history metadata is untrusted. Extra authority claims,
            # duplicate keys, swapped names, and stale originals must block.
            original = root / ("case-" + hashlib.sha256(case["case_id"].encode()).hexdigest()[:24])
            receipt_file = original / ("public-source-" + retained["source_sha256"] + ".bin.receipt.json")
            safe_bytes = receipt_file.read_bytes()
            safe_metadata = json.loads(safe_bytes)
            bad_receipts = [
                {**safe_metadata, "payment_authorized": True},
                {**safe_metadata, "retained_filename": "public-source-" + "f" * 64 + ".bin"},
                {**safe_metadata, "observed_at": (NOW - timedelta(days=9)).isoformat()},
            ]
            for value in bad_receipts:
                receipt_file.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ScopedSourceBlocked):
                    bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)
            # Duplicate JSON keys must not be silently resolved using last-wins semantics.
            duplicate = safe_bytes.decode().replace(
                '"source_sha256":', '"source_sha256": "' + "a" * 64 + '", "source_sha256":', 1
            )
            receipt_file.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(ScopedSourceBlocked):
                bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)
            receipt_file.write_bytes(safe_bytes)
            self.assertEqual(
                bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)[1]["status"],
                "CURRENT_API_BOUND_REMAINING_EVIDENCE_REVIEW_REQUIRED"
            )
            # A forged reviewer claim cannot compensate for missing original bytes.
            original = root / ("case-" + hashlib.sha256(case["case_id"].encode()).hexdigest()[:24])
            retained_file = original / ("public-source-" + retained["source_sha256"] + ".bin")
            retained_file.chmod(0o600)
            retained_file.write_bytes(b"TAMPERED HISTORY SOURCE")
            with self.assertRaises(ScopedSourceBlocked):
                bind_reviewed_scoped_case(case, candidate, private_dir=root, now=NOW)

    def test_case_url_must_be_first_party_and_free_intake_unmodified(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root, case = fixture(Path(tmp))
            for change in (
                {"intake": {**case["intake"], "public_opportunity": "https://sam.gov.evil.example/opp/" + ID + "/view"}},
                {"intake": {**case["intake"], "requested_offer": "PAID"}},
                {"intake": {**case["intake"], "public_only_confirmation": False}},
            ):
                changed = {**case, **change}
                with self.subTest(change=change), self.assertRaises(ScopedSourceBlocked):
                    live_style_capture(changed, root)
            self.assertFalse(any(root.iterdir()))

    def test_one_public_file_can_be_retained_without_publisher_or_history_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "official.pdf"
            raw = b"%PDF-1.4\nFAKE_PUBLIC_DOCUMENT\n" * 10
            original.write_bytes(raw)
            original.chmod(0o600)
            _, root, case = fixture(Path(tmp))
            result = retain_review_source(
                case, original_file=original,
                source_url="https://sam.gov/opp/" + ID + "/view", private_dir=root, observed_at=NOW,
            )
            self.assertEqual(result["source_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(result["publisher_authenticity_verified"])
            self.assertFalse(result["history_completeness_verified"])
            self.assertFalse(result["customer_release_authorized"])
            folder = root / ("case-" + result["case_tag"])
            copy_file = folder / ("public-source-" + result["source_sha256"] + ".bin")
            self.assertEqual(copy_file.read_bytes(), raw)
            again = retain_review_source(
                case, original_file=original,
                source_url="https://sam.gov/opp/" + ID + "/view", private_dir=root, observed_at=NOW,
            )
            self.assertEqual(result, again)
            copy_file.chmod(0o600)
            copy_file.write_bytes(b"TAMPERED")
            with self.assertRaises(ValueError):
                retain_review_source(
                    case, original_file=original,
                    source_url="https://sam.gov/opp/" + ID + "/view", private_dir=root, observed_at=NOW,
                )
            self.assertEqual(copy_file.read_bytes(), b"TAMPERED")

    def test_no_key_cli_never_logs_case_or_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_file, root, _ = fixture(Path(tmp))
            env = dict(os.environ)
            env.pop("SAM_API_KEY", None)
            run = subprocess.run(
                [sys.executable, "scripts/prepare_scoped_sam.py", "observe",
                 "--case", str(case_file), "--private-dir", str(root),
                 "--solicitation", SOL, "--posted-from", "10/20/2026",
                 "--posted-to", "10/27/2026"],
                cwd=Path(__file__).resolve().parents[1], env=env,
                capture_output=True, text=True,
            )
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["status"], "SCOPED_SOURCE_REVIEW_BLOCKED")
            self.assertNotIn("buyer@example.com", run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
