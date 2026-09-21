# CaptureBrief Contract Opportunities Archive Catalog

Observed: September 21, 2026  
Source: https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public  
Observation mode: human-supervised first-party source snapshot

## Catalog snapshot

The SAM Data Services Archived Data listing observed on September 21, 2026 exposed Contract Opportunities archive files for:

- FY1970
- FY1980
- every fiscal year FY1998 through FY2026
- FY2030, which is future-listed and retained as catalog evidence but is not required for a FY2026 completeness claim

CaptureBrief pins that observation in `capturebrief_core/archive_catalog.py`. The catalog object carries its own SHA-256 and an explicit `current_through_fy = 2026`.

## Product rule

A `FULL_CATALOG` history receipt for FY2026 is complete only when the reusable Data Services index has:

1. the current active Contract Opportunities extract; and
2. a current source snapshot for every cataloged archive year at or before FY2026.

CaptureBrief does not infer the family start year from an amendment number, empty year, row order, `PostedDate` tie, UUID ordering, or a third-party latest pointer.

The index is deliberately broader than any one pursuit. Large SAM CSVs are hashed and indexed once, then reused across customer cases.

## Refresh rule

When the evaluated fiscal year moves beyond the catalog's pinned `current_through_fy`, the catalog is stale by definition. CaptureBrief must perform and record a new human-supervised first-party catalog observation before a `FULL_CATALOG` receipt can become releasable for the newer fiscal year.

## Why this matters

The catalog snapshot is source metadata, not a claim that every listed file contains an action for a given solicitation. Its job is to prove the universe of public archive slots CaptureBrief was obligated to inspect. The actual history receipt still retains per-action Data Services row hashes and explicitly states that Data Services membership does not establish currentness or authoritative ordering.


## Freshness

Archive-slot presence is not permanent proof of currentness. GSA documents active notices as updated daily and archived notices as updated weekly. The index therefore separately records the current slot check state and requires periodic approved first-party revalidation before a `FULL_CATALOG` receipt can be released.

A content hash identifies immutable bytes; a fresh source check proves those bytes are still the current extract for that slot. CaptureBrief keeps those claims separate.
