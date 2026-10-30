"""Read-only real-source component validation; never claims a live pursuit passed.

Fetches four immutable first-party GSA rule files, three bounded historical
SAM originals and the already first-party-listed FY2027 original through existing
approved transports. No source bytes, opportunity
identifiers, signed URLs, buyer data or credentials are printed or retained.
The JSON result is safe aggregate evidence, not production source approval.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.data_services import (
    ARCHIVE_DOWNLOAD, _decode_csv, download_extract, scan_extract_bytes,
)
from capturebrief_core.rule_registry import (
    load_source_catalog, to_trace_source_snapshot, validate_rule_source,
)
from capturebrief_core.rule_sync import fetch_pinned_gsa_rule
from capturebrief_core.decision_trace import passage
from scripts.pilot_preflight import inspect

RULES = (("gsa-far-dita", "52.204-21"), ("gsa-far-dita", "52.212-1"),
         ("gsa-dfars-dita", "252.204-7012"), ("gsa-dfars-dita", "252.204-7020"))
YEARS = (1999, 2000, 2001, 2027)
MAX_ARCHIVE_BYTES = 3_000_000
MAX_CURRENT_YEAR_BYTES = 8_000_000


def _error(error: Exception) -> dict:
    # Exception text may contain presigned source URLs. Expose only a type/code.
    result = {"status": "SOURCE_CHECK_BLOCKED", "error_type": type(error).__name__}
    safe_errors = {
        "Data Services extract Content-Length exceeds accepted bounds": "DECLARED_SOURCE_EXCEEDS_BOUND",
        "extract exceeds max_bytes during download": "SOURCE_EXCEEDS_BOUND",
        "Data Services extract did not match Content-Length": "SOURCE_LENGTH_MISMATCH",
        "Data Services full original requires HTTP 200": "FULL_ORIGINAL_HTTP_STATUS_REQUIRED",
        "Data Services full original cannot be a byte range": "PARTIAL_SOURCE_REJECTED",
    }
    if str(error) in safe_errors:
        result["error_code"] = safe_errors[str(error)]
    if isinstance(error, HTTPError):
        result["http_status"] = error.code
    return result


def validate_rule(catalog, source_id, citation, observed_at, *, fetcher=None) -> dict:
    record, receipt = fetch_pinned_gsa_rule(
        catalog, source_id=source_id, citation=citation,
        observed_at=observed_at, fetcher=fetcher,
    )
    if validate_rule_source(record):
        raise ValueError("Live rule normalization failed integrity validation")
    source, snapshot = to_trace_source_snapshot(
        record, source_id=f"LIVE-COMPONENT-{citation}", reviewer="automated component QA; not human applicability review",
    )
    lines = snapshot["text"].splitlines()
    checks = 0
    for paragraph in record["paragraphs"]:
        evidence = passage(snapshot, paragraph["line"], paragraph["line"], locator=paragraph["locator"])
        if evidence["quote"] != lines[paragraph["line"] - 1] or paragraph["text"] not in evidence["quote"]:
            raise ValueError("Real paragraph does not survive exact-passage conversion")
        checks += 1
    if not checks or source["content_sha256"] != receipt["source_sha256"]:
        raise ValueError("Live rule source was not bound to retained trace")
    mutated = copy.deepcopy(record)
    mutated["text"] += "\nUNSUPPORTED TEST ASSERTION"
    if "normalized_text_sha256" not in validate_rule_source(mutated):
        raise ValueError("Source-text mutation was not rejected")
    return {
        "status": "REAL_PINNED_RULE_COMPONENT_PASS", "citation": citation,
        "namespace": record["namespace"], "source_url": record["source_url"],
        "source_revision": record["source_revision"], "source_sha256": receipt["source_sha256"],
        "bytes": receipt["byte_length"], "embedded_or_labeled_edition": record["edition"],
        "edition_basis": record["edition_basis"], "exact_paragraph_checks": checks,
        "tampered_text_rejected": True, "latest_edition_asserted": False,
        "pursuit_applicability_verified": False,
    }


def validate_archive(year, *, downloader=None) -> dict:
    if year not in YEARS:
        raise ValueError("Only the four explicitly listed bounded source years are accepted")
    url = ARCHIVE_DOWNLOAD.format(fy=year)
    limit = MAX_CURRENT_YEAR_BYTES if year == 2027 else MAX_ARCHIVE_BYTES
    data = (downloader or download_extract)(url, max_bytes=limit)
    rows = list(csv.DictReader(io.StringIO(_decode_csv(data), newline="")))
    candidates = list(dict.fromkeys(" ".join((row.get("Sol#") or "").upper().split()) for row in rows))
    candidates = [x for x in candidates if x]
    if not candidates:
        raise ValueError("No historical solicitation is available for parser comparison")
    selected = list(dict.fromkeys(candidates[i] for i in (0, len(candidates)//2, len(candidates)-1)))
    # Independently bind the parser's normalized original-row projection
    # AND snapshot identity to the actual bytes read in this component run.
    # NoticeId equality alone misses a corrupted AAC, office, action date,
    # source year, record hash or different original CSV bearing the same IDs.
    def original_projection(row: dict) -> dict:
        raw_hash = hashlib.sha256(json.dumps(
            row, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        return {
            "notice_id": str(row.get("NoticeId") or "").strip(),
            "solicitation_number": str(row.get("Sol#") or "").strip(),
            "posted_date": str(row.get("PostedDate") or "").strip() or None,
            "notice_type": str(row.get("Type") or "").strip() or None,
            "active": str(row.get("Active") or "").strip() or None,
            "aac_code": str(row.get("AAC Code") or "").strip() or None,
            "office": str(row.get("Office") or "").strip() or None,
            "link": str(row.get("Link") or "").strip() or None,
            "row_sha256": raw_hash,
        }

    original_sha = hashlib.sha256(data).hexdigest()
    matched_rows = 0
    for solicitation in selected:
        parsed = scan_extract_bytes(data, source_url=url, source_kind="ARCHIVE",
                                    solicitation_number=solicitation, fiscal_year=year)
        expected = [original_projection(row) for row in rows
                    if " ".join((row.get("Sol#") or "").upper().split()) == solicitation]
        if not isinstance(parsed, dict) or not isinstance(parsed.get("matches"), list):
            raise ValueError("Product scanner source correlation missing")
        if (type(parsed.get("rows_scanned")) is not int
                or parsed["rows_scanned"] != len(rows)
                or parsed.get("source_kind") != "ARCHIVE"
                or parsed.get("fiscal_year") != year
                or parsed.get("source_url") != url
                or parsed.get("extract_sha256") != original_sha
                or sorted(parsed["matches"], key=lambda item: item["notice_id"])
                   != sorted(expected, key=lambda item: item["notice_id"])):
            raise ValueError("Product scanner disagrees with original public row or source receipt")
        matched_rows += len(expected)
    return {
        "status": ("REAL_CURRENT_YEAR_EXTRACT_COMPONENT_PASS" if year == 2027
                   else "REAL_HISTORICAL_EXTRACT_COMPONENT_PASS"), "fiscal_year": year,
        "source_url": url, "source_sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data), "original_rows": len(rows),
        "solicitation_groups_checked": len(selected), "matched_rows_checked": matched_rows,
        "current_pursuit_verified": False, "raw_bytes_persisted": False,
        "approved_catalog_source": False, "automated_unreviewed_source_observation": True,
    }


def run(*, observed_at: datetime | None = None, rule_fetcher=None, archive_downloader=None) -> dict:
    now = observed_at or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("Observation time must include a timezone")
    stamp = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    catalog = load_source_catalog(ROOT / "RULE-SOURCE-CATALOG.json")
    checks = []
    for source_id, citation in RULES:
        try:
            check = validate_rule(catalog, source_id, citation, stamp, fetcher=rule_fetcher)
        except Exception as error:
            check = {"citation": citation, **_error(error)}
        checks.append(check)
    for year in YEARS:
        try:
            check = validate_archive(year, downloader=archive_downloader)
        except Exception as error:
            check = {"fiscal_year": year, **_error(error)}
        checks.append(check)
    preflight = inspect(now=now, stage="admission")
    return {
        "schema": "capturebrief-live-public-component-validation-v1",
        "observed_at": stamp, "synthetic_transport": rule_fetcher is not None or archive_downloader is not None,
        "status": "LIVE_PURSUIT_ACCEPTANCE_NOT_ESTABLISHED",
        "component_checks": checks,
        "component_pass_count": sum(x["status"].endswith("_PASS") for x in checks),
        "component_check_count": len(checks),
        "sam_current_api_key_available_in_this_environment": bool(os.environ.get("SAM_API_KEY")),
        "sam_current_api_observation_performed": False,
        "current_private_source_index_supplied": False,
        "admission_preflight": preflight,
        "paid_customer_or_revenue_evidence": False,
        "customer_delivery_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Aggregate validation JSON, not raw sources")
    args = parser.parse_args(argv)
    result = run()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    # Missing live-pursuit evidence must never produce a green acceptance job.
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
