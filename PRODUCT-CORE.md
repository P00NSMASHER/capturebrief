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

## Operator workflow

The product now turns the existing website intake directly into fulfillment work.

`case-from-intake` maps the Netlify form fields into a deliberately non-evidentiary case:
- customer assumptions begin as `UNPROVEN / VERIFY_NOW`;
- no source is invented;
- no intake statement is promoted to evidence;
- the public/non-sensitive confirmation is required.

`work-queue` then derives the smallest next-step queue from the case state. Tasks are deduplicated, prioritized, and labeled by execution mode:
- `AUTOMATED_APPROVED_SOURCE` — safe for documented API/extract automation;
- `HYBRID` — automated retrieval plus an explicit human boundary;
- `HUMAN_REVIEW` — source interpretation or evidence CaptureBrief must not automate.

The queue currently covers history establishment, family/current authority, missing historical manifests, reference closure, required public-byte capture, source linkage, ownership, next actions, and deadline timezone defects.

CI exercises the full path:

    website-shaped intake JSON -> case skeleton -> operator work queue

This makes the fulfillment process reproducible rather than dependent on the founder remembering the next evidence step.

## Evidence application bridge

Approved acquisition receipts now update the operational case directly instead of remaining disconnected JSON.

`apply-approved-evidence`:
- semantically validates a Data Services receipt before mutating the case;
- applies the observed action set and preserves superseded history receipts separately;
- invalidates a stale current-action receipt automatically when the history set changes;
- applies documented Opportunities API currentness only when the asserted Notice ID is already inside the validated action set;
- retains the API observation and its approved `resourceLinks` inside the case;
- creates resource placeholders without mislabeling unverified bytes as public evidence;
- promotes only a matching resource after a verified SHA-256 byte receipt;
- is idempotent for sources, current receipts, and resource placeholders.

Source evidence still does **not** adjudicate the customer's assumption. An intake assumption remains `UNPROVEN` until the human review step explicitly changes it.

The tested fulfillment progression is now:

    website intake
      -> unproven case
      -> work queue
      -> hardened Data Services + Opportunities API receipts
      -> evidence-applied case
      -> smaller work queue
      -> historical packet/reference review
      -> human assumption adjudication
      -> release gate

CI asserts that hardened approved evidence removes history/family/current-authority tasks while historical manifest tasks remain open.

## Remaining P0

The remaining automation gap is proving the **history scope start** without guessing. Until GSA exposes a narrower all-version family query with authoritative completeness semantics, CaptureBrief requires an explicit scope boundary for Data Services archive coverage. The product should prefer one extra human confirmation over a false “all amendments found” claim.


## Receipt contract verification

Approved automation receipts are verified semantically, not only by their outer SHA-256.

For `APPROVED_EXTRACT` history receipts, release requires the Data Services source contract, non-authoritative ordering/currentness flags, action-set equality, valid row hashes, confirmed archive scope with no gaps, approved source-snapshot URLs and hashes, active-extract evidence, and a valid family/seed binding.

For `APPROVED_API` current-action receipts, release requires the documented Opportunities v2 source class, the `SAM_GET_OPPORTUNITIES_V2` contract, Notice ID equality, a valid API-payload digest, and resource links that remain inside the approved API-resource-link contract.

Recomputing an outer receipt hash after altering those semantics cannot make the receipt green.


## Full-catalog Data Services index

The preferred history path is now a reusable, content-addressed Data Services index rather than per-case CSV scanning.

A pinned human-supervised first-party archive catalog defines the public Contract Opportunities archive slots CaptureBrief must inspect through the current fiscal year. For the September 21, 2026 catalog snapshot, that means FY1970, FY1980, and every FY1998-FY2026 archive plus the active extract. The future-listed FY2030 entry is retained in the catalog evidence but is not required for FY2026.

The SQLite evidence index:

- streams CSV rows instead of loading the active extract into memory;
- hashes each extract before indexing;
- can retain a read-only content-addressed CSV copy named by SHA-256;
- preserves old source snapshots when a slot refreshes while `current_sources` points to the newest indexed snapshot;
- indexes solicitation number, Notice ID, AAC, office, source slot, row hash, and source-extract hash;
- performs large-source work once and reuses the index across customer pursuits.

A `FULL_CATALOG` history receipt is accepted only when the pinned catalog snapshot verifies, every required archive slot plus ACTIVE is indexed, the independently supplied seed Notice ID is present, and the family filter is anchored to that seed rather than chosen from bulk ordering.

Useful commands:

    python -m capturebrief_core.cli archive-catalog
    python -m capturebrief_core.cli history-index-plan history.sqlite
    python -m capturebrief_core.cli history-index-fetch history.sqlite ARCHIVE:2026 fy2026.csv --snapshot-dir evidence/snapshots
    python -m capturebrief_core.cli history-index-ingest history.sqlite active.csv --kind active --snapshot-dir evidence/snapshots
    python -m capturebrief_core.cli history-index-status history.sqlite
    python -m capturebrief_core.cli history-from-index history.sqlite SOL-123 --seed-notice-id <VERIFIED_ACTION_UUID> -o history.json

`history-index-fetch` downloads exactly one explicitly requested approved source slot. CaptureBrief does not silently initiate a whole-catalog multi-gigabyte sync.
