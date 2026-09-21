from __future__ import annotations
import copy, tempfile, unittest
from pathlib import Path
from capturebrief_core.rule_registry import add_rule_version, diff_rule_versions, filter_deviation_sources, list_rule_versions, load_source_catalog, parse_deviation_manifest, parse_gsa_dita, to_trace_source_snapshot, validate_rule_source

DITA='''<?xml version="1.0" encoding="UTF-8"?>
<concept id="FAR_52_204_21"><title><ph props="autonumber">52.204-21</ph> Basic Safeguarding</title><conbody><p id="a">Contractors shall use safeguards.</p><p id="b">This is a synthetic fixture.</p></conbody></concept>'''
KW=dict(namespace="FAR",agency="FAR Council",edition="FAC TEST",source_repository="GSA/GSA-Acquisition-FAR",source_revision="a"*40,source_path="dita/52.204-21.dita",source_url="https://github.com/GSA/GSA-Acquisition-FAR/blob/"+"a"*40+"/dita/52.204-21.dita",observed_at="2026-09-21T16:00:00Z")
OFFICIAL_SHAPED='''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="FAR_52_204_21">
<title><ph props="autonumber">52.204-21</ph> Basic Safeguarding of Covered Contractor Information Systems.</title>
<conbody outputclass="clause">
<p id="prescription">As prescribed in 4.1903, insert the following clause:</p>
<p id="heading" outputclass="Ctr_SmCaps">Basic Safeguarding of Covered Contractor Information Systems (Nov 2021)</p>
<p id="a"><ph props="autonumber">(a)</ph> Contractors shall use safeguards.</p>
</conbody></concept></dita>'''

