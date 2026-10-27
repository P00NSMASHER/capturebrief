# CaptureBrief real-source validation — October 27, 2026

**8 of 8 source-component checks passed. Live customer-pursuit acceptance is
not established.** This report deliberately separates genuine source bytes
from synthetic regression fixtures and customer delivery evidence.

Machine-readable results and tested component hashes:
[`research/live_public_component_validation_20261027.json`](research/live_public_component_validation_20261027.json).
Observation began **2026-10-27 13:43:22 UTC**. Engine base:
`93b4923dd10739fae98abaf658ee7437248f35ba`; the new validator's exact file digest
is retained in the result alongside the production scanner and rule modules.

## Official data exercised through product code

| Source | Actual bytes | Records or exact passages | Result |
|---|---:|---:|---|
| GSA FAR 52.204-21, pinned official revision | 11,335 | 28 paragraphs | Source parse, source/hash mapping and tamper rejection passed |
| GSA FAR 52.212-1, pinned official revision | 26,693 | 53 paragraphs | Same checks passed |
| GSA DFARS 252.204-7012, pinned official revision | 20,591 | 56 paragraphs | Same checks passed |
| GSA DFARS 252.204-7020, pinned official revision | 18,658 | 61 paragraphs | Same checks passed |
| Official SAM FY1999 original | 2,157,841 | 1,415 CSV rows | Production scanner matched 3 independently selected solicitation groups |
| Official SAM FY2000 original | 1,770,559 | 1,047 CSV rows | Production scanner matched 3 independently selected solicitation groups |
| Official SAM FY2001 original | 2,406,436 | 1,467 CSV rows | Production scanner matched 3 independently selected solicitation groups |
| Official SAM FY2027 original | 4,518,793 | 3,082 CSV rows | Production scanner matched 3 independently selected solicitation groups |

Across the four extracts, the scanner inspected **7,011 rows**. Independent
standard CSV parsing compared exact notice memberships for **12 solicitation
groups / 24 matching rows**. Across the four official rule files, **198**
paragraphs survived exact source-to-trace mapping. Mutating normalized rule
text was rejected by the existing source-integrity validator.

The FY2027 source is the exact already first-party-listed archive described in
[`FY2027-CATALOG-REVIEW-CANDIDATE.md`](FY2027-CATALOG-REVIEW-CANDIDATE.md). Its
new full-byte SHA-256 is
`ea1d2c726566fc9546e80f0ce559f77b104809ad5c86e2095b9935bc03648ea0`.
This is an **automated, unreviewed current-year archive observation**. Archived
membership is not latest-active API currentness or catalog approval.

All downloads used existing approved, redirect-guarded production transport.
Each historical original was capped at 3 MB; the FY2027 original at 8 MB after
a header-only observation showed its current 4.52 MB size. The initial 3 MB
attempt correctly refused that file before accepting it. No raw original,
signed redirect URL, record identifier or customer data was published.

The GSA files are real official **pinned editions**, not a claim that these
are the latest applicable legal editions. Actual applicability and incorporated
versions remain pursuit-specific review work.

## A real freshness discrepancy

The earlier October 20 frozen size expectations for FY1999/FY2000/FY2001 no
longer match these live originals: sizes increased by **5 / 25 / 5 bytes**.
The existing frozen-original semantic audit correctly refused the changed
sizes. Those historical observations were preserved. The new test fetched
fresh bounded originals and exercised the current production parser; it did
not rewrite old hashes, approve a source catalog, or convert stale evidence
into current evidence.

The FY2027 original has also grown from the October 19 recorded 1,607,260
bytes / 1,104 rows to 4,518,793 bytes / 3,082 rows at this observation. This is
why an old source checksum cannot support a new customer decision.

## What still blocks a completed live pursuit

- `BLOCKED_STALE_CATALOG`: production-approved catalog ends at FY2026 while
  the current date is in FY2027.
- `BLOCKED_CATALOG_STALE`: a private source index cannot override that catalog.
  This test supplied no retained complete private source index or recovery proof.
- No `SAM_API_KEY` was available in this test environment. No current-active
  Opportunities API observation was performed. Web pages and archive rows
  were not substituted for that proof.
- No genuine customer case, source/packet review, checked customer bundle,
  provider-verified delivery or actual 14-day watch was completed by this test.
- The existing paid-offer preflight separately requires inbox reconciliation,
  operator review, live-payment verification and release evidence. The free
  route creates no payment requirement or paid status; it keeps the source,
  identity, review and delivery requirements.

The repeatable command intentionally exits **3** even when all source
components pass, because no live-pursuit acceptance has been established:

```sh
python scripts/validate_live_public_sources.py --output /private/source-component-check.json
```

## Trial and customer-journey engineering

The free request now has an explicit parser contract, an idempotent private
ten-business reservation registry and a free-only report builder. It enforces
exactly one selected assumption, a consistent operator-reviewed business
identity, immutable reservation scope, no charge and no automatic upgrade.
The private report includes the evidence appendix and omits a paid watch.
Existing evidence, source integrity and external-send controls remain active.

The actual candidate website JavaScript-generated **SCOPE_FIRST**, **PAID** and
**FREE_CHECK** clipboard drafts were passed into the actual Python parser.
All three produced only unverified intake, preserving their respective offer
claims without inventing payment, source evidence or send authorization.
This repairs a real mismatch between the published request format and core.
The current company deployment contract is also corrected in
[`DEPLOYMENT-TARGET.md`](DEPLOYMENT-TARGET.md).

The complete baseline had **710 passing tests**. After the changes, **722 tests
passed** in the complete local regression run (15.3 seconds). The added trial regressions
cover one-question limits, duplicate businesses/requests, concurrent retries,
cohort capacity, changed scope, tampered receipts, private storage, blocked
source cases, and one-result report generation. The positive report-generation
test uses the existing technical fixture at its historical clock; it is
**software evidence only**, not the missing real-pursuit acceptance.

The maintained website-to-core workflow now triggers on relevant PRs and main
changes, pins website candidate `41d6c563dd4c2cdbb3eedb2dcd13ae0a4828e40e`,
executes its actual three-mode JavaScript composer against the current core,
and retains Chromium/WebKit rendered acceptance. The local actual-JS check
passed. Rendered two-browser acceptance is a separate CI result; this report
does not claim it ran in the local Python environment, which lacks Playwright.
