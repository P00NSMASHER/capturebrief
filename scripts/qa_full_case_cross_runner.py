"""FICTIONAL-ONLY Linux->Windows full-case encrypted snapshot acceptance.

Never use real customers, actual production keys or external sending in this
harness. A public test key is imported from the offline test fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import atomic_write_bytes, atomic_write_text
from capturebrief_core.accepted_case_release import _reject_private_path_links
from scripts.full_case_backup import (
    verify_complete_backup, restore_complete_backup,
)
from scripts.scoped_private_backup import _unique
from tests.test_full_case_backup import FullCaseBackupTests, KINDS, TEST_KEY

SCHEMA = "capturebrief-crossrunner-fictional-proof-v1"
CIPHERTEXT = "fictional-complete-case.cbak"
RECEIPT = "fictional-ciphertext-sha256.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _path(value: str) -> Path:
    path = Path(value).expanduser().absolute()
    _reject_private_path_links(path)
    if path == REPO or path.is_relative_to(REPO):
        raise ValueError("Fictional test artifacts cannot be written to public source Git")
    return path


def produce(directory: str) -> dict[str, object]:
    output = _path(directory)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("Fictional-only artifact directory must be new or empty")
    else:
        output.mkdir(parents=True, mode=0o700)
    if os.name != "nt":
        output.chmod(0o700)
    qa = FullCaseBackupTests(
        "test_entire_case_backup_encrypts_all_required_kinds_and_restores_exact_bytes"
    )
    qa.setUp()
    try:
        encrypted = qa.create()
        if (encrypted["file_count"] != len(KINDS) or
                encrypted["customer_release_authorized"] is not False or
                encrypted["independent_restore_verified"] is not False or
                encrypted["external_send_authorized"] is not False):
            raise ValueError("Test fixture unexpectedly obtained commercial authority")
        ciphertext = qa.archive.read_bytes()
        if b"buyer@example.invalid" in ciphertext:
            raise ValueError("Unencrypted fictional buyer fixture detected")
        rows = [{
            "id": entry["id"], "kind": entry["kind"], "path": entry["path"],
            "sha256": entry["sha256"],
        } for entry in qa.entries]
        receipt = {
            "schema": SCHEMA,
            "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
            "file_count": len(rows),
            "files": rows,
            "fictional_only": True,
            "production_key_custody_verified": False,
            "independent_production_offdevice_restore_verified": False,
            "customer_release_authorized": False,
            "external_send_performed": False,
        }
        atomic_write_bytes(output / CIPHERTEXT, ciphertext, overwrite=False)
        atomic_write_text(output / RECEIPT, json.dumps(
            receipt, sort_keys=True, indent=2) + "\n", overwrite=False)
    finally:
        qa.doCleanups()
    return {
        "status": "FICTIONAL_ENCRYPTED_CASE_CREATED_FOR_SECOND_RUNNER",
        "source_originals": len(rows),
        "encrypted_artifact_only": True,
        "customer_release_authorized": False,
        "production_key_custody_verified": False,
    }


def consume(directory: str, restore_dir: str) -> dict[str, object]:
    root = _path(directory)
    if not root.is_dir() or {item.name for item in root.iterdir()} != {CIPHERTEXT, RECEIPT}:
        raise ValueError("Expected only one fictional ciphertext and source digest manifest")
    src = root / CIPHERTEXT
    meta = root / RECEIPT
    if src.is_symlink() or meta.is_symlink():
        raise ValueError("Fictional test artifact links forbidden")
    receipt = json.loads(meta.read_text("utf-8"), object_pairs_hook=_unique)
    if (not isinstance(receipt, dict)
            or set(receipt) != {
                "schema", "ciphertext_sha256", "file_count", "files",
                "fictional_only", "production_key_custody_verified",
                "independent_production_offdevice_restore_verified",
                "customer_release_authorized", "external_send_performed",
            }
            or receipt["schema"] != SCHEMA
            or receipt["fictional_only"] is not True
            or any(receipt[field] is not False for field in (
                "production_key_custody_verified",
                "independent_production_offdevice_restore_verified",
                "customer_release_authorized",
                "external_send_performed",
            ))
            or not isinstance(receipt["ciphertext_sha256"], str)
            or not SHA256.fullmatch(receipt["ciphertext_sha256"])):
        raise ValueError("Cross-runner fictional-only manifest is invalid")
    raw = src.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["ciphertext_sha256"]:
        raise ValueError("Encrypted artifact transfer changed source bytes")
    rows = receipt["files"]
    if (not isinstance(rows, list) or not isinstance(receipt["file_count"], int)
            or type(receipt["file_count"]) is not int
            or len(rows) != receipt["file_count"] or len(rows) != len(KINDS)
            or Counter(x["kind"] for x in rows if isinstance(x, dict)) != Counter(KINDS)
            or any(not isinstance(x, dict)
                   or set(x) != {"id", "kind", "path", "sha256"}
                   or not isinstance(x["sha256"], str)
                   or not SHA256.fullmatch(x["sha256"])
                   or not isinstance(x["path"], str)
                   or not x["path"].startswith("evidence/")
                   for x in rows)):
        raise ValueError("Fictional case expected-file list is incomplete or modified")
    verified = verify_complete_backup(src, TEST_KEY)
    dest = _path(restore_dir)
    if dest.exists():
        raise ValueError("Independent runner restore needs an empty new path")
    actual = restore_complete_backup(src, dest, TEST_KEY)
    if (verified["file_count"] != len(KINDS)
            or actual["file_count"] != len(KINDS)
            or verified["offdevice_restore_proven"] is not False
            or any(actual.get(flag) is not False for flag in (
                "independent_offdevice_restore_proven",
                "production_key_custody_verified",
                "customer_release_authorized",
                "external_send_authorized",
            ))):
        raise ValueError("Fictional restore claimed unsupported authority")
    for row in rows:
        path = dest.joinpath(*row["path"].split("/"))
        if (not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
                or actual["restored_files"].get(row["id"]) != row["sha256"]):
            raise ValueError("Cross-runner restored original differs from earlier runner")
    return {
        "status": "FICTIONAL_LINUX_TO_WINDOWS_FULL_CASE_RESTORE_VERIFIED",
        "originals_verified": len(KINDS),
        "remote_production_key_custody_verified": False,
        "actual_offdevice_customer_restore_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    producer = sub.add_parser("produce")
    producer.add_argument("--artifact-dir", required=True)
    consumer = sub.add_parser("consume")
    consumer.add_argument("--artifact-dir", required=True)
    consumer.add_argument("--restore-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = (produce(args.artifact_dir)
                  if args.action == "produce" else
                  consume(args.artifact_dir, args.restore_dir))
    except Exception:
        print(json.dumps({"status": "FICTIONAL_CROSS_RUNNER_QA_BLOCKED",
                          "customer_release_authorized": False,
                          "external_send_performed": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
