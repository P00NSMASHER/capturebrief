"""FICTIONAL offline acceptance. No real customer, official-history proof or delivery.

The positive unit case mocks only the existing independent core audit to isolate
this new signed/custody gate. No test should be reported as a LIVE release.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from capturebrief_core.authorization_ledger import reserve_once
from capturebrief_core.accepted_case_release import (
    AcceptedCaseBlocked, canonical, inspect_accepted_case, sha256,
    signature_payload, verify_attestations, _file, _official,
    RECOVERY_SCHEMA, ROLES, SCHEMA, TRUST_SCHEMA,
)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    CRYPTO = True
except ImportError:
    CRYPTO = False

NOW = datetime(2026, 10, 29, 14, 5, tzinfo=timezone.utc)


@unittest.skipUnless(CRYPTO, "Pinned cryptography==46.0.4 required for signed receipt QA")
class AcceptedCaseReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "approved-case"
        self.root.mkdir(mode=0o700)
        self.case = {
            "case_id": "CB-QA-FICTIONAL-NOT-A-CUSTOMER",
            "family_id": "QA-FAMILY-NOT-OFFICIAL",
            "packet": {
                "family_status": "CURRENT",
                "history_action_ids": ["actA", "actB"],
                "artifacts": [{"artifact_id": "res1", "required_for_analysis": True}],
            },
            "decision_trace": {
                "synthetic": True,
                "rule_versions": [{"rule_version_id": "ruleA", "edition": "2026"}],
            },
        }
        self.rows: list[dict] = []
        self.keys = {}
        self.trust = {"schema": TRUST_SCHEMA, "signers": []}
        for role in ROLES:
            key_id = "qa-" + role.lower()
            key = Ed25519PrivateKey.generate()
            self.keys[role] = (key_id, key)
            self.trust["signers"].append({
                "role": role, "key_id": key_id,
                "public_key_base64": base64.b64encode(key.public_key().public_bytes(
                    Encoding.Raw, PublicFormat.Raw)).decode("ascii"),
            })
        self.add("case", "CASE", canonical(self.case))
        self.add("history", "HISTORY", b"FICTIONAL complete source listing",
                 source_url="https://sam.gov/opp/qa-family/view")
        self.add("inventory", "RESOURCE_INVENTORY", b"FICTIONAL all resources",
                 source_url="https://sam.gov/opp/qa-family/view")
        self.add("actionA", "ACTION_ORIGINAL", b"FICTIONAL original notice",
                 source_url="https://sam.gov/opp/actA/view")
        self.add("actionB", "ACTION_ORIGINAL", b"FICTIONAL amendment one",
                 source_url="https://sam.gov/opp/actB/view")
        self.add("res1", "RESOURCE_ORIGINAL", b"FICTIONAL official source bytes",
                 source_url="https://sam.gov/opp/actB/view")
        self.add("ruleA", "INCORPORATED_RULE", b"FICTIONAL rule edition 2026",
                 source_url="https://acquisition.gov/far/qa")
        for ident, kind in (
            ("identity", "BUSINESS_EVIDENCE"), ("inbound", "INBOUND_RECEIPT"),
            ("scope", "SCOPE_AGREEMENT"), ("report", "REPORT"),
            ("report_receipt", "REPORT_RECEIPT"), ("registry", "REGISTRY_SNAPSHOT"),
            ("body", "MESSAGE_BODY"),
        ):
            if kind == "REPORT_RECEIPT":
                receipt = {
                    "case_sha256": sha256(canonical(self.case)),
                    "report_sha256": next(x["sha256"] for x in self.rows if x["id"] == "report"),
                }
                self.add(ident, kind, canonical(receipt))
            else:
                self.add(ident, kind, ("FICTIONAL " + kind).encode())
        self.add("backup", "OFFDEVICE_BACKUP", b"FICTIONAL encrypted backup bytes")
        files_to_restore = {
            x["id"]: x["sha256"] for x in self.rows
            if x["kind"] not in {"OFFDEVICE_BACKUP", "RECOVERY_RECEIPT"}
        }
        recovered = {
            "schema": RECOVERY_SCHEMA,
            "offdevice_backup_sha256": next(x["sha256"] for x in self.rows if x["id"] == "backup"),
            "primary_device_id": "qa-primary",
            "restore_device_id": "qa-independent",
            "key_custodian_id": "qa-external-custodian",
            "restoration_method": "NEW_DEVICE_RETRIEVAL_AND_DECRYPTION",
            "restored_and_verified": True,
            "restored_at": (NOW - timedelta(minutes=30)).isoformat(),
            "restored_files": files_to_restore,
        }
        self.add("recovery", "RECOVERY_RECEIPT", canonical(recovered))
        self.manifest = {
            "schema": SCHEMA, "case_id": self.case["case_id"],
            "family_id": self.case["family_id"], "case_sha256": sha256(canonical(self.case)),
            "files": self.rows,
            "source_closure": {
                "scope": "HUMAN_REVIEWED_COMPLETE_ACTION_SET",
                "collection_mode": "PERMITTED_FIRST_PARTY_SAM_OR_DATA_SERVICES",
                "includes_cancellations_deletions": True,
                "missing_or_unavailable": [],
                "history_file": "history", "resource_inventory_file": "inventory",
                "actions": [
                    {"notice_id": "actA", "type": "SOLICITATION", "original_file": "actionA",
                     "published_at": (NOW-timedelta(days=2)).isoformat()},
                    {"notice_id": "actB", "type": "AMENDMENT", "original_file": "actionB",
                     "amendment_number": "0001", "published_at": (NOW-timedelta(days=1)).isoformat()},
                ],
                "resources": [
                    {"resource_id": "res1", "action_id": "actB", "state": "CURRENT",
                     "original_file": "res1"}
                ],
                "incorporated_sources": [
                    {"rule_version_id": "ruleA", "edition": "2026",
                     "basis_locator": "Section L, fictional", "applicability": "APPLIES",
                     "original_file": "ruleA"}
                ],
            },
            "private_storage": {
                "backup_file": "backup", "recovery_receipt_file": "recovery",
                "approved_by_owner": True, "encrypted_at_rest": True,
                "private_acl_checked": True, "separate_recovery_key_custody": True,
                "approval_reference": "fictional QA approval reference",
                "offdevice_provider_receipt": "fictional QA remote download",
                "key_custodian_id": "qa-external-custodian",
                "primary_device_id": "qa-primary", "restore_device_id": "qa-independent",
                "recovery_completed_at": (NOW-timedelta(minutes=30)).isoformat(),
            },
            "business": {
                "identity_file": "identity", "inbound_receipt_file": "inbound",
                "signed_scope_file": "scope", "canonical_business_key": "domain:example.com",
                "verified_recipient": "buyer@example.com",
                "method": "INDEPENDENT_REGISTRY_AND_CONTROLLED_CHANNEL",
                "identity_verified": True, "scope_accepted": True,
                "verified_at": (NOW-timedelta(hours=4)).isoformat(),
            },
            "report": {
                "report_file": "report", "report_receipt_file": "report_receipt",
                "full_human_review": True, "unresolved_material_conclusions": [],
                "reviewed_at": (NOW-timedelta(hours=1)).isoformat(),
            },
            "delivery": {
                "body_file": "body", "attachment_file": "report",
                "recipient": "buyer@example.com",
                "subject": "Fictional source review",
                "authorization_nonce": "ab" * 16,
                "manual_only": True, "max_sends": 1,
                "external_send_approved": True,
                "expires_at": (NOW + timedelta(hours=20)).isoformat(),
            },
        }
        self.sign()

    def add(self, fid, kind, data, **extra):
        path = self.root / (fid + ".bin")
        path.write_bytes(data)
        if os.name != "nt":
            path.chmod(0o600)
        self.rows.append({
            "id": fid, "kind": kind, "path": path.name, "sha256": sha256(data), **extra
        })

    def sign(self):
        unsigned = {k: v for k, v in self.manifest.items() if k != "attestations"}
        self.manifest["attestations"] = []
        for role in ROLES:
            key_id, private = self.keys[role]
            at = (NOW-timedelta(minutes=5)).isoformat()
            self.manifest["attestations"].append({
                "role": role, "key_id": key_id, "signed_at": at,
                "signature_base64": base64.b64encode(private.sign(
                    signature_payload(unsigned, role, key_id, at))).decode("ascii"),
            })

    def check(self, *, mock_core=True):
        if mock_core:
            with patch("capturebrief_core.accepted_case_release.evaluate_delivery_readiness",
                       return_value=SimpleNamespace(eligible=True)):
                return inspect_accepted_case(self.case, self.manifest,
                    private_root=self.root, trusted_keys=self.trust, now=NOW)
        return inspect_accepted_case(self.case, self.manifest,
            private_root=self.root, trusted_keys=self.trust, now=NOW)

    def reserve(self, ledger_path, *, mock_core=True):
        params = dict(
            case=self.case, private_root=self.root, trusted_keys=self.trust,
            ledger_path=ledger_path, at=NOW,
        )
        if mock_core:
            with patch("capturebrief_core.accepted_case_release.evaluate_delivery_readiness",
                       return_value=SimpleNamespace(eligible=True)):
                return reserve_once(self.manifest, **params)
        return reserve_once(self.manifest, **params)

    def test_cryptographic_case_gate_positive_IS_FICTIONAL_WITH_MOCKED_CORE(self):
        result = self.check()
        self.assertEqual(result["source_action_count"], 2)
        self.assertEqual(result["reviewed_resource_count"], 1)
        self.assertEqual(result["incorporated_source_count"], 1)
        self.assertEqual(len(result["independent_roles_verified"]), 6)
        self.assertFalse(result["external_send_performed"])
        self.assertFalse(result["real_customer_delivery_verified"])

    def test_existing_real_core_rejects_mock_case_for_actual_customer_release(self):
        with self.assertRaises(AcceptedCaseBlocked):
            self.check(mock_core=False)

    def test_tampered_original_and_missing_amendment_block(self):
        (self.root / "actionB.bin").write_bytes(b"TAMPER")
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        (self.root / "actionB.bin").write_bytes(b"FICTIONAL amendment one")
        if os.name != "nt":
            (self.root / "actionB.bin").chmod(0o600)
        self.manifest["source_closure"]["actions"].pop()
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_gsa_latest_action_alone_cannot_clear_history(self):
        self.manifest["source_closure"]["scope"] = "LATEST_ACTIVE_API"
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_current_api_host_cannot_be_relabelled_as_full_history(self):
        for row in self.rows:
            if row["kind"] == "HISTORY":
                row["source_url"] = "https://api.sam.gov/opportunities/v2/search"
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_future_published_amendment_is_rejected(self):
        self.manifest["source_closure"]["actions"][1]["published_at"] = (
            NOW + timedelta(days=2)).isoformat()
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_signed_but_inconsistent_report_receipt_is_rejected(self):
        # New exact bytes + new inventory hash + adjusted restore list can all
        # be signed by FICTIONAL testers, but the report receipt remains
        # inconsistent with the actual report and must still fail.
        path = self.root / "report_receipt.bin"
        wrong = canonical({"case_sha256": sha256(canonical(self.case)),
                           "report_sha256": "0" * 64})
        path.write_bytes(wrong)
        if os.name != "nt":
            path.chmod(0o600)
        for row in self.rows:
            if row["id"] == "report_receipt":
                row["sha256"] = sha256(wrong)
        proof_path = self.root / "recovery.bin"
        proof = json.loads(proof_path.read_text())
        proof["restored_files"]["report_receipt"] = sha256(wrong)
        proof_path.write_bytes(canonical(proof))
        if os.name != "nt":
            proof_path.chmod(0o600)
        for row in self.rows:
            if row["id"] == "recovery":
                row["sha256"] = sha256(canonical(proof))
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_incorporated_edition_and_missing_resources_block(self):
        self.manifest["source_closure"]["incorporated_sources"][0]["edition"] = "2027"
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.manifest["source_closure"]["incorporated_sources"][0]["edition"] = "2026"
        self.manifest["source_closure"]["resources"].clear()
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_missing_primary_storage_separate_restore_or_complete_inventory_blocks(self):
        self.manifest["private_storage"]["separate_recovery_key_custody"] = False
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.manifest["private_storage"]["separate_recovery_key_custody"] = True
        self.manifest["private_storage"]["restore_device_id"] = "qa-primary"
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.manifest["private_storage"]["restore_device_id"] = "qa-independent"
        # A missing private registry means offdevice restoration was incomplete.
        self.rows[:] = [f for f in self.rows if f["kind"] != "REGISTRY_SNAPSHOT"]
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_unreviewed_business_or_changed_recipient_blocks(self):
        self.manifest["business"]["identity_verified"] = False
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.manifest["business"]["identity_verified"] = True
        self.manifest["delivery"]["recipient"] = "attacker@example.com"
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_report_or_message_mutation_invalidates_signoff(self):
        self.manifest["delivery"]["subject"] = "Altered message after approval"
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.manifest["delivery"]["subject"] = "Fictional source review"
        self.manifest["report"]["full_human_review"] = False
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_one_missing_independent_signer_and_reused_key_block(self):
        self.manifest["attestations"].pop()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()
        self.sign()
        self.manifest["attestations"][5]["key_id"] = self.manifest["attestations"][4]["key_id"]
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_expired_one_message_approval_and_future_restore_block(self):
        self.manifest["delivery"]["expires_at"] = (NOW-timedelta(minutes=1)).isoformat()
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.check()

    def test_escape_and_symlink_source_are_never_read(self):
        with self.assertRaises(AcceptedCaseBlocked):
            _file(self.root, "../evil", "0"*64)
        try:
            (self.root / "shortcut").symlink_to(self.root / "case.bin")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not available on this runner")
        with self.assertRaises(AcceptedCaseBlocked):
            _file(self.root, "shortcut", next(x["sha256"] for x in self.rows if x["id"]=="case"))

    def test_one_use_signed_nonce_reserved_atomically_and_never_sends(self):
        verdict = self.check()  # FICTIONAL fixture, mocked existing core.
        ledger_dir = Path(self.tmp.name) / "shared-trusted-ledger"
        ledger_dir.mkdir(mode=0o700)
        ledger_path = ledger_dir / "approved-nonces.sqlite"
        first = self.reserve(ledger_path)
        self.assertEqual(first["status"], "SINGLE_MESSAGE_AUTHORIZATION_RESERVED_MANUAL_SEND_PENDING")
        self.assertFalse(first["external_send_performed"])
        self.assertTrue(ledger_path.is_file())
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path)

    def test_nonce_claim_requires_prior_verified_release_and_unexpired_window(self):
        ledger_dir = Path(self.tmp.name) / "shared-trusted-ledger"
        ledger_dir.mkdir(mode=0o700)
        ledger_path = ledger_dir / "approved-nonces.sqlite"
        # A copied successful status can no longer be used as an authorization:
        # reserve independently executes the REAL core, which rejects the fixture.
        self.assertEqual(self.check()["status"],
                         "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY")
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path, mock_core=False)
        self.assertFalse(ledger_path.exists())
        self.manifest["delivery"]["expires_at"] = (NOW - timedelta(minutes=2)).isoformat()
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path)
        self.assertFalse(ledger_path.exists())

    def test_nonce_reservation_rechecks_modified_source_after_prior_green_verdict(self):
        ledger_dir = Path(self.tmp.name) / "shared-trusted-ledger"
        ledger_dir.mkdir(mode=0o700)
        ledger_path = ledger_dir / "approved-nonces.sqlite"
        verdict = self.check()
        self.assertEqual(verdict["status"],
                         "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY")
        (self.root / "actionB.bin").write_bytes(b"TAMPERED AFTER VERIFICATION")
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path)
        self.assertFalse(ledger_path.exists())

    def test_unexpected_ledger_table_or_trigger_blocks_new_signed_reservation(self):
        ledger_dir = Path(self.tmp.name) / "shared-trusted-ledger"
        ledger_dir.mkdir(mode=0o700)
        ledger_path = ledger_dir / "approved-nonces.sqlite"
        with sqlite3.connect(ledger_path) as db:
            db.execute("CREATE TABLE attacker_can_reset_ledger (secret TEXT)")
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path)
        with sqlite3.connect(ledger_path) as db:
            db.execute("DROP TABLE attacker_can_reset_ledger")
        self.reserve(ledger_path)
        with sqlite3.connect(ledger_path) as db:
            db.execute("CREATE TRIGGER wipe_old_nonce AFTER INSERT ON "
                       "single_message_authorizations BEGIN "
                       "DELETE FROM single_message_authorizations "
                       "WHERE nonce_sha256 != NEW.nonce_sha256; END")
        self.manifest["delivery"]["authorization_nonce"] = "cd" * 16
        self.sign()
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve(ledger_path)
        with sqlite3.connect(ledger_path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM single_message_authorizations"
            ).fetchone()[0], 1)

    def test_official_source_scope_rejects_arbitrary_urls(self):
        self.assertFalse(_official("https://evil.example/history", sam_only=True))
        self.assertFalse(_official("https://sam.gov.evil.example/history", sam_only=True))
        self.assertFalse(_official("http://sam.gov/", sam_only=True))
        self.assertFalse(_official("https://sam.gov/opp?q=api_key=secret", sam_only=True))


if __name__ == "__main__":
    unittest.main()
