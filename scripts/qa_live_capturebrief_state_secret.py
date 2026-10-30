"""Main-branch-only, no-customer private-cloud encrypted recovery rehearsal.

This tests a GitHub fine-grained repository secret WITHOUT printing it, using
a public FICTIONAL test key and the repository's existing 13-kind fake case.
Neither this script nor GitHub Actions owns or handles production recovery keys.
The remote file is cryptographically encrypted but NOT secret (test key public).
No real buyer, payment, customer release, consent, or off-device owner approval.

Only the exact P00NSMASHER/capturebrief-state private repository is allowed by
the existing custody transport. Re-running produces a new nonce and a new
small encrypted fixture; no auto-pruning/deletion and no recurring schedule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.full_case_backup import (
    verify_complete_backup, restore_complete_backup,
)
from scripts.github_private_custody import (
    inspect_private_destination, store_encrypted_backup,
    retrieve_encrypted_backup,
)
from tests.test_full_case_backup import FullCaseBackupTests, KINDS, TEST_KEY

# No token, key, path, provider response or private JSON is ever printed.
ERROR_STATUS = "FICTIONAL_PRIVATE_CLOUD_REHEARSAL_BLOCKED"
FIXTURE_METHOD = "test_entire_case_backup_encrypts_all_required_kinds_and_restores_exact_bytes"


def _fixture() -> FullCaseBackupTests:
    fake = FullCaseBackupTests(FIXTURE_METHOD)
    fake.setUp()
    return fake


def _credentials() -> str:
    token = os.getenv("CAPTUREBRIEF_STATE_TOKEN", "")
    if not token:
        raise ValueError("Missing dedicated repository secret")
    return token


def preflight() -> dict[str, object]:
    info = inspect_private_destination(_credentials())
    if (
        info.get("private_repo_verified") is not True
        or info.get("separate_from_permitplate_state") is not True
        or info.get("destination") != "P00NSMASHER/capturebrief-state"
    ):
        raise ValueError("Private destination isolation was not proved")
    return {
        "status": "CAPTUREBRIEF_DEDICATED_TOKEN_PRIVATE_REPO_READ_VERIFIED",
        "private_repository_verified": True,
        "write_access_exercised": False,
        "permitplate_state_touched": False,
        "real_customer_material_used": False,
        "independent_owner_restore_proven": False,
    }


def encrypt_upload() -> dict[str, object]:
    preflight()
    qa = _fixture()
    try:
        generated = qa.create()
        checked = verify_complete_backup(qa.archive, TEST_KEY)
        if (
            generated.get("file_count") != len(KINDS)
            or checked.get("file_count") != len(KINDS)
            or generated.get("customer_release_authorized") is not False
            or checked.get("customer_release_authorized") is not False
            or checked.get("offdevice_restore_proven") is not False
            or qa.archive.stat().st_size > 900_000
        ):
            raise ValueError("Fictional full-case original is not independently intact")
        encrypted = qa.archive.read_bytes()
        if (
            b"buyer@example.invalid" in encrypted
            or b"FICTIONAL REPORT" in encrypted
            or hashlib.sha256(encrypted).hexdigest() != generated["backup_sha256"]
        ):
            raise ValueError("Encrypted source contains plaintext or mismatched digest")
        # This command is the ONLY persistent write: a small, fictional,
        # AES-256-GCM .cbak object to our isolated private GitHub repository.
        uploaded = store_encrypted_backup(qa.archive, _credentials())
        if (
            uploaded.get("status") != "ENCRYPTED_PRIVATE_GITHUB_READBACK_VERIFIED"
            or uploaded.get("customer_release_authorized") is not False
            or uploaded.get("permitplate_records_untouched") is not True
            or uploaded.get("sha256") != generated["backup_sha256"]
        ):
            raise ValueError("Private provider did not return exact encrypted byte readback")
        return {
            "status": "FICTIONAL_ENCRYPTED_CASE_UPLOADED_AND_READ_BACK",
            "sha256": uploaded["sha256"],
            "file_count": len(KINDS),
            "remote_ciphertext_bytes": uploaded["bytes"],
            "private_repository_verified": True,
            "real_customer_material_used": False,
            "production_recovery_key_proven": False,
            "independent_owner_restore_proven": False,
            "customer_release_authorized": False,
            "external_send_performed": False,
        }
    finally:
        qa.doCleanups()


def independently_restore(ciphertext_sha256: str) -> dict[str, object]:
    if (
        not isinstance(ciphertext_sha256, str)
        or len(ciphertext_sha256) != 64
        or any(c not in "0123456789abcdef" for c in ciphertext_sha256)
    ):
        raise ValueError("Remote fixture SHA-256 must be 64 lowercase hex characters")
    preflight()
    qa = _fixture()
    try:
        downloaded = qa.staging / "new-remote-fixture.cbak"
        receipt = retrieve_encrypted_backup(
            ciphertext_sha256, downloaded, _credentials()
        )
        if (
            receipt.get("status") != "PRIVATE_GITHUB_CIPHERTEXT_RETRIEVED"
            or receipt.get("sha256") != ciphertext_sha256
            or receipt.get("independent_device_restore_verified") is not False
            or hashlib.sha256(downloaded.read_bytes()).hexdigest()
               != ciphertext_sha256
        ):
            raise ValueError("Fresh remote encrypted bytes failed source digest")
        checked = verify_complete_backup(downloaded, TEST_KEY)
        restored_dir = qa.recovered / "independently-restored-fake-case"
        restored = restore_complete_backup(
            downloaded, restored_dir, TEST_KEY
        )
        if (
            checked.get("file_count") != len(KINDS)
            or restored.get("file_count") != len(KINDS)
            or restored.get("independent_offdevice_restore_proven") is not False
            or restored.get("customer_release_authorized") is not False
            or restored.get("external_send_authorized") is not False
        ):
            raise ValueError("Fictional restore claimed unsupported authority")
        for row in qa.entries:
            item = restored_dir.joinpath(*row["path"].split("/"))
            if (
                not item.is_file()
                or hashlib.sha256(item.read_bytes()).hexdigest() != row["sha256"]
                or restored["restored_files"].get(row["id"]) != row["sha256"]
            ):
                raise ValueError("Second-runner restored source hash mismatch")
        return {
            "status": "PRIVATE_GITHUB_FICTIONAL_LINUX_TO_WINDOWS_CASE_RESTORED",
            "file_count": len(KINDS),
            "independent_runner": True,
            "real_customer_material_used": False,
            "production_recovery_key_proven": False,
            "independent_owner_restore_proven": False,
            "customer_release_authorized": False,
            "external_send_performed": False,
        }
    finally:
        qa.doCleanups()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preflight")
    sub.add_parser("upload")
    sub.add_parser("roundtrip")
    restored = sub.add_parser("restore")
    restored.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    phase = "TOKEN_PREFLIGHT"
    try:
        if args.action == "preflight":
            report = preflight()
        elif args.action == "upload":
            phase = "FICTIONAL_AES_GCM_PRIVATE_UPLOAD"
            report = encrypt_upload()
        elif args.action == "roundtrip":
            phase = "FICTIONAL_SAME_RUNNER_PRIVATE_CLOUD_ROUNDTRIP"
            sent = encrypt_upload()
            received = independently_restore(sent["sha256"])
            if received["file_count"] != sent["file_count"]:
                raise ValueError("Fictional original count mismatch")
            report = {
                "status": "FICTIONAL_ENCRYPTED_PRIVATE_CLOUD_ROUNDTRIP_VERIFIED",
                "source_originals_rehashed": received["file_count"],
                "real_customer_material_used": False,
                "separate_device_disaster_recovery_proven": False,
                "production_recovery_key_proven": False,
                "customer_release_authorized": False,
                "external_send_performed": False,
            }
        else:
            phase = "FICTIONAL_SECOND_RUNNER_RESTORE"
            report = independently_restore(args.sha256)
    except Exception:
        print(json.dumps({
            "status": ERROR_STATUS,
            "phase": phase,
            "customer_release_authorized": False,
            "external_send_performed": False,
        }, sort_keys=True))
        return 2
    if args.action == "upload" and os.getenv("GITHUB_OUTPUT"):
        # Exact authenticated ciphertext hash only; no key, case or secret.
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("ciphertext_sha256=" + report["sha256"] + "\n")
    if "sha256" in report:
        report = {k: v for k, v in report.items() if k != "sha256"}
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
