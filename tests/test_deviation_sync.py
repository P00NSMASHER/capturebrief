from __future__ import annotations
import copy, unittest

from capturebrief_core.deviation_sync import (
    attach_deviation_artifact_receipt,
    build_deviation_artifact_request,
    build_deviation_candidate_proposal,
    build_pinned_manifest_request,
    capture_deviation_artifact,
    current_deviation_artifact_receipts,
    deviation_artifact_work_items,
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
A_URL="https://www.acquisition.gov/a.pdf"
B_URL="https://www.acquisition.gov/b.pdf"
C_URL="https://www.acquisition.gov/c.pdf"
U_URL="https://www.acquisition.gov/u.pdf"
PDF=b"%PDF-1.7\n"+b"x"*91
CSV=(
    "on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\n"
    f"a.pdf,{digest(A_URL)[:16]},A.pdf,CFTC,12,0,{A_URL},{len(PDF)}\n"
    f"a.pdf,{digest(A_URL)[:16]},A.pdf,CFTC,13,0,{A_URL},{len(PDF)}\n"
    f"b.pdf,{digest(B_URL)[:16]},B.pdf,CFTC,12,0,{B_URL},200\n"
    f"c.pdf,{digest(C_URL)[:16]},C.pdf,DHS,12,0,{C_URL},300\n"
    f"u.pdf,{digest(U_URL)[:16]},U.pdf,GSA,-1,0,{U_URL},400\n"
)

class DeviationSyncTests(unittest.TestCase):
    def fetcher(self,url,max_bytes):
        self.assertIn("raw.githubusercontent.com/acqagent/rfo-deviations/",""+url)
        return CSV.encode(),url

    def pdf_fetcher(self,url,max_bytes):
        return PDF,url

    def proposal_case(self,parts=None):
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher
        )
        proposal=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=parts or [12,13],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        return {"packet":{"deviation_candidate_proposal":proposal}}

    def test_request_is_exact_revision_no_caller_url(self):
        r=build_pinned_manifest_request(CATALOG)
        self.assertIn("/"+"c"*40+"/manifest.csv",r["raw_url"])
        self.assertFalse(r["mutable_ref_used"])
        self.assertFalse(r["caller_url_used"])

    def test_fetch_and_parse_are_receipted(self):
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher
        )
        self.assertEqual(manifest["row_count"],5)
        self.assertEqual(receipt["row_count"],5)
        self.assertEqual(receipt["manifest_sha256"],digest(CSV.encode()))
        self.assertFalse(receipt["applicability_authoritative"])

    def test_redirect_is_rejected(self):
        def bad(url,max_bytes):
            return CSV.encode(),"https://raw.githubusercontent.com/acqagent/rfo-deviations/"+"d"*40+"/manifest.csv"
        with self.assertRaises(ValueError):
            fetch_pinned_deviation_manifest(
                CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=bad
            )

    def test_candidate_proposal_filters_agency_parts_and_deduplicates_pdf(self):
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher
        )
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
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher
        )
        p=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[53],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        self.assertEqual(p["candidate_count"],0)
        self.assertTrue(p["review_required"])

    def test_tampered_receipt_is_rejected(self):
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.fetcher
        )
        receipt=copy.deepcopy(receipt); receipt["row_count"]=999
        with self.assertRaises(ValueError):
            build_deviation_candidate_proposal(
                manifest,receipt,agency="CFTC",part_numbers=[12],
                proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
            )

    def test_artifact_request_is_bound_to_current_proposal_and_url_hash(self):
        case=self.proposal_case()
        ident=next(x["deviation_source_id"] for x in case["packet"]["deviation_candidate_proposal"]["candidates"] if x["source_url"]==A_URL)
        req=build_deviation_artifact_request(case,ident)
        self.assertEqual(req["source_url"],A_URL)
        self.assertEqual(req["url_hash"],digest(A_URL)[:16])
        self.assertFalse(req["caller_url_used"])

    def test_capture_hashes_pdf_without_claiming_index_byte_identity(self):
        case=self.proposal_case()
        ident=next(x["deviation_source_id"] for x in case["packet"]["deviation_candidate_proposal"]["candidates"] if x["source_url"]==A_URL)
        receipt,data=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
        )
        self.assertEqual(data,PDF)
        self.assertEqual(receipt["pdf_sha256"],digest(PDF))
        self.assertTrue(receipt["declared_size_matches_observed"])
        self.assertFalse(receipt["index_byte_identity_proven"])
        self.assertEqual(receipt["currentness"],"UNRESOLVED")
        self.assertEqual(receipt["applicability"],"UNRESOLVED")

    def test_declared_size_mismatch_is_preserved_not_promoted(self):
        case=self.proposal_case([12])
        ident=next(x["deviation_source_id"] for x in case["packet"]["deviation_candidate_proposal"]["candidates"] if x["source_url"]==B_URL)
        receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
        )
        self.assertFalse(receipt["declared_size_matches_observed"])
        self.assertFalse(receipt["index_byte_identity_proven"])

    def test_pdf_redirect_and_non_pdf_are_rejected(self):
        case=self.proposal_case()
        ident=next(x["deviation_source_id"] for x in case["packet"]["deviation_candidate_proposal"]["candidates"] if x["source_url"]==A_URL)
        with self.assertRaises(ValueError):
            capture_deviation_artifact(
                case,ident,observed_at="2026-09-21T18:10:00Z",
                fetcher=lambda url,max_bytes:(PDF,"https://www.acquisition.gov/other.pdf"),
            )
        with self.assertRaises(ValueError):
            capture_deviation_artifact(
                case,ident,observed_at="2026-09-21T18:10:00Z",
                fetcher=lambda url,max_bytes:(b"<html>not pdf</html>",url),
            )

    def test_receipt_attachment_is_append_only_and_idempotent(self):
        case=self.proposal_case()
        ident=next(x["deviation_source_id"] for x in case["packet"]["deviation_candidate_proposal"]["candidates"] if x["source_url"]==A_URL)
        receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
        )
        once=attach_deviation_artifact_receipt(case,receipt)
        twice=attach_deviation_artifact_receipt(once,receipt)
        self.assertEqual(len(twice["packet"]["deviation_artifact_receipts"]),1)
        self.assertIn(ident,current_deviation_artifact_receipts(twice))

    def test_artifact_capture_is_p0_automatic_then_human_review_remains(self):
        case=self.proposal_case()
        tasks=deviation_artifact_work_items(case)
        self.assertEqual(len(tasks),2)
        self.assertTrue(all(x["priority"]=="P0" for x in tasks))
        self.assertTrue(all(x["can_auto_execute"] for x in tasks))
        human=deviation_candidate_work_item(case)
        self.assertEqual(human["priority"],"P1")
        self.assertEqual(human["actor"],"HUMAN_REVIEW")

        # Capture both candidate PDFs.
        updated=case
        for candidate in case["packet"]["deviation_candidate_proposal"]["candidates"]:
            receipt,_=capture_deviation_artifact(
                updated,candidate["deviation_source_id"],
                observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
            )
            updated=attach_deviation_artifact_receipt(updated,receipt)
        self.assertEqual(deviation_artifact_work_items(updated),[])
        human=deviation_candidate_work_item(updated)
        self.assertEqual(human["priority"],"P0")
        self.assertEqual(human["metadata"]["captured_candidate_count"],2)

    def test_zero_candidate_review_remains_p0_human(self):
        case=self.proposal_case([53])
        task=deviation_candidate_work_item(case)
        self.assertEqual(task["priority"],"P0")
        self.assertEqual(task["actor"],"HUMAN_REVIEW")
        self.assertFalse(task["can_auto_execute"])

if __name__=="__main__":
    unittest.main()
