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
- Full FY2027 original source bytes and independently computed complete-file
  SHA-256 remain **UNVERIFIED** pending a complete download/review.

The current production-approved catalog is STILL observed September 21, 2026,
current through FY2026; this machine/browser observation does NOT supply the
independent human approval required to amend that catalog.

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
- [ ] Obtain immutable approved-source active/archive CSV receipts, per-file
      SHA-256 and refreshed observation times for each required FY2027 year slot.
- [ ] Independently pass both Linux and Windows Product Core exact-head tests
      and protected-main review before any deployment or customer claim.

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
