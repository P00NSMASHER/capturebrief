"""Synthetic-only negative tests: three bounded public-original semantic probes."""
from __future__ import annotations
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from capturebrief_core.data_services import REQUIRED_COLUMNS
from capturebrief_core.source_policy import SourcePolicyError
from scripts import audit_fy2027_small_public_originals as m


class FakeResponse:
    def __init__(self,url,content,*,status=200,length=None,encoding="identity"):
        self.url=url
        self.content=content
        self.status=status
        self.headers={
            "Content-Length":str(len(content)) if length is None else str(length),
            "Content-Encoding":encoding,
        }
        self.closed=False
        self.reads=[]
    def geturl(self):return self.url
    def read(self,n):
        self.reads.append(n)
        out=self.content[:n]
        self.content=self.content[n:]
        return out
    def __enter__(self):return self
    def __exit__(self,*args):
        self.closed=True
        return False


def csv_bytes(notice="FAKE-1",*,bom=False):
    s=io.StringIO()
    w=csv.DictWriter(s,fieldnames=sorted(REQUIRED_COLUMNS))
    w.writeheader()
    w.writerow({
        "NoticeId":notice,"Sol#":"SYNTHETIC","PostedDate":"10/19/2026",
        "Active":"No","Type":"Solicitation","AAC Code":"FICTIONAL",
        "Office":"FICTIONAL","Link":"https://sam.gov/opp/fictional/view",
    })
    return (b"\xef\xbb\xbf" if bom else b"")+s.getvalue().encode("ascii")


