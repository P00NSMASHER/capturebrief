from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.decision_trace import (
    digest,
    evaluate_decision_trace,
    freeze_text_snapshot,
    passage,
)
from capturebrief_core.rule_applicability import (
    review_rule_applicability,
    rule_applicability_review_is_current,
    rule_applicability_work_item,
)
from capturebrief_core.rule_candidates import (
    attach_rule_candidate_proposal,
    attach_rule_candidate_review,
)
from capturebrief_core.rule_evidence import prepare_rule_evidence, prepared_rule_evidence
from capturebrief_core.rule_registry import add_rule_version, parse_gsa_dita
from capturebrief_core.workqueue import build_work_queue

NOW = datetime(2026, 9, 21, 18, tzinfo=timezone.utc)
SOL_TEXT = """ILLUSTRATIVE SOLICITATION
FAR 52.204-21 (Nov 2021) is incorporated into this solicitation.
Offerors must describe their safeguarding approach.
"""
DITA = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="FAR_52_204_21">
<title><ph props="autonumber">52.204-21</ph> Basic Safeguarding.</title>
<conbody outputclass="clause">
<p id="heading" outputclass="Ctr_SmCaps">Basic Safeguarding (Nov 2021)</p>
<p id="a">Contractors shall apply the required safeguards.</p>
</conbody></concept></dita>"""


def base_case():
    return {
        "case_schema_version": "0.2",
        "case_id": "CB-APP",
        "family_id": "FAM-APP",
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
            "url": "https://sam.gov/opp/illustrative/view",
            "authority": "CONTROLLING_CURRENT",
            "artifact_state": "PUBLIC",
            "observed_at": "2026-09-21T16:00:00Z",
            "content_sha256": digest(SOL_TEXT),
        }],
        "assumptions": [{
            "assumption_id": "A1",
            "text": "We satisfy the safeguarding requirement.",
            "evidence_state": "UNPROVEN",
            "decision_class": "VERIFY_NOW",
            "finding": "The cited safeguarding rule is incorporated; compliance evidence is still needed.",
            "owner": "Capture lead",
            "next_action": "Provide safeguarding compliance evidence.",
            "source_ids": ["sol"],
        }],
    }


class RuleApplicabilityTests(unittest.TestCase):
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

    def prepared_case(self, *, with_trace=True):
        case, _ = attach_rule_candidate_proposal(
            base_case(),
            self.registry,
            [{"source_id": "sol", "text": SOL_TEXT}],
            captured_by="Reviewer",
            observed_at="2026-09-21T16:30:00Z",
        )
        match = case["packet"]["rule_candidate_proposal"]["matches"][0]
        case, _ = attach_rule_candidate_review(case, {
            "reviewer": "Rule version reviewer",
            "reviewed_at": "2026-09-21T16:45:00Z",
            "decisions": [{
                "occurrence_id": match["occurrence_id"],
                "decision": "TRACK_VERSION",
                "selected_rule_source_id": match["candidate_versions"][0]["rule_source_id"],
                "reason": "The solicitation names this FAR citation; carry the pinned edition forward.",
            }],
        })
        occurrence = case["packet"]["rule_candidate_review"]["decisions"][0]["occurrence_id"]
        case, _ = prepare_rule_evidence(case, self.registry, {
            "prepared_by": "Rule evidence reviewer",
            "prepared_at": "2026-09-21T17:00:00Z",
            "selections": [{
                "occurrence_id": occurrence,
                "paragraph_locator": "a",
            }],
        })
        if with_trace:
            source = next(s for s in case["sources"] if s["source_id"] == "sol")
            snapshot = freeze_text_snapshot(
                source=source,
                source_key="solicitation-main",
                kind="SOLICITATION",
                version_label="Current solicitation",
                text=SOL_TEXT,
                capture_method="NATIVE_TEXT",
                captured_by="Decision reviewer",
                mapping_note="Illustrative solicitation text retained for applicability basis.",
                published_at="2026-09-20T12:00:00Z",
            )
            basis = passage(snapshot, 2, 2, locator="Solicitation clause incorporation")
            case["decision_trace"] = {
                "schema_version": "1.0",
                "family_id": case["family_id"],
                "decision_at": "2026-09-21T17:05:00Z",
                "snapshots": [snapshot],
                "rule_versions": [],
                "reviews": [{
                    "assumption_id": "A1",
                    "evidence_state": "UNPROVEN",
                    "finding": case["assumptions"][0]["finding"],
                    "citations": [{**basis, "role": "CONTEXT"}],
                    "rule_scope": {
                        "status": "REQUIRED",
                        "rationale": "The assumption depends on the cited safeguarding rule.",
                    },
                    "rule_links": [],
                    "evidence_request": "Provide evidence that the proposed approach satisfies the incorporated safeguarding requirement.",
                    "changes": [],
                    "reviewed_by": "Decision reviewer",
                    "reviewed_at": "2026-09-21T17:05:00Z",
                }],
            }
        return case

    def applicability_review(self, case, *, applicability="APPLIES", basis="INCORPORATED_EDITION"):
        item = prepared_rule_evidence(case)[0]
        trace = case["decision_trace"]
        sol_snapshot = next(s for s in trace["snapshots"] if s["source_id"] == "sol")
        decision = {
            "occurrence_id": item["occurrence_id"],
            "assumption_id": "A1",
            "applicability": applicability,
            "basis": basis,
            "rationale": (
                "The solicitation explicitly incorporates this pinned edition."
                if applicability != "UNRESOLVED"
                else "The available evidence does not yet establish applicability."
            ),
            "scope_rationale": "This assumption depends on whether the cited FAR requirement governs the pursuit.",
        }
        if applicability != "UNRESOLVED":
            decision["basis_passage"] = passage(
                sol_snapshot, 2, 2, locator="Solicitation clause incorporation"
            )
        if basis == "INCORPORATED_EDITION":
            decision["incorporated_edition"] = item["rule_version"]["edition"]
        return {
            "reviewed_by": "Applicability reviewer",
            "reviewed_at": "2026-09-21T17:15:00Z",
            "decisions": [decision],
        }

    def test_task_waits_until_decision_trace_exists(self):
        case = self.prepared_case(with_trace=False)
        self.assertIsNone(rule_applicability_work_item(case))
        queue = build_work_queue(case, now=NOW)
        self.assertFalse(any(t["task_key"] == "rules:review-applicability" for t in queue["tasks"]))
        self.assertTrue(any(t["task_key"].startswith("trace:") for t in queue["tasks"]))

    def test_applies_requires_separate_solicitation_basis(self):
        case = self.prepared_case()
        task = rule_applicability_work_item(case)
        self.assertIsNotNone(task)
        self.assertEqual(task["actor"], "HUMAN_REVIEW")
        self.assertFalse(task["can_auto_execute"])
        before_assumption = copy.deepcopy(case["assumptions"][0])
        updated, transition = review_rule_applicability(
            case, self.applicability_review(case)
        )
        self.assertEqual(transition["status"], "RULE_APPLICABILITY_REVIEW_ATTACHED")
        self.assertTrue(rule_applicability_review_is_current(updated))
        self.assertEqual(updated["assumptions"][0], before_assumption)
        self.assertFalse(transition["assumption_state_changed"])
        self.assertFalse(transition["can_auto_apply"])
        app = updated["packet"]["rule_applicability_review"]
        self.assertFalse(app["decisions"][0]["applicability_authoritative"])
        self.assertTrue(app["decisions"][0]["human_reviewed"])
        trace_review = updated["decision_trace"]["reviews"][0]
        self.assertEqual(len(trace_review["rule_links"]), 1)
        link = trace_review["rule_links"][0]
        self.assertEqual(link["applicability"], "APPLIES")
        self.assertEqual(link["incorporated_edition"], "Nov 2021")
        self.assertEqual(link["reviewed_by"], "Applicability reviewer")
        self.assertEqual(link["basis_passage"]["source_id"] if "source_id" in link["basis_passage"] else link["basis_passage"]["snapshot_id"], link["basis_passage"]["snapshot_id"])
        result = evaluate_decision_trace(updated, now=NOW)
        self.assertEqual(result["trace_state"], "TRACE_COMPLETE")
        self.assertIsNone(rule_applicability_work_item(updated))

    def test_resolved_applicability_requires_basis_passage(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"][0].pop("basis_passage")
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_rule_text_cannot_be_its_own_applicability_basis(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"][0]["basis_passage"] = prepared_rule_evidence(case)[0]["text_passage"]
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_incorporated_edition_must_match_exact_prepared_edition(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"][0]["incorporated_edition"] = "Sep 2026"
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_basis_quote_must_match_retained_source(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"][0]["basis_passage"]["quote"] = "rewritten quote"
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_unresolved_is_allowed_without_false_resolution(self):
        case = self.prepared_case()
        review = self.applicability_review(
            case, applicability="UNRESOLVED", basis="UNRESOLVED"
        )
        updated, _ = review_rule_applicability(case, review)
        link = updated["decision_trace"]["reviews"][0]["rule_links"][0]
        self.assertEqual(link["applicability"], "UNRESOLVED")
        self.assertIsNone(link["basis_passage"])
        self.assertTrue(rule_applicability_review_is_current(updated))
        self.assertEqual(
            evaluate_decision_trace(updated, now=NOW)["trace_state"],
            "TRACE_COMPLETE",
        )

    def test_unresolved_cannot_carry_resolved_basis(self):
        case = self.prepared_case()
        review = self.applicability_review(
            case, applicability="UNRESOLVED", basis="UNRESOLVED"
        )
        review["decisions"][0]["basis"] = "SOLICITATION_TEXT"
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_unknown_assumption_rejected(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"][0]["assumption_id"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_existing_different_rule_link_is_not_rewritten(self):
        case = self.prepared_case()
        updated, _ = review_rule_applicability(case, self.applicability_review(case))
        review = self.applicability_review(updated)
        review["decisions"][0]["applicability"] = "DOES_NOT_APPLY"
        review["decisions"][0]["rationale"] = "Different later conclusion."
        with self.assertRaises(ValueError):
            review_rule_applicability(updated, review)

    def test_tampered_application_review_reopens_task(self):
        case = self.prepared_case()
        updated, _ = review_rule_applicability(case, self.applicability_review(case))
        updated["packet"]["rule_applicability_review"]["decisions"][0]["rationale"] = "tampered"
        self.assertFalse(rule_applicability_review_is_current(updated))
        self.assertIsNotNone(rule_applicability_work_item(updated))

    def test_every_prepared_occurrence_must_be_reviewed(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["decisions"] = []
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)

    def test_timezone_aware_reviewer_time_required(self):
        case = self.prepared_case()
        review = self.applicability_review(case)
        review["reviewed_at"] = "2026-09-21T17:15:00"
        with self.assertRaises(ValueError):
            review_rule_applicability(case, review)


if __name__ == "__main__":
    unittest.main()
