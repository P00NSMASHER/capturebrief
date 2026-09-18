#!/usr/bin/env python3
"""Verify the normalized CaptureBrief backend files already imported from the
Sept. 15 release.

The authoritative external release artifact remains identified by SHA-256
a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d.
This script does NOT claim the whole release has been consolidated yet.
It proves that the imported subset is byte-identical to the verified release.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

EXPECTED = {
    "capturebrief_evidence.py": "7de135be54a6f594ec72fa0a113d71b2796a760ccbba83002a098ed2c61a0011",
    "source_budget.py": "8a5c9db76b124c3ab447edf27d59f2ece4cf3661245ba1573f63bb3db0950b99",
    "webhook_boundary.py": "cfe633e440e5d4877fc7f8d61db6d26ae31fc902cd7d66020593d83cd109283d",
    "tests/test_source_budget.py": "487f0a866e60ae58f9e548142f03026d3442dd750c68dd2548d3095df2bb9f74",
    "tests/test_webhook_boundary.py": "8afad73d39f52c31e9f79aa1274e3659365951c31302e3e8752b335b56a0dd9f",
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    mismatches: list[str] = []
    for rel, expected in EXPECTED.items():
        path = BACKEND_DIR / rel
        if not path.is_file():
            mismatches.append(f"missing:{rel}")
            continue
        actual = sha256(path)
        if actual != expected:
            mismatches.append(f"hash:{rel}:{actual}")
    if mismatches:
        raise SystemExit("release-subset verification failed\n" + "\n".join(mismatches))
    print(f"Verified {len(EXPECTED)} imported files against Sept. 15 release hashes.")
    print("Still unconsolidated by design: entitlement_ledger.py, job_queue.py and their tests.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
