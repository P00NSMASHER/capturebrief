"""Exercise the real operator command, not only its underlying builder."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "ready_trace_case.json"


def command(*args):
    return subprocess.run(
        [sys.executable, "-m", "capturebrief_core.trace_cli", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


class DeliveryCommandTests(unittest.TestCase):
    def test_bundle_command_leaves_a_real_zip_and_prints_separate_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "delivery.zip"
            result = command("bundle", FIXTURE, "-o", target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(zipfile.is_zipfile(target),
                            "The successful bundle command replaced its ZIP with JSON")
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["bundle_sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(receipt["bundle_bytes"], target.stat().st_size)
            self.assertFalse(receipt["external_send_authorized"])
            with zipfile.ZipFile(target) as archive:
                self.assertIn("decision-evidence.html", archive.namelist())
                self.assertIsNone(archive.testzip())

    def test_input_case_cannot_be_used_as_output_even_with_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "case.json"
            original = FIXTURE.read_bytes()
            source.write_bytes(original)
            result = command("bundle", source, "-o", source, "--overwrite")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_bytes(), original)

    def test_existing_delivery_stays_unchanged_without_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "delivery.zip"
            target.write_bytes(b"keep existing delivery")
            result = command("bundle", FIXTURE, "-o", target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"keep existing delivery")

    def test_explicit_overwrite_produces_a_zip_not_a_json_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "delivery.zip"
            target.write_bytes(b"old delivery")
            result = command("bundle", FIXTURE, "-o", target, "--overwrite")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(zipfile.is_zipfile(target))
            self.assertEqual(json.loads(result.stdout)["bundle_sha256"],
                             hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
