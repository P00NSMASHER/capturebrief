"""Small, bounded failure fixtures derived from the real delivery builder."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.delivery_bundle import build_delivery_bundle
from capturebrief_core.delivery_verify import verify_delivery_bundle

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")


class DeliveryVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "delivery.zip"
        self.case = json.loads((ROOT / "fixtures/ready_trace_case.json").read_text())
        self.receipt = build_delivery_bundle(self.case, self.path, now=NOW)
        with zipfile.ZipFile(self.path) as archive:
            self.files = {name: archive.read(name) for name in archive.namelist()}

    def verify(self, **kwargs):
        return verify_delivery_bundle(self.path, expected_sha256=sha(self.path.read_bytes()), **kwargs)

    def rewrite(self, mutate, *, refresh=False, duplicate=False, symlink=False, compression=zipfile.ZIP_DEFLATED):
        files = dict(self.files)
        mutate(files)
        if refresh:
            manifest = json.loads(files["delivery-manifest.json"])
            for row in manifest["files"]:
                row.update(sha256=sha(files[row["path"]]), bytes=len(files[row["path"]]))
            files["delivery-manifest.json"] = encode(manifest)
        with zipfile.ZipFile(self.path, "w", compression=compression) as archive:
            for name, raw in files.items():
                if symlink and name == "brief.md":
                    entry = zipfile.ZipInfo(name)
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(entry, raw)
                else:
                    archive.writestr(name, raw)
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr("brief.md", files["brief.md"])

    def change_json(self, name, fn):
        def mutate(files):
            doc = json.loads(files[name])
            fn(doc)
            files[name] = encode(doc)
        self.rewrite(mutate, refresh=True)

    def assert_failed(self, code, report=None):
        report = self.verify() if report is None else report
        self.assertFalse(report["integrity_verified"])
        self.assertEqual(report["verification_state"], "FAILED")
        self.assertFalse(report["external_send_authorized"])
        self.assertIn(code, report["errors"])

    def test_real_builder_output_matches_separately_retained_receipt(self):
        report = verify_delivery_bundle(
            self.path, expected_sha256=self.receipt["bundle_sha256"],
            expected_case_id=self.case["case_id"],
            expected_case_sha256=self.receipt["case_sha256"],
        )
        self.assertTrue(report["integrity_verified"], report)
        self.assertEqual(report["verified_file_count"], 6)
        self.assertFalse(report["external_send_authorized"])
        self.assertFalse(report["content_review_performed"])
        self.assertFalse(report["source_currentness_rechecked"])
        self.assertFalse(report["reference_origin_authenticated"])

    def test_wrong_outer_digest_is_rejected_before_archive_parsing(self):
        self.assert_failed("BUNDLE_SHA256_MISMATCH", verify_delivery_bundle(self.path, expected_sha256="0" * 64))

    def test_json_receipt_renamed_zip_is_not_a_delivery(self):
        self.path.write_bytes(encode(self.receipt))
        self.assert_failed("ARCHIVE_READ_FAILED")

    def test_changed_payload_cannot_hide_behind_recalculated_outer_digest(self):
        self.rewrite(lambda files: files.update({"brief.md": b"changed brief"}))
        self.assert_failed("PAYLOAD_FINGERPRINT_MISMATCH")

    def test_missing_member_is_rejected(self):
        self.rewrite(lambda files: files.pop("decision-evidence.html"))
        self.assert_failed("ARCHIVE_FILE_SET_MISMATCH")

    def test_extra_raw_case_is_rejected(self):
        self.rewrite(lambda files: files.update({"case.json": b"{}"}))
        self.assert_failed("ARCHIVE_FILE_SET_MISMATCH")

    def test_duplicate_archive_member_is_rejected(self):
        self.rewrite(lambda files: None, duplicate=True)
        self.assert_failed("DUPLICATE_ARCHIVE_MEMBER")

    def test_manifest_must_cover_each_payload_once(self):
        def mutate(doc):
            doc["files"][1] = dict(doc["files"][0])
        self.change_json("delivery-manifest.json", mutate)
        self.assert_failed("PACKAGE_MANIFEST_INVALID")

    def test_manifest_boolean_size_is_not_an_integer_receipt(self):
        def mutate(files):
            doc = json.loads(files["delivery-manifest.json"])
            doc["files"][0]["bytes"] = True
            files["delivery-manifest.json"] = encode(doc)
        self.rewrite(mutate)
        self.assert_failed("PACKAGE_MANIFEST_INVALID")

    def test_duplicate_json_member_is_rejected(self):
        def mutate(files):
            original = files["delivery-manifest.json"].decode()
            files["delivery-manifest.json"] = ('{"schema_version":"1.0",' + original.lstrip()[1:]).encode()
        self.rewrite(mutate)
        self.assert_failed("PACKAGE_MANIFEST_INVALID")

    def test_nonfinite_json_is_rejected(self):
        def mutate(files):
            doc = json.loads(files["decision-summary.json"])
            doc["unexpected"] = float("nan")
            files["decision-summary.json"] = encode(doc)
        self.rewrite(mutate, refresh=True)
        self.assert_failed("PACKAGE_MANIFEST_INVALID")

    def test_mixed_case_ids_are_rejected_even_when_member_hashes_match(self):
        self.change_json("decision-summary.json", lambda doc: doc.update(case_id="OTHER-CASE"))
        self.assert_failed("PACKAGE_IDENTITY_MISMATCH")

    def test_mixed_case_fingerprints_are_rejected(self):
        self.change_json("decision-summary.json", lambda doc: doc.update(case_sha256="0" * 64))
        self.assert_failed("PACKAGE_CASE_HASH_MISMATCH")

    def test_expected_case_checks_reject_wrong_customer_case(self):
        self.assert_failed("EXPECTED_CASE_ID_MISMATCH", self.verify(expected_case_id="OTHER-CASE"))
        self.assert_failed("EXPECTED_CASE_SHA256_MISMATCH", self.verify(expected_case_sha256="0" * 64))

    def test_mixed_review_times_are_rejected(self):
        self.change_json("decision-summary.json", lambda doc: doc.update(evaluated_at="2020-01-01T00:00:00Z"))
        self.assert_failed("PACKAGE_EVALUATION_TIME_MISMATCH")

    def test_tampered_watch_baseline_is_rejected(self):
        self.change_json("watch-baseline.json", lambda doc: doc.update(baseline_sha256="0" * 64))
        self.assert_failed("BASELINE_SHA256_MISMATCH")

    def test_ready_label_never_grants_send_authority(self):
        self.change_json("decision-summary.json", lambda doc: doc.update(external_send_authorized=True))
        self.assert_failed("PACKAGE_SEND_BOUNDARY_INVALID")

    def test_unsupported_package_schema_is_rejected(self):
        self.change_json("source-version-manifest.json", lambda doc: doc.update(schema_version="999"))
        self.assert_failed("PACKAGE_SCHEMA_UNSUPPORTED")

    def test_symlink_member_is_rejected_without_extraction(self):
        self.rewrite(lambda files: None, symlink=True)
        self.assert_failed("UNSUPPORTED_ARCHIVE_MEMBER")
        self.assertEqual([p.name for p in self.root.iterdir()], ["delivery.zip"])

    def test_limits_are_enforced_with_small_test_inputs(self):
        for constant, code in (
            ("MAX_BUNDLE_BYTES", "BUNDLE_UNREADABLE_OR_OVER_LIMIT"),
            ("MAX_MEMBER_BYTES", "ARCHIVE_MEMBER_OVER_LIMIT"),
            ("MAX_EXPANDED_BYTES", "EXPANDED_ARCHIVE_OVER_LIMIT"),
        ):
            with self.subTest(limit=constant), patch("capturebrief_core.delivery_verify." + constant, 10):
                self.assert_failed(code)

    def test_invalid_expected_digest_and_missing_file_fail_closed(self):
        for expected in (None, "", "ABC", "A" * 64):
            self.assert_failed("EXPECTED_BUNDLE_SHA256_INVALID", verify_delivery_bundle(self.path, expected_sha256=expected))
        self.assert_failed("BUNDLE_UNREADABLE_OR_OVER_LIMIT", verify_delivery_bundle(self.root / "missing", expected_sha256="0" * 64))

    def test_verification_is_read_only(self):
        before = self.path.read_bytes()
        report = self.verify()
        self.assertTrue(report["integrity_verified"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([p.name for p in self.root.iterdir()], ["delivery.zip"])

    def test_real_verify_command_returns_nonzero_on_mismatch(self):
        def run(expected):
            return subprocess.run([sys.executable, "-m", "capturebrief_core.trace_cli", "verify-bundle",
                str(self.path), "--expected-sha256", expected], cwd=ROOT,
                capture_output=True, text=True, timeout=30)
        good = run(self.receipt["bundle_sha256"])
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)["integrity_verified"])
        bad = run("0" * 64)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stdout)["integrity_verified"])

    def test_bundle_and_receipt_can_be_kept_as_separate_files(self):
        target = self.root / "cli-delivery.zip"
        receipt_path = self.root / "cli-receipt.json"
        with receipt_path.open("w") as receipt_stream:
            result = subprocess.run([sys.executable, "-m", "capturebrief_core.trace_cli", "bundle",
                str(ROOT / "fixtures/ready_trace_case.json"), "-o", str(target)], cwd=ROOT,
                stdout=receipt_stream, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(receipt_path.read_text())
        self.assertTrue(zipfile.is_zipfile(target))
        self.assertTrue(receipt["artifact_verification"]["integrity_verified"])
        self.assertEqual(receipt["bundle_sha256"], sha(target.read_bytes()))

    def test_bundle_command_rejects_input_path_aliases(self):
        source = self.root / "case.json"
        original = (ROOT / "fixtures/ready_trace_case.json").read_bytes()
        source.write_bytes(original)
        aliases = [self.root / "hardlink.zip"]
        os.link(source, aliases[0])
        symlink = self.root / "symlink.zip"
        try:
            symlink.symlink_to(source)
        except OSError as exc:
            # Standard Windows sessions cannot create symbolic links unless
            # Developer Mode or SeCreateSymbolicLinkPrivilege is enabled.
            if not (os.name == "nt" and getattr(exc, "winerror", None) == 1314):
                raise
        else:
            aliases.append(symlink)
        for alias in aliases:
            result = subprocess.run([sys.executable, "-m", "capturebrief_core.trace_cli", "bundle",
                str(source), "-o", str(alias), "--overwrite"], cwd=ROOT,
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
