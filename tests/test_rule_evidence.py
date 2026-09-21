from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.rule_candidates import (
    attach_rule_candidate_proposal,
    attach_rule_candidate_review,
)
from capturebrief_core.rule_evidence import (
    prepare_rule_evidence,
    prepared_rule_evidence,
    rule_evidence_preparation_is_current,
    rule_evidence_work_item,
)
from capturebrief_core.rule_registry import (
    add_rule_version,
    digest,
    parse_gsa_dita,
)
from capturebrief_core.workqueue import build_work_queue

DITA = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="FAR_52_204_21">
<title><ph props="autonumber">52.204-21</ph> Basic Safeguarding.</title>
<conbody outputclass="clause">
<p id="heading" outputclass="Ctr_SmCaps">Basic Safeguarding (Nov 2021)</p>
<p id="a">Synthetic safeguarding requirement.</p>
<p id="b">Synthetic second paragraph.</p>
</conbody></concept></dita>'''


def base_case():
    return {
        "case_schema_version": "0.2",
        "case_id": "CB-PREP",
        "family_id": "FAM-PREP",
        "current_posture": "HOLD",
        "decision_trace_required": True,
        "packet": {
            "family_status": "UNKNOWN",
            "history_action_ids": [],
            "history_receipts": [],
            "manifest_receipts": [],
            "references": [],
        },
        "current_action_receipts": [],
        "sources": [{
            "source_id": "sol",
            "title": "Solicitation",
            "url": "https://sam.gov/opp/demo/view",
            "authority": "CONTROLLING_CURRENT",
            "artifact_state": "PUBLIC",
            "observed_at": "2026-09-21T16:00:00Z",
            "content_sha256": digest(b"synthetic-solicitation"),
        }],
        "assumptions": [{
            "assumption_id": "A1",
            "text": "The safeguarding requirement is understood.",
            "evidence_state": "UNPROVEN",
            "decision_class": "VERIFY_NOW",
            "finding": "Applicability still requires review.",
            "owner": "Reviewer",
            "next_action": "Review applicability.",
            "source_ids": ["sol"],
        }],
    }


class RuleEvidencePrepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "rules.sqlite"
        self.record = parse_gsa_dita(
            DITA,
            namespace="FAR",
            agency="FAR Council",
            source_repository="GSA/GSA-Acquisition-FAR",
            source_revision="a" * 40,
            source_path="dita/52.204-21.dita",
            source_url="https://github.com/GSA/GSA-Acquisition-FAR/blob/" + "a" * 40 + "/dita/52.204-21.dita",
            observed_at="2026-09-21T15:00:00Z",
        )
        add_rule_version(self.registry, self.record)

    def tearDown(self):
        self.temp.cleanup()

    def reviewed_case(self, *, decision="TRACK_VERSION"):
        case, _ = attach_rule_candidate_proposal(
            base_case(),
            self.registry,
            [{"source_id": "sol", "text": "The solicitation lists FAR 52.204-21."}],
            captured_by="Reviewer",
            observed_at="2026-09-21T16:30:00Z",
        )
        match = case["packet"]["rule_candidate_proposal"]["matches"][0]
        row = {
            "occurrence_id": match["occurrence_id"],
            "decision": decision,
            "reason": "Carry the cited edition forward for exact passage review.",
        }
        if decision == "TRACK_VERSION":
            row["selected_rule_source_id"] = match["candidate_versions"][0]["rule_source_id"]
        case, _ = attach_rule_candidate_review(case, {
            "reviewer": "Human reviewer",
            "reviewed_at": "2026-09-21T16:45:00Z",
            "decisions": [row],
        })
        return case

    def prep(self, case, locator="a"):
        occurrence = case["packet"]["rule_candidate_review"]["decisions"][0]["occurrence_id"]
        return {
            "prepared_by": "Human reviewer",
            "prepared_at": "2026-09-21T17:00:00Z",
            "selections": [{
                "occurrence_id": occurrence,
                "paragraph_locator": locator,
            }],
        }

    def test_selected_version_requires_exact_passage_work(self):
        case = self.reviewed_case()
        task = rule_evidence_work_item(case)
        self.assertIsNotNone(task)
        self.assertEqual(task["priority"], "P0")
        self.assertEqual(task["actor"], "HUMAN_REVIEW")
        self.assertFalse(task["can_auto_execute"])
        self.assertFalse(task["metadata"]["can_auto_apply"])
        self.assertFalse(task["metadata"]["can_auto_bind_assumption"])

    def test_prepare_builds_source_snapshot_passage_and_rule_version(self):
        case = self.reviewed_case()
        updated, transition = prepare_rule_evidence(
            case, self.registry, self.prep(case)
        )
        self.assertEqual(transition["status"], "RULE_EVIDENCE_PREPARED")
        self.assertTrue(rule_evidence_preparation_is_current(updated))
        items = prepared_rule_evidence(updated)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["paragraph_locator"], "a")
        self.assertEqual(
            item["text_passage"]["quote"],
            "[a] Synthetic safeguarding requirement.",
        )
        self.assertEqual(
            item["rule_version"]["revision_ref"],
            self.record["rule_source_id"],
        )
        self.assertEqual(item["rule_version"]["edition"], "Nov 2021")
        self.assertEqual(item["applicability"], "UNRESOLVED")
        self.assertFalse(item["applicability_authoritative"])
        self.assertIsNone(item["bound_assumption_id"])
        self.assertFalse(item["can_auto_bind_assumption"])
        self.assertFalse(item["can_auto_apply"])
        self.assertIn(item["source"], updated["sources"])
        self.assertIsNone(rule_evidence_work_item(updated))

    def test_preparation_does_not_create_or_bind_decision_trace(self):
        case = self.reviewed_case()
        updated, _ = prepare_rule_evidence(case, self.registry, self.prep(case))
        self.assertNotIn("decision_trace", updated)
        item = prepared_rule_evidence(updated)[0]
        self.assertIsNone(item["bound_assumption_id"])
        queue = build_work_queue(updated)
        self.assertTrue(any(t["task_key"].startswith("trace:") for t in queue["tasks"]))
        self.assertFalse(any(t["task_key"] == "rules:prepare-evidence" for t in queue["tasks"]))

    def test_wrong_locator_rejected(self):
        case = self.reviewed_case()
        with self.assertRaises(ValueError):
            prepare_rule_evidence(case, self.registry, self.prep(case, "missing"))

    def test_missing_registry_record_rejected(self):
        case = self.reviewed_case()
        empty = Path(self.temp.name) / "empty.sqlite"
        with self.assertRaises(ValueError):
            prepare_rule_evidence(case, empty, self.prep(case))

    def test_unresolved_or_ignored_review_needs_no_passage_preparation(self):
        for decision in ("UNRESOLVED", "IGNORE"):
            case = self.reviewed_case(decision=decision)
            self.assertIsNone(rule_evidence_work_item(case))
            with self.assertRaises(ValueError):
                prepare_rule_evidence(case, self.registry, {
                    "prepared_by": "Reviewer",
                    "prepared_at": "2026-09-21T17:00:00Z",
                    "selections": [],
                })

    def test_tampered_preparation_reopens_task(self):
        case = self.reviewed_case()
        updated, _ = prepare_rule_evidence(case, self.registry, self.prep(case))
        updated["packet"]["rule_evidence_preparation"]["items"][0]["paragraph_locator"] = "b"
        self.assertFalse(rule_evidence_preparation_is_current(updated))
        self.assertIsNotNone(rule_evidence_work_item(updated))
        self.assertEqual(prepared_rule_evidence(updated), [])

    def test_source_id_collision_rejected(self):
        case = self.reviewed_case()
        prepared, _ = prepare_rule_evidence(case, self.registry, self.prep(case))
        source = prepared_rule_evidence(prepared)[0]["source"]
        collision_case = self.reviewed_case()
        bad = copy.deepcopy(source)
        bad["title"] = "Conflicting title"
        collision_case["sources"].append(bad)
        with self.assertRaises(ValueError):
            prepare_rule_evidence(
                collision_case, self.registry, self.prep(collision_case)
            )

    def test_preparation_is_bound_to_current_rule_review(self):
        case = self.reviewed_case()
        updated, _ = prepare_rule_evidence(case, self.registry, self.prep(case))
        updated["packet"]["rule_candidate_review"]["reviewer"] = "Changed reviewer"
        self.assertFalse(rule_evidence_preparation_is_current(updated))

    def test_requires_timezone_aware_prepared_at(self):
        case = self.reviewed_case()
        prep = self.prep(case)
        prep["prepared_at"] = "2026-09-21T17:00:00"
        with self.assertRaises(ValueError):
            prepare_rule_evidence(case, self.registry, prep)


if __name__ == "__main__":
    unittest.main()
