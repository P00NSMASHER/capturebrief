# CaptureBrief SAM Source Policy

Updated: September 21, 2026

CaptureBrief separates technically reachable public web surfaces from sources approved for automated collection.

## Approved for automation

### SAM.gov Get Opportunities Public API v2
Official documentation: https://open.gsa.gov/api/get-opportunities-public-api/

Use for:
- latest-active opportunity details;
- first-party current-action evidence;
- current `resourceLinks` returned by the API.

CaptureBrief does not log or persist API keys.

### SAM.gov Data Services — Contract Opportunities extracts
Official Data Services pages:
- https://sam.gov/data-services/Contract%20Opportunities/datagov?privacy=Public
- https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public

Use for:
- action/version membership;
- active and archived public CSV evidence;
- source-file hashes and fiscal-year coverage receipts.

Data Services membership does **not** establish current-action ordering. Currentness remains a separate API/source receipt.

## Human-supervised evidence only

SAM.gov UI pages and undocumented web-UI implementation endpoints, including the resource-manifest path under `/api/prod/opps/v3/opportunities/.../resources`, may be retained as human-supervised public evidence when necessary to inspect deletion/tombstone state.

CaptureBrief production code must not poll, crawl, or automatically gather from those UI implementation surfaces. Saved human-supervised snapshots may be normalized, hashed, compared, and audited offline.

## Never automated by CaptureBrief

- authenticated SAM.gov UI scraping;
- private or restricted procurement portals;
- CUI, export-controlled, or credential-gated artifacts without explicit authorization;
- arbitrary crawling of SAM.gov pages;
- guessed download URLs not returned by an approved API or extract.

## Release consequence

If an approved automated source cannot prove a required fact, the case remains `SOURCE_LIMITED`, `UNPROVEN`, or `FAIL_CLOSED` until a permitted human-supervised observation or another approved source closes the gap.
