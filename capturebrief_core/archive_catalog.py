from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .model import canonical_json, sha256_hex

ARCHIVE_CATALOG_VERSION = "sam-contract-opportunities-archives-2026-09-21"
ARCHIVE_CATALOG_SOURCE_PAGE = "https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public"
ARCHIVE_CATALOG_OBSERVED_AT = "2026-09-21T14:29:00+00:00"

# Human-supervised snapshot of the first-party SAM Data Services archive listing observed
# September 21, 2026. The page listed FY1970, FY1980, every FY1998-FY2026, and FY2030.
# Future-listed years are retained as catalog evidence but are never required before their FY.
ARCHIVE_CATALOG_YEARS = (1970, 1980, *tuple(range(1998, 2027)))
ARCHIVE_CATALOG_FUTURE_LISTED_YEARS = (2030,)
ARCHIVE_CATALOG_CURRENT_THROUGH_FY = 2026


class ArchiveCatalogStale(RuntimeError):
    pass


def fiscal_year_for_datetime(value: datetime | None = None) -> int:
    value = value or datetime.now(timezone.utc)
    return value.year + 1 if value.month >= 10 else value.year


def catalog_snapshot() -> dict[str, Any]:
    payload = {
        "catalog_version": ARCHIVE_CATALOG_VERSION,
        "source_url": ARCHIVE_CATALOG_SOURCE_PAGE,
        "observed_at": ARCHIVE_CATALOG_OBSERVED_AT,
        "observation_mode": "HUMAN_SUPERVISED",
        "archive_years": list(ARCHIVE_CATALOG_YEARS),
        "future_listed_years": list(ARCHIVE_CATALOG_FUTURE_LISTED_YEARS),
        "current_through_fy": ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
    }
    return {**payload, "catalog_sha256": sha256_hex(canonical_json(payload))}


def catalog_years_for_fiscal_year(fiscal_year: int) -> list[int]:
    if fiscal_year > ARCHIVE_CATALOG_CURRENT_THROUGH_FY:
        raise ArchiveCatalogStale(
            f"archive catalog snapshot is current only through FY{ARCHIVE_CATALOG_CURRENT_THROUGH_FY}; "
            f"refresh the human-supervised SAM Data Services catalog before FY{fiscal_year}"
        )
    return [year for year in ARCHIVE_CATALOG_YEARS if year <= fiscal_year]


def validate_catalog_snapshot(snapshot: dict[str, Any], *, fiscal_year: int) -> bool:
    expected = catalog_snapshot()
    if snapshot != expected:
        return False
    try:
        years = catalog_years_for_fiscal_year(fiscal_year)
    except ArchiveCatalogStale:
        return False
    return set(years).issubset(set(snapshot.get("archive_years", [])))
