# FY2027 SAM.gov archive catalog — review candidate (NOT APPROVED)

Prepared October 18, 2026 for a supervised CaptureBrief first-pilot release.

**This is NOT a new authoritative source catalog and does not authorize
FULL_CATALOG release. Do not merge a production version bump from this note
without a reviewer checking the actual live first-party catalog and retaining
the reviewed source evidence.**

## Observations available

Official read-only page:
https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public

The October 19, 2026 independent **read-only browser observation**
inspected both the first-party rendered listing and the official SAM.gov
listing API. UTC observation window: 04:59:14Z to 05:00:36Z.

Official listing API (public, OBSERVATION ONLY — not approved for automated
bulk acquisition in CaptureBrief's source policy):
https://sam.gov/api/prod/fileextractservices/v1/api/listfiles?domain=Contract%20Opportunities%2FArchived%20Data&privacy=Public

All **36** visible filenames were reported PUBLIC, as follows:

- FY1969_archived_opportunities.csv
- FY1970_archived_opportunities.csv
- FY1980_archived_opportunities.csv
- FY1981_archived_opportunities.csv
- Every year FY1998_archived_opportunities.csv through
  FY2027_archived_opportunities.csv inclusive, with no gaps in that range
- FY2029_archived_opportunities.csv
- FY2030_archived_opportunities.csv

**FY2028 was NOT listed** in the live 36-entry source inventory.
FY1969 and FY1981 are newly observed relative to the older approved snapshot.
Their presence must be explicitly reviewed; do not silently adopt the old
year list plus FY2027 and omit those earlier years.

FY2027 original object metadata:
- Name: FY2027_archived_opportunities.csv
- Metadata privacy: Public
- SAM UI Date Modified: Oct 11, 2026
- Original official-listing S3 href:
  https://s3.amazonaws.com/falextracts/Contract%20Opportunities/Archived%20Data/FY2027_archived_opportunities.csv
- A READ-ONLY Range bytes=0-0 probe returned HTTP 206 with
  Content-Range bytes 0-0/1607260; 1,607,260 total bytes.
- S3 Last-Modified: 2026-10-18 14:51:03 GMT.
- S3 ETag: 342a9a79f252ba732c347376f4efa66f
  (not asserted to be a SHA-256 checksum).
- At that earlier time only a one-byte probe had been completed. A later,
  separately documented complete-object read is described below.

The current production-approved catalog is STILL observed September 21, 2026,
current through FY2026; this machine/browser observation does NOT supply the
independent human approval required to amend that catalog.

## Exact machine-readable candidate and offline validation

The public observation is frozen in
`research/sam_archives_observation_20261019.json`. It records the
36 observed filename strings in original sorted order, the first-party
listing/API URLs, observation window, and a read-only one-byte FY2027 object
probe. Its exact browser provenance is explicitly **UNREVIEWED**.

Run offline without credentials or network calls:

    python scripts/reconcile_sam_catalog_candidate.py

The output identifies the four filename additions relative to the last
pinned FY2026 catalog (**FY1969, FY1981, FY2027, FY2029**) and retains
future listed FY2029/FY2030 separately. It rejects renamed/duplicate years,
invented FY2028, changed observation timestamps, spoofed source URLs, and
fabricated claims that FY2027's full source bytes or human review were
completed. The tool cannot update the production catalog or authorize a
FULL_CATALOG claim.

This is a reproducible review *candidate*, not a source attestation. The
complete FY2027 object read and checksum are documented below. That automated
read did not retain the original on the CI runner and does not establish the
complete private source index or approved catalog. Source review and durable
retention still need independently verifiable evidence.

## October 19 full original-file checksum — automated, unreviewed

A one-time **read-only GitHub Actions source probe** successfully downloaded
the complete official-listing S3 object from the exact first-party-listed
URL, prohibited redirect following, checked full HTTP 200, verified required
CSV columns, counted data rows and computed a streaming SHA-256 digest.

- Source proof workflow: [GitHub Actions #39205786451](https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451)
- Original object bytes read: **1,607,260**
- CSV records (excluding header): **1,104**
- SHA-256: `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`
- S3 last modified: 2026-10-18 14:51:03 GMT.
- S3 ETag: `342a9a79f252ba732c347376f4efa66f` (not represented as SHA).
- Full raw bytes **were read but not retained**: the CI runner deleted its
  temporary original file. A digest is not a replacement for locally
  retained original bytes in the approved source-history index.
- Machine-readable proof: `research/fy2027_original_bytes_observation_20261019.json`.
- Result status: **AUTOMATED_UNREVIEWED_PUBLIC_ORIGIN_BYTES**.
  This does **not** grant catalog signoff, source provenance review,
  full historical coverage or permission to release a customer package.

## Source recertification: exact checks to perform

- [ ] Independently load the above *first-party page* at the review time.
- [ ] Save the complete visible Contract Opportunities archive-year inventory
      including any additional years and exact filename casing. Never silently
      infer FY2028 or another year.
- [ ] Retain a source snapshot or independently verifiable review evidence,
      exact UTC observed time, reviewer identity and review reference.
- [x] Propose a complete explicit observed inventory (36 first-party listing
      entries) without inventing FY2028, but do NOT approve it.
- [ ] Compare the approved FY2026 year set (FY1970, FY1980, FY1998-FY2026) to
      the live inventory including **new FY1969 and FY1981**, FY2027,
      and future-listed FY2029/FY2030; retain review evidence.
- [ ] Only then propose to update archive_catalog.py's version, source
      observation timestamp, approved archive years, and current_through_fy.
      A bot's read-only browsing is not a human-reviewed catalog signoff.
- [ ] Require whole-catalog hash consistency tests and explicit negative
      controls for unapproved future fiscal years and edited snapshot hashes.
- [x] Calculate and independently log an automated SHA-256 for the complete
      FY2027 public object (original bytes were not retained by CI).
- [ ] Independently review and durably retain original approved-source active
      and archive CSV bytes for **all** required FY2027 year slots, with
      per-file SHA-256 and refreshed checked-at timestamps in a private index.
- [ ] Independently pass both Linux and Windows Product Core exact-head tests
      and an authorized merge before any deployment or customer claim. Passing
      code review or CI does not substitute for the source evidence above.

## Release boundary

A filename listed in SAM.gov does **not** prove that a full source is available,
that all source years have fresh approved bytes, or that a target pursuit has
complete history. CaptureBrief must remain fail-closed at FY2027 until these
facts are independently established and approved. Narrowly scoped alternate
history claims, where the core explicitly supports them, must be disclosed as
limited coverage and must never be labeled FULL_CATALOG.

Operator can inspect the current blocking state using the read-only command:

    python scripts/pilot_preflight.py --as-of 2026-10-18T12:00:00Z

No API key, archive contents, customer data or protected source bytes are
included in this public candidate record.

## October 22 operational correction

The catalog and source-retention hold remains in force. The retention and
private-operations utilities were integrated by
[PR #69](https://github.com/P00NSMASHER/capturebrief/pull/69); merging utilities
does not prove they have populated and recovered the required private index.

The bounded [FY2027 public source byte proof workflow](.github/workflows/capturebrief-fy2027-source-byte-proof.yml)
now runs when its definition changes on `main` and can be manually dispatched.
It previously targeted only an obsolete pilot branch. Each successful run reads
the exact previously listed public object, validates its CSV structure and full
HTTP response, computes its current SHA-256, and retains a seven-day JSON receipt
with the run ID and commit. The original CSV and response headers are removed.
The receipt explicitly marks listing refresh, private retention, source-index
update, off-device restore and customer release as unproven. Retrieve the exact
run receipt; the historical October 19 checksum above is not a fresh observation.

To close customer readiness, the remaining evidence is:

1. A new approved first-party catalog observation, including every actual
   listing addition or removal; the October 19 candidate contains 34 archive
   slots at or before FY2027 and two future slots. Never infer missing FY2028.
2. Fresh, verified original bytes for those approved archive slots **and the
   active extract**, with matching private index receipts. A fresh FY2027-only
   checksum closes only that single-object observation.
3. Protected retention and a verified independent recovery of the private
   evidence. A local backup file or checksum alone is not a restore test.
4. A current admission preflight against that real index:
   `python scripts/pilot_preflight.py --stage admission --history-index <private-index> --verify-source-bytes --source-snapshot-root <private-extracts>`.
   Omitting `--as-of` evaluates the actual current fiscal year.

No production catalog version, year coverage, payment proof, release gate or
customer-delivery status was promoted by this operational correction.
