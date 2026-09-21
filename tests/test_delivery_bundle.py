from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.delivery_bundle import build_delivery_bundle, build_delivery_files

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,21,17,30,tzinfo=timezone.utc)


def ready_case():
    return json.loads((ROOT/"fixtures"/"ready_trace_case.json").read_text(encoding="utf-8"))


class DeliveryBundleTests(unittest.TestCase):
    def test_ready_case_builds_buyer_safe_bundle(self):
        case=ready_case()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"delivery.zip"
            result=build_delivery_bundle(case,target,now=NOW)
            self.assertEqual(result["release_state"],"READY_FOR_HUMAN_RELEASE")
            self.assertEqual(result["trace_state"],"TRACE_COMPLETE")
            self.assertTrue(target.exists())
            self.assertEqual(result["bundle_sha256"],hashlib.sha256(target.read_bytes()).hexdigest())
            with zipfile.ZipFile(target) as zf:
                names=set(zf.namelist())
                self.assertEqual(names,{
                    "brief.md","decision-evidence.md","decision-evidence.html",
                    "decision-summary.json","source-version-manifest.json",
                    "delivery-manifest.json",
                })
                manifest=json.loads(zf.read("delivery-manifest.json"))
                self.assertFalse(manifest["contains_raw_case"])
                self.assertFalse(manifest["contains_restricted_source_bytes"])
                for row in manifest["files"]:
                    data=zf.read(row["path"])
                    self.assertEqual(row["sha256"],hashlib.sha256(data).hexdigest())
                    self.assertEqual(row["bytes"],len(data))
                source_manifest=json.loads(zf.read("source-version-manifest.json"))
                self.assertEqual(source_manifest["case_id"],case["case_id"])
                self.assertNotIn("text",source_manifest["snapshots"][0])
                self.assertNotIn("intake",source_manifest)

    def test_bundle_is_deterministic_for_same_case_and_time(self):
        case=ready_case()
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"a.zip"; b=Path(d)/"b.zip"
            ra=build_delivery_bundle(case,a,now=NOW)
            rb=build_delivery_bundle(case,b,now=NOW)
            self.assertEqual(ra["bundle_sha256"],rb["bundle_sha256"])
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_untraced_case_is_refused(self):
        case=ready_case()
        case.pop("decision_trace")
        with self.assertRaises(ValueError):
            build_delivery_files(case,now=NOW)

    def test_trace_tamper_is_refused(self):
        case=ready_case()
        case["decision_trace"]["reviews"][0]["citations"][0]["quote"]="rewritten"
        with self.assertRaises(ValueError):
            build_delivery_files(case,now=NOW)

    def test_synthetic_trace_is_refused(self):
        case=ready_case()
        case["decision_trace"]["synthetic"]=True
        with self.assertRaises(ValueError):
            build_delivery_files(case,now=NOW)

    def test_existing_output_requires_explicit_overwrite(self):
        case=ready_case()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"delivery.zip"
            target.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                build_delivery_bundle(case,target,now=NOW)

    def test_bundle_contains_no_raw_case_or_customer_intake(self):
        case=ready_case()
        case["intake"]={"email":"customer@example.com","company":"Example Buyer"}
        files=build_delivery_files(case,now=NOW)
        combined=b"\n".join(files.values())
        self.assertNotIn(b"customer@example.com",combined)
        self.assertNotIn(b"Example Buyer",combined)


if __name__=="__main__":
    unittest.main()