class EarlyOriginalSafetyTests(unittest.TestCase):
    def test_exact_three_original_year_inventory_is_frozen(self):
        m.validate_frozen_sizes()
        self.assertEqual(m.YEARS,(1999,2000,2001))
        self.assertEqual(sum(m.SIZES.values()),m.MAX_BYTES)
        self.assertEqual(m.MAX_BYTES,6334801)
        for y in m.YEARS:
            self.assertLess(m.SIZES[y],3_000_000)

    def test_each_synthetic_full_source_original_decodes_in_memory(self):
        responses=[]
        data=csv_bytes(bom=True)
        def opener(req,*,timeout):
            response=FakeResponse(req.full_url,data)
            responses.append(response)
            return response
        report=m.observe_all(opener=opener,fake_sizes={y:len(data) for y in m.YEARS})
        self.assertEqual(len(responses),3)
        self.assertEqual(report["source_bytes_observed"],len(data)*3)
        self.assertEqual(report["source_metadata_declared_bytes"],6334801)
        self.assertFalse(report["source_bytes_written_to_disk"])
        self.assertFalse(report["source_catalog_approved"])
        self.assertFalse(report["customer_release_authorized"])
        self.assertEqual([o["rows"] for o in report["observations"]],[1,1,1])
        for obj in responses:
            self.assertTrue(obj.closed)
            self.assertEqual(obj.reads,[len(data)+1])

    def test_anonymized_missing_anchor_and_repeat_collision_counts(self):
        # Fictional public-style rows only; the analysis never discloses
        # individual notice identities, Sol numbers or office names.
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader()
        cases = (
            ("fake-1", "SAME-SOL", "", ""),
            ("fake-2", "SAME-SOL", "AAC1", "OFFICE-A"),
            ("fake-3", "SAME-SOL", "AAC1", "OFFICE-B"),
            ("fake-4", "SAME-SOL", "AAC2", "OFFICE-B"),
            ("fake-5", "", "AAC3", "OFFICE-C"),
        )
        for notice_id, sol, aac, office in cases:
            writer.writerow({
                "NoticeId": notice_id, "Sol#": sol,
                "AAC Code": aac, "Office": office,
                "PostedDate": "10/19/2026",
                "Type": "Solicitation", "Active": "No",
            })
        metrics = m.inspect_original_memory(out.getvalue().encode("ascii"))
        self.assertEqual(metrics["rows"], 5)
        self.assertEqual(metrics["blank_solicitation_rows"], 1)
        self.assertEqual(metrics["blank_aac_rows"], 1)
        self.assertEqual(metrics["blank_office_rows"], 1)
        self.assertEqual(metrics["blank_aac_and_office_rows"], 1)
        self.assertEqual(metrics["repeated_nonblank_solicitation_groups"], 1)
        self.assertEqual(
            metrics["repeated_groups_with_missing_agency_or_office"], 1,
        )
        self.assertEqual(metrics["repeated_groups_with_multiple_known_aacs"], 1)
        self.assertEqual(
            metrics["repeated_groups_with_multiple_offices_inside_known_aac"], 1,
        )
        for notice_id, sol, aac, office in cases:
            if notice_id:
                self.assertNotIn(notice_id, repr(metrics))
            if sol:
                self.assertNotIn(sol, repr(metrics))

    def test_unauthorized_redirect_refused_before_source_body_read(self):
        data=csv_bytes()
        out=[]
        def opener(req,*,timeout):
            x=FakeResponse("https://evil.example/signed?X-Amz-Credential=DO_NOT_LOG",data)
            out.append(x)
            return x
        with self.assertRaises(SourcePolicyError) as context:
            m.observe_public_original(1999,opener=opener,size_override=len(data))
        self.assertNotIn("DO_NOT_LOG",str(context.exception))
        self.assertEqual(out[0].reads,[])
        self.assertTrue(out[0].closed)

    def test_range_ignored_or_changed_declared_bytes_rejected_before_body(self):
        data=csv_bytes()
        for status,length,encoding in (
            (206,len(data),"identity"),
            (200,len(data)+1,"identity"),
            (200,len(data),"gzip"),
        ):
            with self.subTest(status=status,length=length,encoding=encoding):
                observed=[]
                def opener(req,*,timeout):
                    x=FakeResponse(req.full_url,data,status=status,
                                   length=length,encoding=encoding)
                    observed.append(x)
                    return x
                with self.assertRaises(ValueError):
                    m.observe_public_original(2000,opener=opener,
                                              size_override=len(data))
                self.assertEqual(observed[0].reads,[])
                self.assertTrue(observed[0].closed)

    def test_invalid_original_csv_bytes_and_duplicate_headers_block(self):
        raw=csv_bytes()
        for data in (
            raw.replace(b"FAKE-1",b"FAKE-\x81"),
            b"\xef\xbb\xbf"+raw.replace(b"FAKE-1",b"FAKE-\xff"),
            b"NoticeId,NoticeId\nFAKE,FAKE\n",
            b"not-a-valid-sam-original",
            raw.replace(b"FAKE-1",b"FAKE-1,EXTRA"),
        ):
            with self.subTest(case=len(data)),self.assertRaises(
                    (UnicodeDecodeError,ValueError)):
                m.inspect_original_memory(data)

    def test_source_year_or_size_overrides_cannot_escape_bounded_contract(self):
        for bad in (1970,1980,1998,2002,2027,"1999",True):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                m.observe_public_original(bad,opener=lambda req,timeout:None,
                                          size_override=10)
        with self.assertRaises(ValueError):
            m.observe_public_original(1999,size_override=100)
        with self.assertRaises(ValueError):
            m.observe_public_original(1999,opener=lambda req,timeout:None,
                                      size_override=3_000_001)

    def test_malformed_metadata_snapshot_never_approves_source(self):
        original=json.loads(m.METADATA.read_text(encoding="utf-8"))
        for kind in ("year_size","catalog_approval","duplicate_key"):
            forged=json.loads(json.dumps(original))
            if kind=="year_size":forged["year_size_bytes"]["FY1999"]=0
            elif kind=="catalog_approval":forged["independent_human_catalog_approval"]=True
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/"snapshot.json"
                text=json.dumps(forged)
                if kind=="duplicate_key":
                    text=text.replace('"schema":', '"schema":"fake","schema":',1)
                p.write_text(text,encoding="utf-8")
                with patch.object(m,"METADATA",p),self.assertRaises(ValueError):
                    m.validate_frozen_sizes()


    def test_frozen_real_three_source_original_evidence_remains_unapproved(self):
        """Never promote small publisher full-byte reads into catalog approval."""
        path=(m.ROOT/"research"/
              "fy2027_1999_2001_public_original_observations_20261020.json")
        doc=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            doc["schema"],
            "capturebrief-fy2027-bounded-early-original-full-byte-evidence-v1",
        )
        self.assertEqual(
            doc["observation_source"],
            "https://github.com/P00NSMASHER/capturebrief/actions/runs/39366738245",
        )
        self.assertEqual(doc["source_commit"],
                         "0a880d955d88d3fe689a0efc532834268be7ce9c")
        by_year={o["fy"]:o for o in doc["observations"]}
        self.assertEqual(set(by_year),set(m.YEARS))
        self.assertEqual(doc["raw_original_bytes_read_into_memory"],m.MAX_BYTES)
        self.assertEqual(doc["observed_rows_total"],3929)
        self.assertEqual(doc["blank_solicitation_rows_total"],265)
        self.assertEqual(doc["blank_aac_rows_total"],1157)
        self.assertEqual(doc["blank_office_rows_total"],1157)
        for fy, expected in {
            1999:("def8f8be6b002dc7df31e478c68aaeb7d1bec6bed9c4fa030f24f6970c8bca8c",1415),
            2000:("94eb95631fa44a401dfd1fcb4f18e1082ddb22bf45c1e3a69533c2288d37e6f1",1047),
            2001:("5d6aeca22b38784626f9259f6a7973f912c485a1ebe67ea0a83acbc1597b51a5",1467),
        }.items():
            with self.subTest(year=fy):
                row=by_year[fy]
                self.assertEqual(row["sha256"],expected[0])
                self.assertEqual(row["csv_rows"],expected[1])
                self.assertEqual(row["original_bytes"],m.SIZES[fy])
                self.assertTrue(row["required_headers_present"])
                self.assertEqual(row["header_columns"],47)
                self.assertEqual(row["blank_notice_id_rows"],0)
                self.assertEqual(row["duplicate_notice_id_rows"],0)
                self.assertFalse(row["approved"])
                self.assertFalse(row["original_retained"])
        for flag in (
            "original_source_bytes_durably_retained",
            "source_file_upstream_independently_adjudicated",
            "independent_human_catalog_approval",
            "complete_34_year_original_coverage",
            "source_index_updated","offdevice_backup_verified",
            "customer_release_authorized","external_send_authorized",
        ):
            self.assertIs(doc[flag],False,flag)
        self.assertIs(doc["blank_aac_and_office_overlap_unmeasured"],True)

    def test_frozen_unapproved_public_original_agency_ambiguity_observation(self):
        path=(m.ROOT/"research"/
              "fy2027_1999_2001_agency_ambiguity_observation_20261020.json")
        doc=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            doc["schema"],
            "capturebrief-fy2027-unapproved-public-original-agency-ambiguity-v1",
        )
        self.assertEqual(
            doc["observed_from_run"],
            "https://github.com/P00NSMASHER/capturebrief/actions/runs/39367333629",
        )
        years=doc["observations"]
        self.assertEqual([entry["fy"] for entry in years], list(m.YEARS))
        self.assertEqual(doc["original_rows"],3929)
        self.assertEqual(doc["original_bytes_read_in_memory"],6334801)
        self.assertEqual(doc["rows_missing_both_aac_and_office"],1157)
        self.assertEqual(doc["repeated_nonblank_solicitation_groups"],637)
        self.assertEqual(doc["repeated_groups_with_missing_agency_or_office"],193)
        self.assertEqual(doc["repeated_groups_with_multiple_known_aacs"],2)
        self.assertTrue(doc["complete_public_original_bytes_checked_for_these_three_years"])
        self.assertFalse(doc["distinct_group_count_across_years_verified"])
        for entry in years:
            self.assertEqual(entry["bytes"],m.SIZES[entry["fy"]])
            self.assertEqual(entry["blank_aac_rows"],
                             entry["blank_both_aac_and_office_rows"])
            self.assertEqual(entry["blank_office_rows"],
                             entry["blank_both_aac_and_office_rows"])
            self.assertTrue(entry["sha256"] in {
                "def8f8be6b002dc7df31e478c68aaeb7d1bec6bed9c4fa030f24f6970c8bca8c",
                "94eb95631fa44a401dfd1fcb4f18e1082ddb22bf45c1e3a69533c2288d37e6f1",
                "5d6aeca22b38784626f9259f6a7973f912c485a1ebe67ea0a83acbc1597b51a5",
            })
        for blocked in (
            "specific_notice_identity_emitted", "source_originals_retained",
            "independent_publisher_human_review_completed",
            "approved_FY2027_catalog", "all_34_year_archive_sources_covered",
            "private_index_updated", "whole_disk_encryption_verified",
            "offdevice_backup_with_independent_key_verified",
            "customer_release_authorized",
        ):
            self.assertIs(doc[blocked],False,blocked)


if __name__=="__main__":
    unittest.main()
