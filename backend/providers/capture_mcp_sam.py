"""Adapter for blencorp/capture-mcp-server SAM.gov opportunity summaries.

Pinned upstream contract:
blencorp/capture-mcp-server@e91ce243cd6a62e9c2a55609d34a187fca89703b
src/tools/sam-tools.ts -> get_sam_opportunities

The upstream summary intentionally omits amendments, attachments, and several
detail fields. Those remain explicit unknowns here. This module never accepts or
stores a SAM API key.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from opportunity_record import DeadlineFact, OpportunityRecord, SourceRef, safe_public_url

_TIMEZONE_TOKEN = re.compile(r"\b(?:UTC|GMT|ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT)\b", re.I)
_OFFSET_END = re.compile(r"([+-]\d{2}:\d{2})$")
_ALLOWED_METADATA = ("baseType", "subTier", "active")
PROVIDER_ROLE = "discovery_only"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).split()).strip()
    return result or None


def _sam_source_url(opportunity: Mapping[str, Any]) -> str:
    links = opportunity.get("links")
    raw = links.get("self") if isinstance(links, Mapping) else None
    if not isinstance(raw, str):
        raise ValueError("Capture MCP SAM opportunity is missing links.self provenance")
    safe = safe_public_url(raw)
    host = (urlsplit(safe).hostname or "").lower()
    if host != "sam.gov" and not host.endswith(".sam.gov"):
        raise ValueError("Capture MCP SAM source must resolve to sam.gov")
    return safe


def _deadline(raw_value: Any, source: SourceRef) -> DeadlineFact | None:
    raw = _text(raw_value)
    if raw is None:
        return None

    normalized: str | None = None
    timezone_wording: str | None = None

    candidate = raw
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() is not None:
        normalized = parsed.isoformat()
        if raw.endswith("Z"):
            timezone_wording = "Z"
        else:
            match = _OFFSET_END.search(raw)
            timezone_wording = match.group(1) if match else "explicit offset"
    else:
        match = _TIMEZONE_TOKEN.search(raw)
        if match:
            timezone_wording = match.group(0)

    return DeadlineFact(
        raw_wording=raw,
        normalized_value=normalized,
        timezone_wording=timezone_wording,
        source=source,
    )


def adapt_opportunity(opportunity: Mapping[str, Any], *, retrieved_at: str) -> OpportunityRecord:
    """Translate one Capture MCP SAM summary row into OpportunityRecord.

    Credentials or arbitrary provider fields are intentionally not retained.
    """
    if not isinstance(opportunity, Mapping):
        raise TypeError("opportunity must be a mapping")

    source = SourceRef(
        source="capture-mcp:sam.gov",
        url=_sam_source_url(opportunity),
        retrieved_at=retrieved_at,
    )

    notice_id = _text(opportunity.get("id"))
    solicitation = _text(opportunity.get("solicitationNumber"))
    set_aside = _text(opportunity.get("setAside"))
    deadline = _deadline(opportunity.get("responseDeadLine"), source)

    unknowns = {
        "amendments",
        "attachments",
        "place_of_performance",
        "award_history",
    }
    if not (notice_id or solicitation):
        unknowns.add("identity")
    if set_aside is None:
        unknowns.add("set_aside")
    if deadline is None:
        unknowns.add("response_deadline")

    field_sources: dict[str, SourceRef] = {}
    if notice_id or solicitation:
        field_sources["identity"] = source
    if set_aside is not None:
        field_sources["set_aside"] = source
    if deadline is not None:
        field_sources["response_deadline"] = source

    # The summary endpoint does not expose an amendment inventory. Keep this
    # deliberately unknown instead of interpreting baseType/type as amendments.
    metadata = {
        key: opportunity[key]
        for key in _ALLOWED_METADATA
        if key in opportunity and opportunity[key] is not None
    }

    naics = _text(opportunity.get("naicsCode"))
    psc = _text(opportunity.get("classificationCode"))

    return OpportunityRecord(
        provider="capture_mcp_sam",
        opportunity_id=notice_id,
        notice_id=notice_id,
        solicitation_number=solicitation,
        title=_text(opportunity.get("title")),
        agency=_text(opportunity.get("department")),
        office=_text(opportunity.get("office")),
        notice_type=_text(opportunity.get("type")),
        naics=(naics,) if naics else (),
        psc=(psc,) if psc else (),
        set_aside=set_aside,
        posted_at=_text(opportunity.get("postedDate")),
        response_deadline=deadline,
        amendment_ids=(),
        attachment_ids=(),
        award_history_ids=(),
        field_sources=field_sources,
        source_manifest=(source,),
        explicit_unknowns=frozenset(unknowns),
        provider_metadata=metadata,
    )
