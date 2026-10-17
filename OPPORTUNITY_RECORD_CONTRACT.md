# CaptureBrief OpportunityRecord Contract

## Purpose
Create a stable boundary between federal-data providers and CaptureBrief's proprietary qualification/evidence engine.

External providers may change. CaptureBrief conclusions must not depend on provider-specific response shapes.

## Canonical record

```json
{
  "opportunity_id": null,
  "notice_id": null,
  "solicitation_number": null,
  "title": null,
  "agency": null,
  "office": null,
  "notice_type": null,
  "naics": [],
  "psc": [],
  "set_aside": null,
  "place_of_performance": null,
  "posted_at": null,
  "response_deadline": null,
  "amendments": [],
  "attachments": [],
  "award_history": [],
  "requirements_text": null,
  "source_manifest": [
    {
      "source": null,
      "url": null,
      "retrieved_at": null,
      "content_hash": null
    }
  ],
  "provider_metadata": {}
}
```

## Rules
1. Provider adapters may populate facts; they may not generate pursue/hold/pass conclusions.
2. Deadline, eligibility, set-aside, amendment, and solicitation identity fields are critical and require source-level provenance.
3. Conflicting provider facts must be surfaced, not silently reconciled.
4. Missing critical fields remain explicit unknowns.
5. Provider-specific metadata is retained outside the canonical fields for audit/debugging.
6. CaptureBrief's existing blocker/unknown distinction remains authoritative.
7. Any open-source adapter must be pinned in OPEN_SOURCE_PROVENANCE.md before production incorporation.

## Initial adapters to evaluate
- current/native CaptureBrief source path;
- blencorp/capture-mcp-server;
- EthanHNguyen/rfp-map bulk ingestion.

## Regression gate
Before enabling an alternate provider, run the same representative opportunity set through native and candidate adapters and compare:
- notice/solicitation identity;
- response deadline;
- set-aside/eligibility;
- amendment state;
- attachment/source inventory;
- missing/unknown handling.

No adapter ships if it increases material deadline, identity, eligibility, or source-provenance errors.
