from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.rule_candidates import (
    attach_rule_candidate_proposal,
    extract_rule_citations,
    match_rule_versions,
    rule_candidate_proposal_is_current,
    rule_candidate_work_item,
)
from capturebrief_core.rule_registry import add_rule_version, digest, parse_gsa_dita
from capturebrief_core.workqueue import build_work_queue

NOW = datetime(2026, 9, 21, 17, tzinfo=timezone.utc)


def rule(citation: str, namespace: str, edition: str, revision: str, text: str):
    dita = f'''<?xml version="1.0" encoding="UTF-8"?>
<concept id="r"><title><ph props="autonumber">{citation}</ph> Synthetic test rule</title>
<conbody><p id="a">{text}</p></conbody></concept>'''
    repo = "GSA/GSA-Acquisition-FAR" if namespace == "FAR" else "GSA/GSA-Acquisition-DFARS"
    agency = "FAR Council" if namespace == "FAR" else "DoD"
    return parse_gsa_dita(
        dita,
        namespace=namespace,
        agency=agency,
        edition=edition,
        source_repository=repo,
        source_revision=revision,
        source_path=f"dita/{citation}.dita",
        source_url=f"https://github.com/{repo}/blob/{revision}/dita/{citation}.dita",
        observed_at="2026-09-21T16:00:00Z",
    )


def case_with_source(text: str):
    return {
        "case_schema_version": "0.2",
        "case_id": "CB-RULE-DEMO",
        "family_id": "FAM-1",
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
            "source_id": "solicitation",
            "title": "Solicitation",
            "url": "https://sam.gov/opp/demo/view",
            "authority": "CONTROLLING_CURRENT",
            "artifact_state": "PUBLIC",
            "observed_at": "2026-09-21T15:00:00Z",
            "content_sha256": digest(b"synthetic-pdf-bytes"),
        }],
        "assumptions": [{
            "assumption_id": "A1",
            "text": "Cybersecurity clause is understood.",
            "evidence_state": "UNPROVEN",
            "decision_class": "VERIFY_NOW",
            "finding": "Rule edition/applicability still requires review.",
            "owner": "Reviewer",
            "next_action": "Review cited rule editions.",
            "source_ids": ["solicitation"],
        }],
    }


class RuleCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "rules.sqlite"
        add_rule_version(self.registry, rule("52.204-21", "FAR", "Nov 2021", "a" * 40, "Original FAR text."))
        add_rule_version(self.registry, rule("52.204-21", "FAR", "Sep 2026", "b" * 40, "Later FAR text."))
        add_rule_version(self.registry, rule("252.204-7012", "DFARS", "Jan 2023", "c" * 40, "DFARS text."))

    def tearDown(self):
        self.temp.cleanup()

    def extract(self, text):
        return extract_rule_citations([{
            "source_id": "solicitation",
            "document_sha256": "d" * 64,
            "text": text,
        }], captured_by="Reviewer", observed_at="2026-09-21T16:30:00Z")

    def test_explicit_far_and_dfars(self):
        x = self.extract("FAR 52.204-21 applies here. DFARS 252.204-7012 is also listed.")
        self.assertEqual([(o["namespace_hint"], o["citation"]) for o in x["occurrences"]],
                         [("FAR", "52.204-21"), ("DFARS", "252.204-7012")])
        self.assertFalse(x["can_auto_select_version"])
        self.assertFalse(x["can_auto_apply"])
        self.assertFalse(x["automatic_completeness_claim"])

    def test_bare_citation_uses_non_authoritative_hint(self):
        x = self.extract("The schedule lists 52.204-21.")
        row = x["occurrences"][0]
        self.assertEqual(row["namespace_hint"], "FAR")
        self.assertEqual(row["namespace_hint_basis"], "NUMBER_RANGE_HEURISTIC")

    def test_decimal_false_positive_reduced(self):
        x = self.extract("The proposed price is 12.50 and the ratio is 1.25.")
        self.assertEqual(x["occurrences"], [])

    def test_all_matching_editions_are_retained(self):
        x = match_rule_versions(self.registry, self.extract("FAR 52.204-21 is listed."))
        row = x["matches"][0]
        self.assertEqual(row["candidate_count"], 2)
        self.assertEqual({c["edition"] for c in row["candidate_versions"]}, {"Nov 2021", "Sep 2026"})
        self.assertFalse(row["can_auto_select_version"])
        self.assertFalse(row["can_auto_apply"])

    def test_unmatched_explicit_citation_is_visible(self):
        x = match_rule_versions(self.registry, self.extract("FAR 52.999-99 is listed."))
        self.assertEqual(x["matches"][0]["candidate_count"], 0)

    def test_attach_binds_to_case_source_hash(self):
        case = case_with_source("FAR 52.204-21")
        updated, result = attach_rule_candidate_proposal(
            case, self.registry, [{"source_id": "solicitation", "text": "FAR 52.204-21"}],
            captured_by="Reviewer", observed_at="2026-09-21T16:30:00Z",
        )
        proposal = updated["packet"]["rule_candidate_proposal"]
        self.assertEqual(result["status"], "RULE_CANDIDATE_PROPOSAL_ATTACHED")
        self.assertTrue(rule_candidate_proposal_is_current(updated))
        self.assertEqual(proposal["matches"][0]["candidate_count"], 2)

    def test_unknown_case_source_rejected(self):
        with self.assertRaises(ValueError):
            attach_rule_candidate_proposal(
                case_with_source("x"), self.registry, [{"source_id": "other", "text": "FAR 52.204-21"}],
                captured_by="Reviewer",
            )

    def test_nonpublic_case_source_rejected(self):
        case = case_with_source("x")
        case["sources"][0]["artifact_state"] = "RESTRICTED"
        with self.assertRaises(ValueError):
            attach_rule_candidate_proposal(
                case, self.registry, [{"source_id": "solicitation", "text": "FAR 52.204-21"}],
                captured_by="Reviewer",
            )

    def test_tampered_proposal_is_not_current(self):
        case = case_with_source("x")
        updated, _ = attach_rule_candidate_proposal(
            case, self.registry, [{"source_id": "solicitation", "text": "FAR 52.204-21"}],
            captured_by="Reviewer",
        )
        updated["packet"]["rule_candidate_proposal"]["matches"][0]["candidate_count"] = 99
        self.assertFalse(rule_candidate_proposal_is_current(updated))

    def test_work_item_is_human_only(self):
        case = case_with_source("x")
        updated, _ = attach_rule_candidate_proposal(
            case, self.registry, [{"source_id": "solicitation", "text": "FAR 52.204-21"}],
            captured_by="Reviewer",
        )
        task = rule_candidate_work_item(updated)
        self.assertEqual(task["actor"], "HUMAN_REVIEW")
        self.assertFalse(task["can_auto_execute"])
        queue = build_work_queue(updated, now=NOW)
        queued = [t for t in queue["tasks"] if t["task_key"] == "rules:review-candidates"]
        self.assertEqual(len(queued), 1)
        self.assertFalse(queued[0]["metadata"]["can_auto_apply"])


if __name__ == "__main__":
    unittest.main()
