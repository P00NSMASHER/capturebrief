"""Exercise the full TEST intake/review path; synthetic transport is never live evidence."""
import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from scripts.refresh_sam_source_candidate import refresh_candidate
from scripts.run_customer_source_simulation import run
from tests.test_history_index import FIELDS, row
from tests.test_retain_fy2027_candidate import FakeResponse


def original(notices):
    stream = io.StringIO(newline="")
    fields = FIELDS + ["Title", "ResponseDeadLine", "PrimaryContactEmail"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for notice in notices:
        writer.writerow({**row(notice, sol="SIM-" + notice[0]),
                         "Title": "SIMULATED software procurement " + notice[0],
                         "ResponseDeadLine": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
                         "PrimaryContactEmail": "official-contact@example.gov"})
    return stream.getvalue().encode("cp1252")


class CustomerSourceSimulationTests(unittest.TestCase):
    def candidate(self, root):
        for slot, notices, url in (("ACTIVE", ["a"*32, "b"*32], ACTIVE_DOWNLOAD),
                                   ("ARCHIVE:2027", ["c"*32], ARCHIVE_DOWNLOAD.format(fy=2027))):
            data = original(notices)
            refresh_candidate(root, slot=slot, max_bytes=8192,
                              opener=lambda *a, raw=data, final=url, **kw: FakeResponse(contents=raw, url=final))

    def test_three_reviews_keep_real_release_blocked_and_do_not_expose_source_contacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, output = Path(temporary)/"candidate", Path(temporary)/"simulation"
            self.candidate(candidate)
            report = run(candidate, output)
            self.assertTrue(report["passed"])
            self.assertEqual(report["scenario_count"], 3)
            self.assertFalse(report["real_public_transport_used"])
            self.assertFalse(report["live_registry_updated"])
            self.assertFalse(report["customer_delivery_verified"])
            for result in report["results"]:
                self.assertIn("DELIVERY_SYNTHETIC_EVIDENCE", result["production_blocker_codes"])
                self.assertTrue(result["production_builder_rejected"])
                self.assertTrue(result["quote_mutation_rejected"])
                self.assertTrue(result["reservation_scope_matches"])
            for path in output.glob("SIM-*/*"):
                if path.suffix in {".md", ".json", ".txt"}:
                    self.assertNotIn("official-contact@example.gov", path.read_text())
            cases = list(output.glob("SIM-*/SIMULATED-reviewed-case.json"))
            self.assertEqual(len(cases), 3)
            for path in cases:
                self.assertTrue(json.loads(path.read_text())["decision_trace"]["synthetic"])
            feedback = json.loads((output/"SIM-01/SIMULATED-customer-feedback.json").read_text())
            self.assertEqual(len(feedback["personas"]), 2)
            self.assertFalse(feedback["real_customer"])
            self.assertFalse(feedback["customer_satisfaction_measured"])
            self.assertEqual(feedback["acceptance"], "SIMULATED_REVIEW_REQUIRES_SOURCE_COMPLETION")
            self.assertFalse(list(output.rglob("MUST-NOT-EXIST*")))
            with self.assertRaises(ValueError):
                run(candidate, output)

    def test_changed_source_bytes_are_rejected_before_any_customer_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, output = Path(temporary)/"candidate", Path(temporary)/"simulation"
            self.candidate(candidate)
            source = next((candidate/"originals").glob("ACTIVE-*.csv"))
            source.chmod(0o600)
            source.write_bytes(source.read_bytes() + b"unexpected")
            with self.assertRaises(ValueError):
                run(candidate, output)
            self.assertFalse(list(output.rglob("*preview.md")))

    def test_stale_or_future_source_observation_cannot_be_current_simulation_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary)/"candidate"
            self.candidate(candidate)
            for days in (-3, 3):
                output = Path(temporary)/f"simulation-{days}"
                with self.subTest(days=days), self.assertRaises(ValueError):
                    run(candidate, output, now=datetime.now(timezone.utc) + timedelta(days=days))
                self.assertFalse(list(output.rglob("*preview.md")))

    def test_mock_receipt_cannot_claim_real_transport_over_operator_file_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, output = Path(temporary)/"candidate", Path(temporary)/"simulation"
            self.candidate(candidate)
            receipt = next((candidate/"observations").glob("ACTIVE-*.json"))
            changed = json.loads(receipt.read_text())
            changed["synthetic_transport"] = False
            receipt.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                run(candidate, output)
            self.assertFalse(list(output.rglob("*preview.md")))


if __name__ == "__main__":
    unittest.main()
