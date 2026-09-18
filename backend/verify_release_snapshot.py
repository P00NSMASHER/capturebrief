#!/usr/bin/env python3
"""Verify the preserved CaptureBrief backend release exactly, then run its original tests.

This script treats the ZIP as an immutable provenance artifact. It does not trust archive
paths, validates the outer artifact hash plus expected internal file hashes, extracts into
an isolated temporary directory, and runs the original unittest suite with ResourceWarning
promoted to errors.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "snapshots" / "CaptureBrief_Backend_Deploy_Ready_2026-09-15.zip"
EXPECTED_ARCHIVE_SHA256 = "a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d"

EXPECTED_FILES = {
    "capturebrief_evidence.py": "7de135be54a6f594ec72fa0a113d71b2796a760ccbba83002a098ed2c61a0011",
    "entitlement_ledger.py": "eeb713e1446d2155d18758c8c2fd8ba3a88680715e707b0c80a42fc46d0ff2cd",
    "job_queue.py": "6212d53d222b5370bf2528f8472e3c00b0e45a712aec17a4e7d287d5150889ed",
    "source_budget.py": "8a5c9db76b124c3ab447edf27d59f2ece4cf3661245ba1573f63bb3db0950b99",
    "webhook_boundary.py": "cfe633e440e5d4877fc7f8d61db6d26ae31fc902cd7d66020593d83cd109283d",
    "tests/test_entitlement.py": "9b6f83c744f1ca4fd5572a7fc01a48999b66cde150c76657d9e68d43c05f9647",
    "tests/test_evidence.py": "2b17220993be3a45bdb7df7aff81df0c5ccf32ea250d6eee43e18c9ba07f5347",
    "tests/test_job_queue.py": "a432e8c8dbc6143d759d84b3871a90637db2129e8122762ebbac48d68197b231",
    "tests/test_source_budget.py": "487f0a866e60ae58f9e548142f03026d3442dd750c68dd2548d3095df2bb9f74",
    "tests/test_webhook_boundary.py": "8afad73d39f52c31e9f79aa1274e3659365951c31302e3e8752b335b56a0dd9f",
}

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe archive path: {member.filename}")
        members.append(member)
    return members

def locate_payload_root(extracted: Path) -> Path:
    candidates = list(extracted.rglob("capturebrief_evidence.py"))
    if len(candidates) != 1:
        raise SystemExit(f"expected exactly one payload root; found {len(candidates)}")
    return candidates[0].parent

def main() -> int:
    if not SNAPSHOT.is_file():
        raise SystemExit(f"missing snapshot: {SNAPSHOT}")
    archive_bytes = SNAPSHOT.read_bytes()
    actual_archive_hash = sha256_bytes(archive_bytes)
    if actual_archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise SystemExit(f"archive hash mismatch: {actual_archive_hash}")

    with tempfile.TemporaryDirectory(prefix="capturebrief-release-") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(SNAPSHOT) as archive:
            members = safe_members(archive)
            archive.extractall(tmp_path, members=members)
        payload = locate_payload_root(tmp_path)

        for rel, expected_hash in EXPECTED_FILES.items():
            path = payload / rel
            if not path.is_file():
                raise SystemExit(f"missing expected release file: {rel}")
            actual = sha256_bytes(path.read_bytes())
            if actual != expected_hash:
                raise SystemExit(f"internal hash mismatch for {rel}: {actual}")

        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "error::ResourceWarning"
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=payload,
            env=env,
            text=True,
        )
        return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
