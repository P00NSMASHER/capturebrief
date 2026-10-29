"""Static, read-only audit of the founder-curated, zero-card operator runbook.

This detects a stale paid-pilot workflow before an operator relies on it.
It does not attest human training, website deployment, source truth, storage
authorization, delivery, or a successful real-world recovery drill.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RUNBOOK = Path(__file__).resolve().parents[1] / "FIRST-PILOT-OPERATOR-RUNBOOK.md"
REQUIRED = {
    "free_scope": "one free assumption",
    "cohort_limit": "at most ten",
    "no_card": "no card",
    "founder_preflight": "python scripts/pilot_preflight.py --stage admission --offer free --launch-mode founder_curated",
    "draft_not_delivery": "draft is not a submitted request",
    "source_api_limit": "latest-active only",
    "full_family_history": "complete official action and amendment history",
    "incomplete_history_hold": "HOLD",
    "private_destination": "`P00NSMASHER/capturebrief-state`",
    "isolated_token": "`CAPTUREBRIEF_STATE_TOKEN`",
    "provider_isolation": "Never upload to `P00NSMASHER/permitplate-state`",
    "complete_backup": "full-case encrypted backup",
    "second_device": "second authorized device",
    "separate_key": "separately held recovery key",
    "signed_one_message_release": "six distinct Ed25519",
    "no_messages": "no external message is sent",
    "no_customer_prelaunch_gate": "no customer is required for prelaunch",
}
FORBIDDEN = {
    "legacy_prepaid_intake": "## A. Source, identity, and prepayment intake",
    "legacy_paid_pilot_section": "## B. Payment: live account, never website assertion",
    "legacy_stripe_price_instruction": "one-time USD 149.00",
    "legacy_included_paid_watch": "## D. The 14-day targeted watch",
}


def violations(document: str) -> list[str]:
    if not isinstance(document, str):
        raise TypeError("Runbook text must be a string")
    # Markdown line wrapping is not a policy change. Match the visible phrase
    # across newlines while preserving exact required/forbidden token content.
    normalized = re.sub(r"\s+", " ", document.casefold())
    problems = [f"MISSING_{key.upper()}" for key, value in REQUIRED.items()
                if re.sub(r"\s+", " ", value.casefold()) not in normalized]
    problems.extend(f"STALE_{key.upper()}" for key, value in FORBIDDEN.items()
                    if re.sub(r"\s+", " ", value.casefold()) in normalized)
    return sorted(problems)


def main() -> int:
    issues = violations(RUNBOOK.read_text(encoding="utf-8"))
    print(json.dumps({"status": "RUNBOOK_CONTRACT_PASS" if not issues else "RUNBOOK_CONTRACT_BLOCKED",
                      "violations": issues, "real_world_operator_acceptance_proven": False,
                      "customer_send_authorized": False}, sort_keys=True))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
