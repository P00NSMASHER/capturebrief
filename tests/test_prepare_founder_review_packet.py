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


    def test_review_draft_refuses_private_output_inside_unrelated_git_checkout(self):
        """A different Git checkout is not an approved private evidence room."""
        import io
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest.mock import patch
        from scripts import prepare_founder_review_packet as module
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, proof = base / "fictional.pdf", base / "fictional-proof.json"
            source.write_bytes(b"FICTIONAL_NO_SOURCE_RECORD")
            proof.write_text("{}", encoding="utf-8")
            foreign_checkout = base / "unrelated-git-repository"
            foreign_checkout.mkdir(mode=0o700)
            (foreign_checkout / ".git").mkdir()
            output = foreign_checkout / "private-review"
            fake_packet = {
                "status": "FIRST_PARTY_CONFLICT_REVIEW_DRAFT_NOT_DELIVERABLE",
                "findings": [],
            }
            with patch.object(module, "prepare",
                              return_value=(fake_packet, "# Fictional review only\\n")):
                captured = io.StringIO()
                with redirect_stdout(captured):
                    result = module.main([
                        "--source-pdf", str(source),
                        "--source-proof", str(proof),
                        "--output-dir", str(output),
                    ])
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(captured.getvalue())["status"], "REVIEW_DRAFT_BLOCKED")
            self.assertFalse(output.exists(), "No private packet may be written into another repository")

    def test_review_draft_uses_existing_private_owner_workspace_not_shared_parent(self):
        """Reject publicly traversable workspace parents; preserve a safe no-send path."""
        import io
        import os
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest.mock import patch
        from scripts import prepare_founder_review_packet as module
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source, proof = base / "fictional.pdf", base / "fictional-proof.json"
            source.write_bytes(b"FICTIONAL_NO_SOURCE_RECORD")
            proof.write_text("{}", encoding="utf-8")
            owner_workspace = base / "operator-only"
            owner_workspace.mkdir(mode=0o700)
            shared_workspace = base / "shared-workspace"
            shared_workspace.mkdir(mode=0o755)
            fake_packet = {
                "status": "FIRST_PARTY_CONFLICT_REVIEW_DRAFT_NOT_DELIVERABLE",
                "findings": [],
            }
            with patch.object(module, "prepare",
                              return_value=(fake_packet, "# Fictional review only\\n")):
                if os.name != "nt":
                    unsafe = shared_workspace / "review"
                    captured = io.StringIO()
                    with redirect_stdout(captured):
                        result = module.main([
                            "--source-pdf", str(source),
                            "--source-proof", str(proof),
                            "--output-dir", str(unsafe),
                        ])
                    self.assertEqual(result, 2)
                    self.assertFalse(unsafe.exists())
                safe = owner_workspace / "review"
                captured = io.StringIO()
                with redirect_stdout(captured):
                    result = module.main([
                        "--source-pdf", str(source),
                        "--source-proof", str(proof),
                        "--output-dir", str(safe),
                    ])
            self.assertEqual(result, 0, captured.getvalue())
            self.assertEqual(json.loads(captured.getvalue())["status"], fake_packet["status"])
            self.assertTrue((safe / "review-packet.json").is_file())
            self.assertTrue((safe / "review-preview.md").is_file())
            if os.name != "nt":
                self.assertEqual(safe.stat().st_mode & 0o077, 0)
                self.assertEqual((safe / "review-packet.json").stat().st_mode & 0o077, 0)
            self.assertFalse(json.loads((safe / "review-packet.json").read_text()).get(
                "customer_release_authorized", False))


if __name__ == "__main__":
    unittest.main()
