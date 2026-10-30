"""Adversarial contracts for the fictional-only cross-runner restore harness."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
else:
    CRYPTOGRAPHY_AVAILABLE = True

from scripts.qa_full_case_cross_runner import (
    CIPHERTEXT,
    RECEIPT,
    consume,
    produce,
)


@unittest.skipUnless(
    CRYPTOGRAPHY_AVAILABLE,
    "Pinned cryptography==46.0.4 required for encrypted cross-runner QA",
)
class FictionalCrossRunnerHarnessTests(unittest.TestCase):
    def test_exact_ciphertext_roundtrip_reconciles_all_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "artifact"
            restored = Path(temp) / "restored"

            created = produce(str(artifact))
            verified = consume(str(artifact), str(restored))

            self.assertEqual(created["source_originals"], 13)
            self.assertEqual(verified["originals_verified"], 13)
            self.assertFalse(verified["remote_production_key_custody_verified"])
            self.assertFalse(verified["actual_offdevice_customer_restore_verified"])
            self.assertFalse(verified["customer_release_authorized"])
            self.assertFalse(verified["external_send_performed"])

    def test_changed_ciphertext_is_rejected_before_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "artifact"
            produce(str(artifact))
            ciphertext = artifact / CIPHERTEXT
            ciphertext.write_bytes(ciphertext.read_bytes() + b"changed-in-transit")

            with self.assertRaisesRegex(
                ValueError, "Encrypted artifact transfer changed source bytes"
            ):
                consume(str(artifact), str(Path(temp) / "restored"))

    def test_manifest_cannot_escalate_customer_release_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "artifact"
            produce(str(artifact))
            manifest = artifact / RECEIPT
            receipt = json.loads(manifest.read_text("utf-8"))
            receipt["customer_release_authorized"] = True
            manifest.write_text(
                json.dumps(receipt, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError, "Cross-runner fictional-only manifest is invalid"
            ):
                consume(str(artifact), str(Path(temp) / "restored"))


if __name__ == "__main__":
    unittest.main()
