from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_ACTION_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_OPP_PATH = re.compile(r"(?:^|/)opp/([0-9a-fA-F]{32})(?:/|$)", re.IGNORECASE)


class OpportunityReferenceError(ValueError):
    pass


def parse_opportunity_reference(value: Any) -> dict[str, Any]:
    """Parse the public opportunity reference submitted by the buyer.

    This parser extracts identity only. It never treats URL position, UUID spelling, or a
    customer-supplied link as evidence that an action is current.
    """
    raw = str(value or "").strip()
    if not raw:
        raise OpportunityReferenceError("public opportunity reference is empty")

    if _ACTION_ID.fullmatch(raw):
        return {
            "reference_type": "SAM_ACTION_ID",
            "raw": raw,
            "action_id": raw.lower(),
            "solicitation_number": None,
            "source_authoritative": False,
        }

    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (host == "sam.gov" or host.endswith(".sam.gov")):
            return {
                "reference_type": "UNSUPPORTED_URL",
                "raw": raw,
                "host": host or None,
                "source_authoritative": False,
            }
        match = _OPP_PATH.search(parsed.path or "")
        if match:
            return {
                "reference_type": "SAM_ACTION_URL",
                "raw": raw,
                "action_id": match.group(1).lower(),
                "solicitation_number": None,
                "source_authoritative": False,
            }
        return {
            "reference_type": "SAM_URL_UNRESOLVED",
            "raw": raw,
            "host": host,
            "source_authoritative": False,
        }

    if len(raw) > 240 or any(ord(ch) < 32 for ch in raw):
        raise OpportunityReferenceError("solicitation reference is malformed")

    return {
        "reference_type": "SOLICITATION_NUMBER",
        "raw": raw,
        "action_id": None,
        "solicitation_number": raw,
        "source_authoritative": False,
    }
