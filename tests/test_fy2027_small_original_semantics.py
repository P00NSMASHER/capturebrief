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

    def test_unauthorized_redirect_refused_before_source_body_read(self):
        data=csv_bytes()
        out=[]
        def opener(req,*,timeout):
            x=FakeResponse("https://evil.example/signed?X-Amz-Credential=DO_NOT_LOG",data)
            out.append(x)
            return x
        with self.assertRaises(ValueError) as context:
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


if __name__=="__main__":
    unittest.main()
