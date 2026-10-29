"""No-send and exact-page acceptance for the supervised original-source draft."""
import copy
import json
import unittest

from scripts.prepare_founder_review_packet import source_findings, prepare, CHECKS, SOURCE_SHA


def fake_pages():
    pages = ["Unrelated filler."] * 35
    for code, severity, clauses, detail in CHECKS:
        for page, pattern in clauses:
            # Explicit synthetic text corresponding to the published findings.
            sample = {
                "DEADLINE_CONFLICT": ["11/09/2026 1000 ET",
                                      "November 5, 2026 at 12:00 PM"],
                "PRICE_HOLD_CONFLICT": ["60 calendar days",
                                        "minimum of 90 calendar days"],
                "OFF_TOPIC_CONTENT": ["nationwide court reporting services"],
                "QUESTIONS_CUTOFF": ["October 29, 2026 at 12:00 PM"],
            }[code]
            index = list(clauses).index((page,pattern))
            pages[page-1] += "\n" + sample[index]
    return pages


class SourceReviewTests(unittest.TestCase):
    def test_four_real_source_page_claims_are_individually_bound(self):
        rows = source_findings(fake_pages())
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["original_pdf_pages"], [1,3])
        self.assertEqual(rows[1]["original_pdf_pages"], [27,33])
        self.assertEqual(rows[2]["original_pdf_pages"], [3])
        self.assertEqual(rows[3]["original_pdf_pages"], [34])
        for row in rows:
            self.assertIs(row["human_review_verified"], False)

    def test_tampered_page_or_missing_page_fails_closed(self):
        origin = fake_pages()
        with self.assertRaises(ValueError):
            source_findings(origin[:-1])
        for page in [1,3,27,33,34]:
            changed = copy.deepcopy(origin)
            changed[page-1] = "Document has no evidence"
            with self.subTest(page=page), self.assertRaises(ValueError):
                source_findings(changed)

    def test_missing_or_different_original_never_generates_approved_report(self):
        with self.assertRaises(ValueError):
            prepare(b"%PDF-FAKE", {"customer_release_authorized":True})
        self.assertEqual(len(SOURCE_SHA),64)

    def test_internal_review_outputs_never_claim_delivery_authority(self):
        import inspect
        from scripts import prepare_founder_review_packet as code
        src = inspect.getsource(code.prepare)
        self.assertIn('"customer_release_authorized": False', src)
        self.assertIn('"reviewer_approved": False', src)
        self.assertIn('"payment_authorized": False', src)
        self.assertIn('"watch_included": False', src)
        self.assertIn('"automatic_upgrade_authorized": False', src)


if __name__ == "__main__":
    unittest.main()
