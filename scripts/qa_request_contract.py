"""Run the actual pinned website composer against the actual core parser.

No browser navigation, email or payments. Node executes the website branch's
real JS through its deterministic DOM harness; rendered browser QA is separate.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capturebrief_core.audit import audit_case
from capturebrief_core.request_draft import (
    FREE_CLAIM, FREE_OFFER, PAID_CLAIM, SCOPE_CLAIM, create_unverified_case,
)


def main():
    site = Path(os.environ["SITE_CHECKOUT"]).resolve(strict=True)
    completed = subprocess.run(
        ["node", ".github/request_draft_unit.cjs", "--emit-drafts"],
        cwd=site, check=True, capture_output=True, text=True, timeout=30,
    )
    drafts = json.loads(completed.stdout)
    expected = {"SCOPE_FIRST": SCOPE_CLAIM, "PAID": PAID_CLAIM, "FREE_CHECK": FREE_CLAIM}
    if set(drafts) != set(expected):
        raise ValueError("Website emitted unexpected request modes")
    for mode, claim in expected.items():
        case, receipt = create_unverified_case(drafts[mode])
        if (receipt["purchase_claim"] != claim or receipt["purchase_claim_verified"] is not False
                or receipt["ready_to_start_work"] is not False
                or receipt["external_send_authorized"] is not False
                or audit_case(case).release_state != "FAIL_CLOSED"):
            raise ValueError("Website request claims unsupported authority")
        if mode == "FREE_CHECK" and (len(case["assumptions"]) != 1
                or case["intake"].get("requested_offer") != FREE_OFFER):
            raise ValueError("Free-check offer scope did not survive the actual composer")
    print(json.dumps({
        "status": "THREE_ACTUAL_JS_REQUEST_MODES_PARSED",
        "modes": list(expected), "source_or_payment_claims_promoted": False,
        "customer_records_used": False, "external_messages_sent": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
