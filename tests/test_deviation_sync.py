from __future__ import annotations
import copy, unittest

from capturebrief_core.deviation_sync import (
    build_deviation_candidate_proposal,
    build_pinned_manifest_request,
    deviation_candidate_work_item,
    fetch_pinned_deviation_manifest,
)
from capturebrief_core.rule_registry import digest

CATALOG={
    "schema_version":"1.0",
    "sources":[{
        "source_id":"acqagent-rfo-deviations",
        "namespace":"CLASS_DEVIATION",
        "repository":"acqagent/rfo-deviations",
        "repository_url":"https://github.com/acqagent/rfo-deviations",
        "revision":"c"*40,
        "snapshot_label":"test",
        "path_pattern":"manifest.csv + source PDFs",
    }],
}
CSV=(
    "on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\n"
    "a.pdf,0123456789abcdef,A.pdf,CFTC,12,0,https://www.acquisition.gov/a.pdf,100\n"
    "a.pdf,0123456789abcdef,A.pdf,CFTC,13,0,https://www.acquisition.gov/a.pdf,100\n"
    "b.pdf,fedcba9876543210,B.pdf,CFTC,12,0,https://www.acquisition.gov/b.pdf,200\n"
    "c.pdf,aaaaaaaaaaaaaaaa,C.pdf,DHS,12,0,https://www.acquisition.gov/c.pdf,300\n"
    "u.pdf,bbbbbbbbbbbbbbbb,U.pdf,GSA,-1,0,https://www.acquisition.gov/u.pdf,400\n"
)

class DeviationSyncTests(unittest.TestCase):
    def fetcher(self,url,max_bytes):
        self.assertIn("raw.githubusercontent.com/acqagent/rfo-deviations/",""+url)
        return CSV.encode(),url

    def test_request_is_exact_revision_no_caller_url(self):
        r=build_pinned_manifest_request(CATALOG)
        self.assertIn("/"+"c"*40+"/manifest.csv",r["raw_url"])
        self.assertFalse(r["mutable_ref_used"])
        self.assertFalse(r["caller_url_used"])

    def test_fetch_and_parse_are_receipted(self):
        manifest,receipt=fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher)
        self.assertEqual(manifest["row_count"],5)
        self.assertEqual(receipt["row_count"],5)
        self.assertEqual(receipt["manifest_sha256"],digest(CSV.encode()))
        self.assertFalse(receipt["applicability_authoritative"])

    def test_redirect_is_rejected(self):
        def bad(url,max_bytes):
            return CSV.encode(),"https://raw.githubusercontent.com/acqagent/rfo-deviations/"+"d"*40+"/manifest.csv"
        with self.assertRaises(ValueError):
            fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=bad)

    def test_candidate_proposal_filters_agency_parts_and_deduplicates_pdf(self):
        manifest,receipt=fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher)
        p=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[12,13],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        self.assertEqual(p["candidate_count"],2)
        a=next(x for x in p["candidates"] if x["source_url"].endswith("/a.pdf"))
        self.assertEqual(a["matched_parts"],[12,13])
        self.assertEqual(a["applicability"],"UNRESOLVED")
        self.assertFalse(p["can_auto_apply"])

    def test_candidate_proposal_does_not_treat_corpus_absence_as_no_deviation(self):
        manifest,receipt=fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher)
        p=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[53],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        self.assertEqual(p["candidate_count"],0)
        self.assertTrue(p["review_required"])

    def test_tampered_receipt_is_rejected(self):
        manifest,receipt=fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher)
        receipt=copy.deepcopy(receipt); receipt["row_count"]=999
        with self.assertRaises(ValueError):
            build_deviation_candidate_proposal(
                manifest,receipt,agency="CFTC",part_numbers=[12],
                proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
            )

    def test_work_item_is_human_only(self):
        manifest,receipt=fetch_pinned_deviation_manifest(CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher)
        proposal=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[12],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        case={"packet":{"deviation_candidate_proposal":proposal}}
        task=deviation_candidate_work_item(case)
        self.assertEqual(task["actor"],"HUMAN_REVIEW")
        self.assertFalse(task["can_auto_execute"])

if __name__=="__main__":
    unittest.main()