class RuleRegistryTests(unittest.TestCase):
    def test_parse_dita(self):
        r=parse_gsa_dita(DITA,**KW); self.assertEqual(r["citation"],"52.204-21"); self.assertEqual(r["rule_key"],"FAR:FAR Council:52.204-21"); self.assertEqual(len(r["paragraphs"]),2); self.assertEqual(validate_rule_source(r),[])
    def test_rejects_entities(self):
        with self.assertRaises(ValueError): parse_gsa_dita('<!DOCTYPE x [<!ENTITY y "z">]><concept><title><ph props="autonumber">1.1</ph>x</title><conbody><p>&y;</p></conbody></concept>',**{**KW,"source_path":"dita/1.1.dita"})

    def test_accepts_exact_gsa_external_dita_doctype(self):
        kwargs={k:v for k,v in KW.items() if k!="edition"}
        row=parse_gsa_dita(OFFICIAL_SHAPED,**kwargs)
        self.assertEqual(row["edition"],"Nov 2021")
        self.assertEqual(row["edition_basis"],"EMBEDDED_RULE_TEXT")
        self.assertEqual(row["embedded_edition_locator"],"heading")
        self.assertTrue(row["standard_doctype_stripped"])
        self.assertIsNone(row["source_snapshot_label"])
        self.assertEqual(validate_rule_source(row),[])

    def test_embedded_rule_edition_outranks_source_snapshot_label(self):
        row=parse_gsa_dita(OFFICIAL_SHAPED,**{**KW,"edition":"FAC 2026-01 snapshot"})
        self.assertEqual(row["edition"],"Nov 2021")
        self.assertEqual(row["source_snapshot_label"],"FAC 2026-01 snapshot")
        self.assertEqual(row["edition_basis"],"EMBEDDED_RULE_TEXT")

    def test_rejects_arbitrary_external_doctype(self):
        bad=OFFICIAL_SHAPED.replace(
            'PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd"',
            'SYSTEM "https://evil.invalid/evil.dtd"',
        )
        kwargs={k:v for k,v in KW.items() if k!="edition"}
        with self.assertRaises(ValueError):
            parse_gsa_dita(bad,**kwargs)
    def test_commit_is_not_effective_date(self):
        r=parse_gsa_dita(DITA,**KW); self.assertIsNone(r["effective_from"]); self.assertEqual(r["effective_date_authority"],"UNKNOWN"); self.assertFalse(r["applicability_authoritative"])
    def test_registry_versions_are_append_only(self):
        first=parse_gsa_dita(DITA,**KW); second=parse_gsa_dita(DITA.replace("shall use safeguards","shall use revised safeguards"),**{**KW,"edition":"FAC NEXT","source_revision":"b"*40,"source_url":"https://github.com/GSA/GSA-Acquisition-FAR/blob/"+"b"*40+"/dita/52.204-21.dita","observed_at":"2026-09-22T16:00:00Z"})
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/"rules.sqlite"; self.assertEqual(add_rule_version(db,first),"INSERTED"); self.assertEqual(add_rule_version(db,first),"EXISTS"); self.assertEqual(add_rule_version(db,second),"INSERTED"); rows=list_rule_versions(db,rule_key=first["rule_key"]); self.assertEqual([x["edition"] for x in rows],["FAC TEST","FAC NEXT"])
    def test_diff_requires_review_not_auto_applicability(self):
        first=parse_gsa_dita(DITA,**KW); second=parse_gsa_dita(DITA.replace("shall use safeguards","shall use revised safeguards"),**{**KW,"edition":"FAC NEXT","source_revision":"b"*40,"source_url":"https://github.com/GSA/GSA-Acquisition-FAR/blob/"+"b"*40+"/dita/52.204-21.dita","observed_at":"2026-09-22T16:00:00Z"}); diff=diff_rule_versions(first,second); self.assertTrue(diff["changed"]); self.assertTrue(diff["review_required"]); self.assertFalse(diff["automatic_applicability_change"])
    def test_deviation_manifest(self):
        text='on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\na.pdf,0123456789abcdef,A.pdf,DOD,12,1,https://www.acquisition.gov/a.pdf,100\nb.pdf,fedcba9876543210,B.pdf,CFTC,12,0,https://www.acquisition.gov/b.pdf,200\n'; m=parse_deviation_manifest(text,source_repository="acqagent/rfo-deviations",source_revision="c"*40,observed_at="2026-09-21T16:00:00Z"); self.assertEqual(m["row_count"],2); self.assertEqual(len(filter_deviation_sources(m,agency="DOD",part_number=12)),1); self.assertFalse(m["rows"][0]["applicability_authoritative"])
    def test_deviation_manifest_preserves_unparsed_and_zero_part_sentinels(self):
        text='on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\n' \
             'a.pdf,0123456789abcdef,A.pdf,GSA,-1,0,https://www.acquisition.gov/a.pdf,100\n' \
             'b.pdf,fedcba9876543210,B.pdf,DHS,0,0,https://www.acquisition.gov/b.pdf,200\n'
        m=parse_deviation_manifest(text,source_repository="acqagent/rfo-deviations",source_revision="d"*40,observed_at="2026-09-21T16:00:00Z")
        self.assertEqual([x["part_number"] for x in m["rows"]],[-1,0])
        self.assertEqual(filter_deviation_sources(m,agency="GSA",part_number=-1)[0]["original_filename"],"A.pdf")

    def test_trace_bridge(self):
        r=parse_gsa_dita(DITA,**KW); source,snap=to_trace_source_snapshot(r,source_id="rule-1",reviewer="Analyst"); self.assertEqual(source["content_sha256"],r["source_sha256"]); self.assertEqual(snap["version_label"],"FAC TEST"); self.assertIn("52.204-21",snap["text"])
    def test_catalog(self):
        catalog=load_source_catalog(Path(__file__).parents[1]/"RULE-SOURCE-CATALOG.json"); self.assertGreaterEqual(len(catalog["sources"]),4); self.assertTrue(all(len(x["revision"])==40 for x in catalog["sources"]))
    def test_tampered_record_fails(self):
        r=parse_gsa_dita(DITA,**KW); bad=copy.deepcopy(r); bad["text"]+="x"; self.assertIn("normalized_text_sha256",validate_rule_source(bad))

if __name__=="__main__": unittest.main()
