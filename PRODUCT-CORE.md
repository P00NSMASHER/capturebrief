# CaptureBrief Product Core v0.3 — Approved-Source Evidence Pipeline

Updated: September 21, 2026

CaptureBrief is a human-supervised, public-source Pursuit QA second pass. v0.3 hardens the product around approved SAM automation surfaces and explicitly separates automated evidence from human-supervised source observations.

## v0.3 source architecture

### Automated
- **SAM Get Opportunities Public API v2** — current/latest-active assertion and current `resourceLinks`.
- **SAM Data Services Contract Opportunities extracts** — action/version membership across active and declared fiscal-year archive coverage.

### Human-supervised
- SAM UI pages and the undocumented resource-manifest web-UI implementation surface, used only when deletion/tombstone or historical packet state cannot be established from approved APIs/extracts.

The old automated SAM web-UI manifest poller and canary are retired. Production code now throws if asked to automate that surface.

## History receipt

`history-from-extracts` scans official Contract Opportunities CSV extracts, hashes each extract, exact-matches the solicitation number, disambiguates by AAC when possible, and issues a Data Services history receipt.

A Data Services receipt records:
- every observed Notice ID/action UUID;
- per-action source-row hashes;
- extract SHA-256 values;
- active vs archive source;
- supplied and missing fiscal-year coverage;
- AAC/office family context;
- `ordering_authoritative = false`;
- `current_action_authoritative = false`.

A receipt becomes `COMPLETE` only when the declared archive-year scope is explicitly confirmed and every required archive year plus the active extract is present. CaptureBrief does not guess the family start year.

## Current-action receipt

`current-from-api` uses the documented Opportunities v2 API with an API key supplied through an environment variable. The API observation is not allowed to redefine the history set: its `noticeId` must already be a member of the Data Services receipt.

This creates the required separation:

`HISTORY MEMBERSHIP != CURRENT ACTION`

The documented API's latest-active assertion proves currentness; Data Services proves version membership.

## Attachment evidence

Historical/deletion-inclusive SAM resource manifests can still be normalized and hashed, but only as human-supervised observations. Automated polling of the undocumented web-UI manifest endpoint is disabled by source policy.

For current attachments, CaptureBrief may download only an exact `resourceLinks` URL bound to an approved Opportunities API observation. It refuses guessed resource URLs.

## Release gates

The existing case schema remains backward-compatible. The evidence pipeline adds stricter acquisition rules without silently changing the case format.

A case can reach `READY_FOR_HUMAN_RELEASE` only when applicable gates pass:
1. current/terminal authority;
2. complete history evidence;
3. deletion-inclusive per-action packet evidence where required;
4. semantic reference closure;
5. required public byte hashes;
6. assumption/source/timezone rules.

Unknowns remain unknown. Restricted or source-limited evidence cannot become a resolved gate-changing fact.

## CLI

    python -m capturebrief_core.cli history-from-extracts SOL-123 active.csv \
      --archive 2026:FY2026_archived_opportunities.csv \
      --seed-notice-id <NOTICE_ID> --scope-start-fy 2026 --scope-end-fy 2026 --confirm-scope \
      -o history.json

    SAM_API_KEY=... python -m capturebrief_core.cli current-from-api \
      SOL-123 history.json 09/01/2026 09/30/2026 -o current.json \
      --observation-output current-observation.json

    python -m capturebrief_core.cli normalize-manifest <ACTION_UUID> manually-saved-manifest.json \
      --observed-at 2026-09-21T13:00:00-04:00 -o manifest.json

    python -m capturebrief_core.cli capture-api-resource current-observation.json '<RESOURCE_LINK>' \
      -o artifact.bin --receipt-output artifact-receipt.json

## Remaining P0

The remaining automation gap is proving the **history scope start** without guessing. Until GSA exposes a narrower all-version family query with authoritative completeness semantics, CaptureBrief requires an explicit scope boundary for Data Services archive coverage. The product should prefer one extra human confirmation over a false “all amendments found” claim.
