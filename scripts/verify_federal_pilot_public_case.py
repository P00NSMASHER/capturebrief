"""Read-only real SAM.gov one-opportunity pilot rehearsal, NEVER customer fulfillment.

Uses the previously independently sourced current probe solicitation. Captures
a bounded current first-party API observation, attempts the exact public
official RFQ PDF and the documented management history endpoint, then makes a
synthetic (not real-buyer) case encrypted backup for a fresh-runner restore.
No private buyer input, automatic source approval, payment or external send.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.scoped_source import (
    ScopedApiRedirects, observe_scoped_case, retain_review_source, read_private_case,
)
from scripts.import_request_draft import import_request
from scripts.scoped_private_backup import create_backup
from tests.test_free_trial import free_draft

SOL = "2031JW27Q00011"
NOTICE = "0d961fc227d34d4da9a895f941e48a1e"
RESOURCE = "bef67716955a4d909f2cbf8b6b8533da"
FILENAME = "2031JW27Q00011 Global Macro - Final RFQ.pdf"
SAM_NOTICE = "https://sam.gov/opp/" + NOTICE + "/view"
PUBLIC_FILE = ("https://sam.gov/api/prod/opps/v3/opportunities/resources/files/"
               + RESOURCE + "/download?" + urlencode({"fn": FILENAME}))
# Public-data-only demo key. Never use as a real customer recovery key.
DEMO_KEY = b"DEMO_PUBLIC_GOVERNMENT_SOURCE_NO_CUSTOMER_NOT_A_PRODUCTION_SECRET_2026"
MAX_PDF = 2 * 1024 * 1024


class OfficialPdfRedirectBlocked(RuntimeError):
    """A blocked official attachment redirect, with NO signed URL disclosure."""

    def __init__(self, destination_host: str | None, response_code: int, location: str):
        host = (destination_host or "").lower()
        self.destination_host = host if re.fullmatch(r"[a-z0-9.-]{1,253}", host) else "UNSAFE_HOST"
        self.response_code = int(response_code) if isinstance(response_code, int) and 300 <= response_code <= 399 else 0
        self.location_sha256 = hashlib.sha256(location.encode("utf-8")).hexdigest()
        public_path = urlsplit(location).path
        self.path_sha256 = hashlib.sha256(public_path.encode("utf-8")).hexdigest()
        self.path_segment_count = len([part for part in public_path.split("/") if part])
        self.path_has_resource_id = RESOURCE in public_path.lower()
        self.path_looks_like_pdf = public_path.lower().endswith(".pdf")
        raw_names = [
            field.partition("=")[0] for field in urlsplit(location).query.split("&")
            if field
        ][:24]
        safe_names = {
            "X-Amz-Algorithm", "X-Amz-Credential", "X-Amz-Date",
            "X-Amz-Expires", "X-Amz-SignedHeaders", "X-Amz-Signature",
            "X-Amz-Security-Token", "response-content-disposition",
            "response-content-type", "response-cache-control",
            "response-content-language", "response-content-encoding",
            "response-expires", "x-id",
        }
        self.query_parameter_names = sorted(
            {name if name in safe_names else "OTHER_QUERY_FIELD" for name in raw_names}
        )
        super().__init__("Official source cross-host redirect blocked before connection")

    def safe_projection(self) -> dict:
        return {
            "redirect_host": self.destination_host,
            "redirect_status": self.response_code,
            "redirect_location_sha256_only": self.location_sha256,
            "redirect_path_sha256_only": self.path_sha256,
            "redirect_path_segment_count": self.path_segment_count,
            "redirect_path_contains_public_resource_id": self.path_has_resource_id,
            "redirect_path_pdf_extension": self.path_looks_like_pdf,
            "redirect_query_parameter_names_only": self.query_parameter_names,
        }


class SameHost(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        source = urlsplit(req.full_url)
        target = urlsplit(newurl)
        if (source.scheme != "https" or target.scheme != "https"
                or target.hostname != source.hostname
                or target.hostname not in {"sam.gov", "api.sam.gov"}
                or target.username or target.password
                or target.port not in (None, 443)):
            raise OfficialPdfRedirectBlocked(target.hostname, code, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_official_pdf(opener=None) -> tuple[bytes, dict]:
    """No third-party mirror may satisfy the original-file requirement."""
    open_ = opener or build_opener(SameHost()).open
    req = Request(PUBLIC_FILE, headers={
        "Accept": "application/pdf,application/octet-stream",
        "User-Agent": "CaptureBrief-public-source-readonly/1.0",
    })
    with open_(req, timeout=25) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname != "sam.gov":
            raise RuntimeError("Official PDF origin was not proven")
        length = response.headers.get("Content-Length")
        if length and (not length.isdigit() or int(length) > MAX_PDF):
            raise RuntimeError("Official PDF exceeds bounded file size")
        original = response.read(MAX_PDF + 1)
    if not 500 < len(original) <= MAX_PDF or not original.startswith(b"%PDF-"):
        raise RuntimeError("Expected public first-party PDF was not returned")
    if b"%%EOF" not in original[-4096:]:
        raise RuntimeError("Official PDF ends without expected trailer")
    # PDF may be an updated original. Hash, page count and text are reviewed,
    # never silently treated as the version originally posted on October 26.
    return original, {
        "status": "FIRST_PARTY_PDF_TRANSPORT_OBSERVED_REVIEW_REQUIRED",
        "source_host": "sam.gov", "sha256": hashlib.sha256(original).hexdigest(),
        "bytes": len(original), "publisher_human_reviewed": False,
    }


def read_pdf_deadlines(original: bytes) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(original), strict=True)
    if not 1 <= len(reader.pages) <= 90:
        raise RuntimeError("Document page count is outside approved limit")
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    # Report only whether date patterns appear, not extracted document text.
    found = {
        "november_05_2026": bool(re.search(r"\bNov(?:ember|\.)?\s+0?5\s*,?\s*2026\b", text, re.I)),
        "november_09_2026": bool(re.search(r"\bNov(?:ember|\.)?\s+0?9\s*,?\s*2026\b", text, re.I)),
    }
    return {"page_count": len(reader.pages), "machine_text_dates": found,
            "pdf_visual_human_review_completed": False}


def try_official_history(key: str, *, opener=None) -> dict:
    """Documented management API. An ordinary public key might lack permissions."""
    base = "https://api.sam.gov/prod/opportunity/v1/api/history/" + NOTICE
    url = base + "?" + urlencode({"api_key": key})
    req = Request(url, headers={"Accept": "application/json",
                                "User-Agent": "CaptureBrief-public-history-readonly/1.0"})
    open_ = opener or build_opener(SameHost()).open
    try:
        with open_(req, timeout=18) as response:
            final = urlsplit(response.geturl())
            if final.hostname != "api.sam.gov" or final.scheme != "https":
                raise RuntimeError("Official history final URL is not approved")
            raw = response.read(512 * 1024 + 1)
        if not 0 < len(raw) <= 512 * 1024:
            raise RuntimeError("Official history payload is empty or oversized")
        payload = json.loads(raw.decode("utf-8"))
        actions = payload.get("history") if isinstance(payload, dict) else None
        if not isinstance(actions, list) or not actions:
            return {"status": "HISTORY_UNVERIFIED_NO_COMPLETE_ACTION_SET",
                    "complete_first_party_history_verified": False}
        # An official endpoint response is evidence of observed actions, not
        # proof no other actions exist or a substitute for independent review.
        ids = [str(x.get("opportunityId") or x.get("noticeId") or "").lower()
               for x in actions if isinstance(x, dict)]
        if len(ids) != len(actions) or len(set(ids)) != len(ids) or NOTICE not in ids:
            return {"status": "HISTORY_UNVERIFIED_ACTION_SET_INCONSISTENT",
                    "complete_first_party_history_verified": False}
        return {"status": "HISTORY_OBSERVED_REVIEW_REQUIRED",
                "action_count": len(ids),
                "action_id_set_sha256": hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest(),
                "complete_first_party_history_verified": False}
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as exc:
        # Never leak exception strings: the management URL includes the API key.
        return {"status": "HISTORY_ENDPOINT_UNAVAILABLE_OR_UNAUTHORIZED",
                "error_type": type(exc).__name__,
                "complete_first_party_history_verified": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    key = os.environ.get("SAM_API_KEY", "")
    if not key:
        print(json.dumps({"status": "BLOCKED_NO_PRIVATE_SAM_API_KEY", "customer_delivery_authorized": False}))
        return 2
    root = Path(args.output_root).absolute()
    if root.exists():
        print(json.dumps({"status": "BLOCKED_PRIVATE_WORKSPACE_NOT_EMPTY"}))
        return 2
    root.mkdir(mode=0o700, parents=True)
    case_path, receipt_path, raw_path = (root / "case.json", root / "intake-receipt.json", root / "request.txt")
    sample = free_draft(assumptions=["The response deadline has not changed."]).replace(
        "c20a138049b94add92f0f32a41856585", NOTICE)
    raw_path.write_text(sample, encoding="utf-8")
    raw_path.chmod(0o600)
    import_request(str(raw_path), str(case_path), str(receipt_path),
                   imported_at=datetime.now(timezone.utc))
    case = read_private_case(case_path)
    private = root / "private"
    private.mkdir(mode=0o700)
    try:
        source = observe_scoped_case(
            case, solicitation_number=SOL, posted_from="10/25/2026",
            posted_to="10/28/2026", api_key=key, private_dir=private,
            opener=build_opener(ScopedApiRedirects()).open)
        if not source["selected_notice_matches_latest_api"]:
            raise RuntimeError("Actual current notice is not the selected exact notice")
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED_EXACT_PURSUIT_SAM_SOURCE",
                          "safe_error_type": type(exc).__name__,
                          "customer_delivery_authorized": False}))
        return 2

    doc = {"status": "FIRST_PARTY_PDF_NOT_YET_OBSERVED"}
    try:
        original, doc = fetch_official_pdf()
        doc.update(read_pdf_deadlines(original))
        input_file = root / "original-public-rfq.pdf"
        input_file.write_bytes(original)
        input_file.chmod(0o600)
        retain_review_source(case, original_file=input_file,
                             source_url=SAM_NOTICE, private_dir=private)
    except OfficialPdfRedirectBlocked as exc:
        doc = {"status": "BLOCKED_OFFICIAL_PDF_REDIRECT_TRANSPORT_REVIEW_REQUIRED",
               "publisher_human_reviewed": False, **exc.safe_projection()}
    except Exception as exc:
        doc = {"status": "BLOCKED_OFFICIAL_PDF_OR_DOCUMENT_REVIEW",
               "safe_error_type": type(exc).__name__,
               "publisher_human_reviewed": False}
    history = try_official_history(key)
    backup_path = root / "backup"
    backup_path.mkdir(mode=0o700)
    encrypted = backup_path / "public-case-rehearsal.cbak"
    try:
        b = create_backup(case_path, private, encrypted, DEMO_KEY)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED_PRIVATE_BACKUP",
                          "safe_error_type": type(exc).__name__,
                          "customer_delivery_authorized": False}))
        return 2
    # Only aggregate provenance leaves this isolated synthetic/public-source job.
    result = {
        "status": "PUBLIC_PILOT_CASE_SOURCE_AND_BACKUP_REHEARSAL",
        "source": source["status"], "solicitation_number": SOL,
        "selected_notice_matches_latest_api": True,
        "official_document": doc, "official_history": history,
        "backup_sha256": b["backup_sha256"],
        "backup_is_test_key_only": True,
        "source_history_complete_and_independently_reviewed": False,
        "client_identity_verified": False, "customer_report_delivered": False,
        "independently_retained_production_recovery_key": False,
        "customer_release_authorized": False, "payment_authorized": False,
        "external_send_authorized": False,
    }
    (root / "safe-proof.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
