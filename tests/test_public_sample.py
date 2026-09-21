from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class PublicDecisionEvidenceSampleTests(unittest.TestCase):
    def test_homepage_points_primary_sample_to_decision_evidence(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertIn('href="decision-evidence-sample.html">View Decision Evidence sample</a>',html)
        self.assertIn('href="decision-evidence-sample.html">Sample</a>',html)

    def test_sample_is_explicitly_illustrative_and_contains_product_contract(self):
        html=(ROOT/"decision-evidence-sample.html").read_text(encoding="utf-8")
        self.assertIn("Illustrative format — not a real solicitation.",html)
        self.assertIn("Exact source-version delta",html)
        self.assertIn("REVIEWED RULE VERSION",html)
        self.assertIn("Four separate evidence planes",html)
        self.assertIn("Candidate index",html)
        self.assertIn("Exact public bytes",html)
        self.assertIn("Memo authority",html)
        self.assertIn("Pursuit applicability",html)
        self.assertIn("Finding the memo did not make it applicable.",html)
        self.assertIn("SOURCE-LIMITED",html)
        self.assertIn("Included 14-day watch",html)
        self.assertIn("delivery-manifest.json",html)
        self.assertIn("watch-baseline.json",html)
        self.assertIn("The prior decision remains preserved",html)

    def test_sample_document_hashes_match_illustrative_text(self):
        html=(ROOT/"decision-evidence-sample.html").read_text(encoding="utf-8")
        texts=[
            "ILLUSTRATIVE\nL.3: Technical response must not exceed 20 pages.",
            "ILLUSTRATIVE\nAmendment 02 replaces L.3: technical response must not exceed 15 pages.\nDR-7 May 2025 remains incorporated; September 2026 is not incorporated.\nEligibility appendix is referenced but unavailable.",
            "ILLUSTRATIVE RULE\nEffective from 2025-05-01.\nApproval required before proposal submission.",
            "ILLUSTRATIVE RULE\nEffective from 2026-09-10.\nApproval required before award.",
        ]
        for text in texts:
            sha=hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.assertIn(sha,html)

        deviation_pdf=(
            b"%PDF-1.7\nILLUSTRATIVE DEVIATION PDF\nCD-26-04\n"
            b"Effective September 1, 2026.\n"
            b"Covered acquisitions use the replacement Part 12 text in this memorandum.\n"
        )
        deviation_texts=[
            "ILLUSTRATIVE DEVIATION\nCD-26-04\nEffective September 1, 2026.\nCovered acquisitions use the replacement Part 12 text in this memorandum.",
            "ILLUSTRATIVE CURRENTNESS GUIDE\nCD-26-04 is listed as a current CFTC class deviation.",
            "ILLUSTRATIVE SOLICITATION\nSection I: Offerors shall follow CFTC Class Deviation CD-26-04 for the Part 12 provisions identified in this solicitation.",
        ]
        self.assertIn(hashlib.sha256(deviation_pdf).hexdigest(),html)
        for text in deviation_texts:
            self.assertIn(hashlib.sha256(text.encode("utf-8")).hexdigest(),html)

    def test_existing_real_public_sample_remains_available(self):
        html=(ROOT/"decision-evidence-sample.html").read_text(encoding="utf-8")
        self.assertIn('href="sample.html">See the FAA Pursuit QA example</a>',html)


if __name__=="__main__":
    unittest.main()
