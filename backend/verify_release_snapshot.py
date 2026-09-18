#!/usr/bin/env python3
"""Verify CaptureBrief backend source-consolidation invariants.

Historical provenance:
- Authoritative Sept. 15 release artifact:
  CaptureBrief_Backend_Deploy_Ready_2026-09-15.zip
- External artifact SHA-256:
  a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d

The normal source tree is a compatibility implementation, not a byte-for-byte
copy of that ZIP. Behavioral compatibility is enforced by the Sept. 15
regression suites in backend/tests plus provider-boundary tests.
"""
from __future__ import annotations

from pathlib import Path
import re

BACKEND_DIR=Path(__file__).resolve().parent

REQUIRED_MODULES=(
    "capturebrief_evidence.py",
    "entitlement_ledger.py",
    "job_queue.py",
    "source_budget.py",
    "webhook_boundary.py",
    "opportunity_record.py",
    "providers/capture_mcp_sam.py",
)
REQUIRED_TESTS=(
    "tests/test_evidence.py",
    "tests/test_entitlement.py",
    "tests/test_job_queue.py",
    "tests/test_source_budget.py",
    "tests/test_webhook_boundary.py",
    "tests/test_opportunity_record.py",
    "tests/test_capture_mcp_sam.py",
)

FORBIDDEN_PATTERNS=(
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"whsec_[A-Za-z0-9._~-]{12,}"),
    re.compile(r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]",re.I),
)

def main()->int:
    missing=[rel for rel in REQUIRED_MODULES+REQUIRED_TESTS if not (BACKEND_DIR/rel).is_file()]
    if missing:
        raise SystemExit("missing consolidated backend files:\n"+"\n".join(missing))

    # Production modules only: regression tests intentionally contain fake
    # secret-shaped fixtures to prove validators fail closed.
    leaks=[]
    for rel in REQUIRED_MODULES:
        text=(BACKEND_DIR/rel).read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                leaks.append(f"{rel}:{pattern.pattern}")
    if leaks:
        raise SystemExit("credential-like literal detected:\n"+"\n".join(leaks))

    snapshots=BACKEND_DIR/"snapshots"
    bad_binary=list(snapshots.glob("*.zip")) if snapshots.exists() else []
    if bad_binary:
        raise SystemExit("binary release snapshots must not be committed; use external SHA provenance")

    print("CaptureBrief source-consolidation invariant check passed.")
    print("Historical release SHA-256: a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d")
    print(f"Modules: {len(REQUIRED_MODULES)}; test modules: {len(REQUIRED_TESTS)}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
