"""Private CaptureBrief original-source REVIEW DRAFT, never an approved report.

Binds one genuine SAM.gov PDF by full SHA-256, independently checks each
claim against its actual pages, and writes an operator-only HOLD packet.
No API calls, customer contact, payment, approval, watch, or public output.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re

SOURCE_SHA = "557bceeec58e625376d43678260075d1f96a831afe295035941addf77ae214e4"
SOURCE_BYTES = 290590
SOL = "2031JW27Q00011"
NOTICE = "0d961fc227d34d4da9a895f941e48a1e"

CHECKS = (
    ("DEADLINE_CONFLICT", "MATERIAL", ((1, r"11\s*/\s*09\s*/\s*2026\s+1000\s*ET"),
                                     (3, r"November\s+5\s*,?\s*2026\s+at\s+12:00\s+PM")),
     "The original RFQ states two incompatible response deadlines."),
    ("PRICE_HOLD_CONFLICT", "REVIEW", ((27, r"60\s+calendar\s+days"),
                                      (33, r"minimum\s+of\s+90\s+calendar\s+days")),
     "Price validity is expressed as both 60 and 90 calendar days."),
    ("OFF_TOPIC_CONTENT", "REVIEW", ((3, r"nationwide\s+court\s+reporting\s+services"),),
     "The software RFQ includes unrelated court-reporting language."),
    ("QUESTIONS_CUTOFF", "TIME_SENSITIVE", ((34, r"October\s+29\s*,?\s*2026\s+at\s+12:00\s+PM"),),
     "The first-party original sets an October 29 noon question cutoff."),
)


def source_findings(text_pages: list[str]) -> list[dict]:
    if not isinstance(text_pages, list) or len(text_pages) != 35:
        raise ValueError("Incomplete original-source page collection")
    found = []
    for code, severity, page_contract, detail in CHECKS:
        for page, pattern in page_contract:
            if re.search(pattern, text_pages[page - 1], re.I) is None:
                raise ValueError("Original source does not establish " + code)
        found.append({
            "code": code, "severity": severity,
            "original_pdf_pages": [item[0] for item in page_contract],
            "finding": detail, "source_text_matched": True,
            "human_review_verified": False,
        })
    return found


def prepare(original: bytes, proof: dict) -> tuple[dict, str]:
    if (not isinstance(original, bytes) or len(original) != SOURCE_BYTES or
            hashlib.sha256(original).hexdigest() != SOURCE_SHA):
        raise ValueError("Original source does not match the authenticated public evidence")
    if (not isinstance(proof, dict) or
            proof.get("status") != "FIRST_PARTY_PUBLIC_PDF_OBSERVED_REVIEW_REQUIRED" or
            proof.get("pdf_sha256") != SOURCE_SHA or
            proof.get("pdf_bytes") != SOURCE_BYTES or
            proof.get("notice_id") != NOTICE or proof.get("solicitation") != SOL or
            proof.get("source_link_bound_to_prior_v2_capture") is not True or
            any(proof.get(k) is not False for k in (
                "historical_family_complete", "independent_human_original_review_signed_off",
                "customer_release_authorized", "external_send_authorized", "payment_authorized",
                "production_recovery_key_custody_verified", "customer_case_admission_verified"))):
        raise ValueError("Public-original provenance or release boundary invalid")
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(original), strict=True)
    findings = source_findings([page.extract_text() or "" for page in reader.pages])
    packet = {
        "schema": "capturebrief-source-limited-founder-review-v1",
        "status": "FIRST_PARTY_CONFLICT_REVIEW_DRAFT_NOT_DELIVERABLE",
        "solicitation": SOL, "notice_id": NOTICE,
        "official_notice": "https://sam.gov/opp/" + NOTICE + "/view",
        "pdf_sha256": SOURCE_SHA, "pdf_bytes": SOURCE_BYTES, "pdf_pages": len(reader.pages),
        "assumption": "The response deadline has not changed.",
        "suggested_posture": "HOLD", "findings": findings,
        "complete_history_verified": False, "reviewer_approved": False,
        "real_customer_admitted": False, "production_backup_recovery_verified": False,
        "customer_release_authorized": False, "external_send_authorized": False,
        "payment_authorized": False, "automatic_upgrade_authorized": False,
        "watch_included": False,
    }
    lines = [
        "# CaptureBrief: FIRST-PARTY SOURCE REVIEW DRAFT (NOT FOR CUSTOMER DELIVERY)",
        "", "Assumption: The response deadline has not changed.",
        "Suggested posture: HOLD, source conflict unresolved.",
        "Original 35-page PDF SHA-256: " + SOURCE_SHA,
        "Official SAM.gov notice: " + packet["official_notice"], "",
        "## Observed findings", "",
    ]
    for f in findings:
        lines.append("- " + f["code"] + " [" + f["severity"] + "]: " + f["finding"] +
                     " PDF p. " + ", ".join(map(str, f["original_pdf_pages"])) + ".")
    lines += [
        "", "## Outstanding safeguards", "",
        "The complete official action/amendment set, all incorporated references, "
        "real business identity, independent human reviewer, production private "
        "off-device recovery and per-message send authorization remain unverified.",
        "", "NO CUSTOMER CONTACT, PAYMENT, DELIVERABLE, AUTOMATIC UPGRADE OR WATCH.",
    ]
    return packet, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-pdf", required=True)
    ap.add_argument("--source-proof", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args(argv)
    try:
        packet, markdown = prepare(
            Path(args.source_pdf).read_bytes(),
            json.loads(Path(args.source_proof).read_text(encoding="utf-8")),
        )
        root = Path(args.output_dir).expanduser().absolute()
        repo = Path(__file__).resolve().parents[1]
        if (root.exists() or root.is_relative_to(repo) or
                any(component.is_symlink() for component in root.parents)):
            raise ValueError("A new private output folder outside the repository is required")
        root.mkdir(mode=0o700, parents=True)
        for name, content in (
            ("review-packet.json", json.dumps(packet, indent=2, sort_keys=True) + "\n"),
            ("review-preview.md", markdown),
        ):
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
        print(json.dumps({"status": packet["status"], "findings": len(packet["findings"]),
                          "pdf_sha256": SOURCE_SHA, "customer_release_authorized": False,
                          "external_send_authorized": False}, sort_keys=True))
        return 0
    except Exception as exc:
        # Never leak private file paths, buyer details or provider-auth URLs.
        print(json.dumps({"status": "REVIEW_DRAFT_BLOCKED", "error_type": type(exc).__name__,
                          "customer_release_authorized": False,
                          "external_send_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
