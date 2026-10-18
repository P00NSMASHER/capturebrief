# FY2027 SAM.gov archive catalog — review candidate (NOT APPROVED)

Prepared October 18, 2026 for a supervised CaptureBrief first-pilot release.

**This is NOT a new authoritative source catalog and does not authorize
FULL_CATALOG release. Do not merge a production version bump from this note
without a reviewer checking the actual live first-party catalog and retaining
the reviewed source evidence.**

## Observations available

Official read-only page:
https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public

A separate live first-party webpage inspection on October 18, 2026 reported
the following filenames visibly listed as Public items:

- FY2026_archived_opportunities.csv
- FY2027_archived_opportunities.csv
- FY2029_archived_opportunities.csv
- FY2030_archived_opportunities.csv

FY2028 was **not established** from that observation. Neither a missing
FY2028 nor a listing of future files proves a data gap, download success or
record completeness. The observed list was partial; no complete year inventory
or downloadable file bytes were independently retained. The current approved
product catalog remains observed September 21, 2026, current through FY2026.

## Source recertification: exact checks to perform

- [ ] Independently load the above *first-party page* at the review time.
- [ ] Save the complete visible Contract Opportunities archive-year inventory
      including any additional years and exact filename casing. Never silently
      infer FY2028 or another year.
- [ ] Retain a source snapshot or independently verifiable review evidence,
      exact UTC observed time, reviewer identity and review reference.
- [ ] Compare the approved FY2026 year set (FY1970, FY1980, FY1998-FY2026) to
      the new first-party inventory. Resolve all missing/additional-year
      discrepancies, including FY2027 and the reported future FY2029/FY2030.
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
