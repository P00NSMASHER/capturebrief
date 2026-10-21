"""Cross-stage offline acceptance: fictional buyer drafts, provider, source and watch."""
from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.batch_import_request_drafts import batch_import
from scripts.process_private_order_queue import process_private_order_queue
from scripts.save_private_checkout_association import save_private_checkout_association
from scripts.inspect_private_order_fulfillment import inspect_fulfillment, source_catalog_preflight
from tests.test_private_order_os import stripe_records, provider_for
from tests.test_request_draft import draft

NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


class PrivateOrderPipelineTests(unittest.TestCase):
    def setup_dirs(self, td):
        root = Path(td)
        inbox, cases, assoc, orders = [root / x for x in ("inbox","cases","associations","orders")]
        for p in (inbox,cases,assoc,orders):
            p.mkdir()
        db = orders / "registry.sqlite"
        return inbox,cases,assoc,db

    def build_association(self, inbox, cases, assoc, *, message=None,
                          suffix="REGISTRATION", filename="request.txt"):
        (inbox/filename).write_text(message or draft(), encoding="utf-8")
        result = batch_import(inbox,cases)
        self.assertFalse(result["blocked"])
        digest = hashlib.sha256((inbox/filename).read_bytes()).hexdigest()
        payload = {
            "schema": "capturebrief-private-checkout-association-v1",
            "request_sha256": digest,
            "checkout_session_id": "cs_live_" + suffix,
        }
        (assoc/f"request-{digest}.order.json").write_text(
            json.dumps(payload), encoding="utf-8",
        )
        return digest

    def synthetic(self, cases, assoc, db, *, records=None, preview=False):
        provider, calls = provider_for(records or stripe_records("REGISTRATION"))
        report = process_private_order_queue(
            cases, assoc, db, preview_only=preview,
            api_key="sk_live_FICTIONAL_TEST_KEY",
            synthetic_provider=provider, synthetic_test_mode=True,
        )
        return report, calls

    def test_end_to_end_private_preview_registration_and_source_watch_holds(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db = self.setup_dirs(td)
            self.build_association(inbox,cases,assoc)
            initial = {p.name:p.read_bytes() for p in cases.iterdir()}
            preview,calls = self.synthetic(cases,assoc,db,preview=True)
            self.assertEqual(preview["preview_ready"],1)
            self.assertEqual(preview["registered"],0)
            self.assertEqual(preview["blocked"],0)
            self.assertEqual(calls, [])
            self.assertFalse(db.exists())
            paid, calls = self.synthetic(cases,assoc,db)
            self.assertEqual(paid["registered"],1)
            self.assertEqual(len(calls),4)
            self.assertEqual(paid["provider_mode"],"SYNTHETIC_TEST_ONLY")
            self.assertFalse(paid["any_customer_release_authorized"])
            again,_ = self.synthetic(cases,assoc,db)
            self.assertEqual(again["reused"],1)
            self.assertEqual(again["registered"],0)
            summary = inspect_fulfillment(cases,db,now=NOW)
            self.assertEqual(summary["status"],"PRIVATE_ORDER_FULFILLMENT_REVIEW_PENDING")
            self.assertEqual(summary["source_catalog"]["requested_fiscal_year"],2027)
            self.assertEqual(summary["source_catalog"]["status"],"SOURCE_CATALOG_REFRESH_REVIEW_REQUIRED")
            self.assertEqual(summary["orders"][0]["watch_state"],"NOT_STARTED")
            self.assertEqual(summary["orders"][0]["delivery_state"],"NOT_VERIFIED")
            self.assertIn("FY2027_ARCHIVE_CATALOG_RECERTIFICATION",
                          summary["orders"][0]["pending_evidence"])
            self.assertFalse(summary["orders"][0]["payment_currently_authenticated_for_start"])
            self.assertFalse(summary["external_send_authorized"])
            self.assertFalse(summary["customer_release_authorized"])
            self.assertEqual(initial,{p.name:p.read_bytes() for p in cases.iterdir()})
            text = json.dumps(summary) + json.dumps(paid)
            for secret in ("buyer@example.com","https://sam.gov/opp/",
                           "cs_live_REGISTRATION","pi_REGISTRATION",str(cases)):
                self.assertNotIn(secret,text)

    def test_paid_case_collision_is_reported_without_second_order(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db = self.setup_dirs(td)
            self.build_association(inbox,cases,assoc)
            self.build_association(inbox,cases,assoc,
                message=draft(company="Another Fictional Buyer"),
                filename="other.txt")
            check,_ = self.synthetic(cases,assoc,db)
            self.assertEqual(check["registered"],1)
            self.assertEqual(check["blocked"],1)
            self.assertFalse(check["any_customer_release_authorized"])
            view = inspect_fulfillment(cases,db,now=NOW)
            self.assertEqual(len(view["orders"]),1)

    def test_refund_after_first_observation_never_grants_research_authority(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db = self.setup_dirs(td)
            self.build_association(inbox,cases,assoc)
            first,_ = self.synthetic(cases,assoc,db)
            self.assertEqual(first["registered"],1)
            with closing(sqlite3.connect(db)) as conn:
                original = conn.execute(
                    "SELECT observation_sha256,created_at,payment_state FROM orders"
                ).fetchone()
            records=list(stripe_records("REGISTRATION"))
            records[2]["refunded"]=True
            records[2]["amount_refunded"]=14900
            replay,_=self.synthetic(cases,assoc,db,records=records)
            self.assertEqual(replay["blocked"],1)
            result=inspect_fulfillment(cases,db,now=NOW)
            self.assertEqual(result["status"], "PRIVATE_ORDER_FULFILLMENT_BLOCKED")
            self.assertEqual(result["orders"][0]["status"], "PAYMENT_RECHECK_BLOCKED")
            self.assertTrue(result["orders"][0]["payment_recheck_blocked"])
            self.assertIn("STRIPE_PAYMENT_RECHECK_BLOCKED",
                          result["orders"][0]["pending_evidence"])
            self.assertFalse(result["orders"][0]["payment_currently_authenticated_for_start"])
            self.assertEqual(result["orders"][0]["research_state"] if "research_state" in result["orders"][0] else "NOT_STARTED","NOT_STARTED")
            self.assertFalse(result["customer_release_authorized"])
            with closing(sqlite3.connect(db)) as conn:
                after = conn.execute(
                    "SELECT observation_sha256,created_at,payment_state FROM orders"
                ).fetchone()
            self.assertEqual(original, after, "Earlier paid observation must remain intact")

    def test_invalid_association_and_damaged_case_block_without_provider_reads(self):
        for kind in ("wrong_sha","duplicate_json_key","damaged_case"):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
                inbox,cases,assoc,db=self.setup_dirs(td)
                digest=self.build_association(inbox,cases,assoc)
                file=assoc/f"request-{digest}.order.json"
                if kind=="wrong_sha":
                    value=json.loads(file.read_text())
                    value["request_sha256"]="0"*64
                    file.write_text(json.dumps(value))
                elif kind=="duplicate_json_key":
                    file.write_text('{"schema":"x","schema":"y"}')
                else:
                    next(cases.glob("*.case.json")).write_text("synthetic tamper")
                checked,calls=self.synthetic(cases,assoc,db)
                self.assertEqual(checked["blocked"],1)
                self.assertEqual(calls,[])
                self.assertFalse(db.exists())

    def test_source_preflight_never_turns_catalog_listing_into_source_truth(self):
        old=source_catalog_preflight(now=datetime(2026,9,21,tzinfo=timezone.utc))
        self.assertEqual(old["requested_fiscal_year"],2026)
        self.assertEqual(old["status"],"APPROVED_CATALOG_SCOPE_ONLY_NOT_SOURCE_COVERAGE")
        self.assertFalse(old["full_history_coverage_approved"])
        current=source_catalog_preflight(now=NOW)
        self.assertEqual(current["requested_fiscal_year"],2027)
        self.assertEqual(current["approved_catalog_current_through_fy"],2026)
        self.assertFalse(current["publisher_originals_authenticated"])
        self.assertFalse(current["customer_release_authorized"])

    def test_fulfillment_read_only_and_case_mutation_detected(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            self.build_association(inbox,cases,assoc)
            self.synthetic(cases,assoc,db)
            old={p.name:p.read_bytes() for p in cases.iterdir()}
            self.assertEqual(inspect_fulfillment(cases,db,now=NOW)["blocked"],0)
            self.assertEqual(old,{p.name:p.read_bytes() for p in cases.iterdir()})
            case=next(cases.glob("*.case.json"))
            case.write_text('{"tampered":true}',encoding="utf-8")
            r=inspect_fulfillment(cases,db,now=NOW)
            self.assertEqual(r["status"],"PRIVATE_ORDER_FULFILLMENT_BLOCKED")
            self.assertEqual(r["blocked"],1)
            self.assertFalse(r["external_send_authorized"])

    def test_malformed_checkout_mapping_never_masquerades_as_empty_queue(self):
        # A user may save a JSON file with an incomplete digest, old name,
        # or .tmp suffix. It must be visible as BLOCKED, not an empty inbox.
        for filename in (
            "request-too-short.order.json",
            "request-" + ("a" * 64) + ".order.json.tmp",
            "Request-" + ("b" * 64) + ".order.json",
            "request-" + ("c" * 64) + ".order.jsn",
            "wrongprefix.order.json",
        ):
            with self.subTest(filename_kind=filename.rsplit(".", 1)[-1]), tempfile.TemporaryDirectory() as td:
                inbox,cases,assoc,db=self.setup_dirs(td)
                invalid=assoc/filename
                invalid.write_text('{"untrusted":"fictional"}',encoding="utf-8")
                before=invalid.read_bytes()
                check, calls=self.synthetic(cases,assoc,db,preview=True)
                self.assertEqual(check["status"],"PRIVATE_ORDER_QUEUE_BLOCKED")
                self.assertEqual(check["blocked"],1)
                self.assertEqual(check["unexpected_association_entries"],1)
                self.assertEqual(check["input_associations"],1)
                self.assertEqual(check["registered"],0)
                self.assertFalse(db.exists())
                self.assertEqual(calls,[])
                self.assertEqual(invalid.read_bytes(),before)
                self.assertNotIn(filename,json.dumps(check))

    def test_malformed_checkout_mapping_blocks_with_valid_neighbor_without_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            self.build_association(inbox,cases,assoc)
            stale=assoc/"request-pending.order.json.tmp"
            stale.write_text("partial fictional association",encoding="utf-8")
            check,calls=self.synthetic(cases,assoc,db,preview=True)
            self.assertEqual(check["preview_ready"],1)
            self.assertEqual(check["blocked"],1)
            self.assertEqual(check["unexpected_association_entries"],1)
            self.assertEqual(check["status"],"PRIVATE_ORDER_QUEUE_BLOCKED")
            self.assertFalse(db.exists())
            self.assertEqual(calls,[])
            self.assertFalse(check["any_customer_release_authorized"])

    def test_unrelated_notes_are_ignored_not_false_orders(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            (assoc/"notes.txt").write_text("fictional private operator notes",encoding="utf-8")
            (assoc/"readme.pdf").write_bytes(b"fictional")
            check,calls=self.synthetic(cases,assoc,db,preview=True)
            self.assertEqual(check["status"],"PRIVATE_ORDER_QUEUE_EMPTY")
            self.assertEqual(check["ignored_non_association_entries"],2)
            self.assertEqual(check["unexpected_association_entries"],0)
            self.assertEqual(check["blocked"],0)
            self.assertEqual(calls,[])
            self.assertFalse(db.exists())

    def test_safe_association_builder_creates_and_reuses_one_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            digest=self.build_association(inbox,cases,assoc)
            manual=assoc/f"request-{digest}.order.json"
            manual.unlink()
            case=cases/f"request-{digest}.case.json"
            before={p.name:p.read_bytes() for p in cases.iterdir()}
            saved=save_private_checkout_association(case,assoc,"cs_live_REGISTRATION")
            self.assertEqual(saved["status"],"PRIVATE_ASSOCIATION_SAVED_UNVERIFIED")
            self.assertFalse(saved["stripe_payment_verified"])
            self.assertFalse(saved["external_send_authorized"])
            self.assertFalse(saved["customer_release_authorized"])
            original=manual.read_bytes()
            again=save_private_checkout_association(case,assoc,"cs_live_REGISTRATION")
            self.assertEqual(again["status"],"PRIVATE_ASSOCIATION_ALREADY_SAVED_UNVERIFIED")
            self.assertEqual(original,manual.read_bytes())
            preview,calls=self.synthetic(cases,assoc,db,preview=True)
            self.assertEqual(preview["preview_ready"],1)
            self.assertEqual(calls,[])
            self.assertFalse(db.exists())
            self.assertEqual(before,{p.name:p.read_bytes() for p in cases.iterdir()})
            self.assertFalse(list(assoc.glob("*.lock")))
            self.assertNotIn("cs_live_REGISTRATION",json.dumps(saved))

    def test_builder_rejects_same_checkout_session_assigned_to_two_cases(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            first_sha=self.build_association(inbox,cases,assoc)
            first=assoc/f"request-{first_sha}.order.json"
            first.unlink()
            case_first=cases/f"request-{first_sha}.case.json"
            save_private_checkout_association(case_first,assoc,"cs_live_ONEPAYMENT")
            self.build_association(inbox,cases,assoc,
                filename="second.txt",
                message=draft(company="Fictional Other Buyer"))
            second=next(p for p in cases.glob("*.case.json") if p != case_first)
            previous={p.name:p.read_bytes() for p in assoc.iterdir()}
            with self.assertRaisesRegex(ValueError,"another request"):
                save_private_checkout_association(second,assoc,"cs_live_ONEPAYMENT")
            self.assertEqual(previous,{p.name:p.read_bytes() for p in assoc.iterdir()})
            self.assertFalse(db.exists())

    def test_builder_conflicting_mapping_or_malformed_neighbor_cannot_overwrite(self):
        for issue in ("conflict","malformed_neighbor","altered_case"):
            with self.subTest(issue=issue),tempfile.TemporaryDirectory() as td:
                inbox,cases,assoc,db=self.setup_dirs(td)
                digest=self.build_association(inbox,cases,assoc)
                mapped=assoc/f"request-{digest}.order.json"
                case=cases/f"request-{digest}.case.json"
                if issue=="conflict":
                    attempted="cs_live_WRONG"
                elif issue=="malformed_neighbor":
                    (assoc/"request-missing.order.json.tmp").write_text("unfinished",encoding="utf-8")
                    attempted="cs_live_REGISTRATION"
                else:
                    case.write_text("tampered original synthetic case",encoding="utf-8")
                    attempted="cs_live_REGISTRATION"
                snapshot={p.name:p.read_bytes() for p in assoc.iterdir()}
                with self.assertRaises(ValueError):
                    save_private_checkout_association(case,assoc,attempted)
                self.assertEqual(snapshot,{p.name:p.read_bytes() for p in assoc.iterdir()})
                self.assertFalse(db.exists())

    def test_noninteractive_builder_cli_without_id_does_not_guess_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            digest=self.build_association(inbox,cases,assoc)
            mapping=assoc/f"request-{digest}.order.json"
            mapping.unlink()
            case=cases/f"request-{digest}.case.json"
            run=subprocess.run(
                [sys.executable,str(Path(__file__).resolve().parents[1]
                /"scripts"/"save_private_checkout_association.py"),
                str(case),"--associations-dir",str(assoc)],
                capture_output=True,text=True,input="cs_live_FICTIONAL_TTY\n",
            )
            self.assertEqual(run.returncode,3)
            self.assertFalse(mapping.exists())
            self.assertFalse(db.exists())
            self.assertNotIn("cs_live_FICTIONAL_TTY",run.stdout)
            self.assertNotIn(str(case),run.stdout)

    def test_empty_pipeline_and_no_live_key_do_not_create_registry(self):
        with tempfile.TemporaryDirectory() as td:
            inbox,cases,assoc,db=self.setup_dirs(td)
            out=process_private_order_queue(cases,assoc,db)
            self.assertEqual(out["status"],"PRIVATE_ORDER_QUEUE_EMPTY")
            self.assertFalse(db.exists())
            self.build_association(inbox,cases,assoc)
            env=dict(os.environ)
            env.pop("STRIPE_CAPTUREBRIEF_SECRET_KEY",None)
            run=subprocess.run([
                sys.executable,
                str(Path(__file__).resolve().parents[1]/"scripts/process_private_order_queue.py"),
                "--cases-dir",str(cases),"--associations-dir",str(assoc),
                "--registry",str(db),"--execute"
            ],capture_output=True,text=True,env=env)
            self.assertEqual(run.returncode,3)
            self.assertFalse(db.exists())
            self.assertNotIn("buyer@example.com",run.stdout)
            self.assertNotIn(str(cases),run.stdout)


if __name__=="__main__":
    unittest.main()
