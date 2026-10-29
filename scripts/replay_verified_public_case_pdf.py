"""Re-use one fresh, authenticated, public-only SAM API receipt without a new API call.

Input is immutable GitHub Actions encrypted artifact from main-only source run
40737843155. The public demo key is NOT usable for customer confidentiality.
No SAM_API_KEY, user data, human reviewer signoff, payment or external send.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capturebrief_core.scoped_source import (
    private_root, read_private_case, verify_scoped_capture, retain_review_source,
)
from scripts.scoped_private_backup import restore_backup, create_backup, verify_backup
from scripts.verify_federal_pilot_public_case import (
    SOL, NOTICE, PUBLIC_FILE, SAM_NOTICE, DEMO_KEY,
    _require_exact_original_resource, fetch_official_pdf, read_pdf_deadlines,
)

PINNED_INPUT_BACKUP_SHA256 = "c4cccab46991eedad2a903c20e5d1038603135c21b860ccc1309daad666ef4e9"
PINNED_SOURCE_RUN_ID = 40737843155
PINNED_SOURCE_MAIN_COMMIT = "d4a8f522054a72ca58a884ed8685e3cbc5f540aa"
EXPECTED_LISTED_BYTES = 290590


def _verify_prior_proof(proof: dict) -> bool:
    required = {
        "status", "solicitation_number", "source",
        "selected_notice_matches_latest_api", "backup_is_test_key_only",
        "backup_sha256", "client_identity_verified",
        "customer_release_authorized", "payment_authorized",
        "external_send_authorized", "source_history_complete_and_independently_reviewed",
        "independently_retained_production_recovery_key",
        "official_document", "official_history",
    }
    optional = {"customer_report_delivered"}
    if not isinstance(proof, dict) or not required.issubset(proof) or set(proof) - required - optional:
        raise ValueError("Prior public source proof has an unexpected schema")
    if (proof["status"] != "PUBLIC_PILOT_CASE_SOURCE_AND_BACKUP_REHEARSAL" or
            proof["solicitation_number"] != SOL or
            proof["source"] != "SCOPED_SAM_SOURCE_OBSERVED_REVIEW_REQUIRED" or
            proof["selected_notice_matches_latest_api"] is not True or
            proof["backup_is_test_key_only"] is not True or
            proof["backup_sha256"] != PINNED_INPUT_BACKUP_SHA256 or
            any(proof[k] is not False for k in (
                "client_identity_verified", "customer_release_authorized",
                "payment_authorized", "external_send_authorized",
                "source_history_complete_and_independently_reviewed",
                "independently_retained_production_recovery_key",
            )) or
            proof.get("customer_report_delivered", False) is not False or
            not isinstance(proof["official_document"], dict) or
            proof["official_document"].get("publisher_human_reviewed") is not False
            and proof["official_document"].get("publisher_human_reviewed") is not None or
            not isinstance(proof["official_history"], dict) or
            proof["official_history"].get("complete_first_party_history_verified", False) is not False):
        raise ValueError("Prior source input claims an unproved customer or publisher authority")
    return True


def _date_pages(original: bytes) -> dict:
    from pypdf import PdfReader
    from scripts.verify_federal_pilot_public_case import read_pdf_deadlines
    pages = PdfReader(io.BytesIO(original), strict=True).pages
    if not 1 <= len(pages) <= 90:
        raise ValueError("Official PDF pages exceed bounded review")
    candidates = {
        "november_05_2026": re.compile(r"\b(?:Nov(?:ember|\.)?\s+0?5\s*,?\s*2026|11[/.-]0?5[/.-]2026)\b", re.I),
        "november_09_2026": re.compile(r"\b(?:Nov(?:ember|\.)?\s+0?9\s*,?\s*2026|11[/.-]0?9[/.-]2026)\b", re.I),
    }
    identified = {label: [] for label in candidates}
    for i,page in enumerate(pages,1):
        txt=page.extract_text() or ""
        for key,reg in candidates.items():
            if reg.search(txt):
                identified[key].append(i)
    return {"page_count":len(pages), "candidate_date_page_numbers":identified,
            "machine_text_date_summary":read_pdf_deadlines(original)}


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--private-output", required=True)
    args=ap.parse_args(argv)
    try:
        source=Path(args.artifact_dir).expanduser().absolute()
        original_archive=source/"backup"/"public-case-rehearsal.cbak"
        previous=json.loads((source/"safe-proof.json").read_text(encoding="utf-8"))
        _verify_prior_proof(previous)
        if hashlib.sha256(original_archive.read_bytes()).hexdigest()!=PINNED_INPUT_BACKUP_SHA256:
            raise ValueError("Previous encrypted source receipt differs from pinned capture")
        private=Path(args.private_output).expanduser().absolute()
        if private.exists():
            raise ValueError("Private replay destination must be new")
        private.mkdir(mode=0o700,parents=True)
        private_root(private)
        restored=restore_backup(original_archive,private/"recovered",DEMO_KEY)
        case_path=private/"recovered"/"intake-case.json"
        case=read_private_case(case_path)
        captures=list((private/"recovered"/"evidence").glob("sam-current-*.json"))
        if len(captures)!=1:
            raise ValueError("Prior signed case must have exactly one SAM API observation")
        captured=json.loads(captures[0].read_text(encoding="utf-8"))
        checked=verify_scoped_capture(case,captured,now=datetime.now(timezone.utc))
        if _require_exact_original_resource(checked) != PUBLIC_FILE:
            raise ValueError("Exact official original source was not retained")
        if restored["file_count"] != 2:
            raise ValueError("Unexpected prior encrypted source file count")
        original,receipt=fetch_official_pdf()
        page_evidence=_date_pages(original)
        raw_path=private/"retrieved-public-original.pdf"
        raw_path.write_bytes(original)
        raw_path.chmod(0o600)
        case_root=private/"retained"
        case_root.mkdir(mode=0o700)
        case_folder=case_root/("case-"+restored["case_tag"])
        case_folder.mkdir(mode=0o700)
        target=case_folder/captures[0].name
        shutil.copyfile(captures[0],target)
        target.chmod(0o600)
        retained=retain_review_source(
            case,original_file=raw_path,source_url=SAM_NOTICE,private_dir=case_root)
        if retained["source_sha256"]!=receipt["sha256"]:
            raise ValueError("Retained public original SHA differs from fetched source")
        backup_dir=private/"backup"
        backup_dir.mkdir(mode=0o700)
        out=backup_dir/"public-case-with-official-original.cbak"
        bundle=create_backup(case_path,case_root,out,DEMO_KEY)
        verified=verify_backup(out,DEMO_KEY)
        if verified["file_count"]!=4:
            raise ValueError("Original PDF source was not included in authenticated backup")
        result={
            "status":"FIRST_PARTY_PUBLIC_PDF_OBSERVED_REVIEW_REQUIRED",
            "solicitation":SOL, "notice_id":NOTICE,
            "prior_main_only_authenticated_source_commit":PINNED_SOURCE_MAIN_COMMIT,
            "prior_source_run_id":PINNED_SOURCE_RUN_ID,
            "input_sha256":PINNED_INPUT_BACKUP_SHA256,
            "source_at":checked["observed_at"],
            "source_link_bound_to_prior_v2_capture":True,
            "pdf_sha256":receipt["sha256"],
            "pdf_bytes":receipt["bytes"],
            "size_matches_official_oct26_public_listing":receipt["bytes"]==EXPECTED_LISTED_BYTES,
            "signed_delivery_host":receipt["signed_delivery_host"],
            "source_file_page_candidates":page_evidence,
            "offdevice_new_test_backup_sha256":bundle["backup_sha256"],
            "offdevice_new_test_bundle_files":bundle["file_count"],
            "historical_family_complete":False,
            "independent_human_original_review_signed_off":False,
            "customer_release_authorized":False,
            "external_send_authorized":False,
            "payment_authorized":False,
            "production_recovery_key_custody_verified":False,
            "customer_case_admission_verified":False,
        }
        (private/"safe-proof.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as exc:
        # Never print exception strings, signed URL, source bytes or buyer fields.
        print(json.dumps({"status":"BLOCKED_FIRST_PARTY_PUBLIC_PDF_REPLAY",
                          "safe_error_type":type(exc).__name__,
                          "source_approval":False,
                          "customer_release_authorized":False,
                          "payment_authorized":False,
                          "external_send_authorized":False},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
