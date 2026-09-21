from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.rule_candidates import (
    attach_rule_candidate_proposal,
    attach_rule_candidate_review,
    rule_candidate_review_is_current,
    rule_sync_work_items,
    sync_missing_rule_candidates_for_case,
)
from capturebrief_core.rule_registry import digest
from capturebrief_core.workqueue import build_work_queue

FAR_DITA = b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="FAR_52_204_21">
<title><ph props="autonumber">52.204-21</ph> Basic Safeguarding.</title>
<conbody outputclass="clause">
<p id="heading" outputclass="Ctr_SmCaps">Basic Safeguarding (Nov 2021)</p>
<p id="a">Synthetic FAR text.</p>
</conbody></concept></dita>'''

DFARS_DITA = b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="DFARS_252_204_7012">
<title><ph props="autonumber">252.204-7012</ph> Safeguarding Covered Defense Information.</title>
<conbody outputclass="clause">
<p id="heading" outputclass="Ctr_SmCaps">Safeguarding Covered Defense Information (Jan 2023)</p>
<p id="a">Synthetic DFARS text.</p>
</conbody></concept></dita>'''


def base_case():
    return {
        "case_schema_version": "0.2",
        "case_id": "CB-AUTO-RULE",
        "family_id": "FAM-AUTO",
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
            "content_sha256": digest(b"synthetic-source"),
        }],
        "assumptions": [{
            "assumption_id": "A1",
            "text": "Rule treatment is understood.",
            "evidence_state": "UNPROVEN",
            "decision_class": "VERIFY_NOW",
            "finding": "Rule edition and applicability require review.",
            "owner": "Reviewer",
            "next_action": "Review rule.",
            "source_ids": ["sol"],
        }],
    }


class RuleAutoSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "rules.sqlite"
        self.catalog = Path(__file__).parents[1] / "RULE-SOURCE-CATALOG.json"

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self, text="FAR 52.204-21 is listed."):
        case, _ = attach_rule_candidate_proposal(
            base_case(),
            self.registry,
            [{"source_id": "sol", "text": text}],
            captured_by="Reviewer",
            observed_at="2026-09-21T16:30:00Z",
        )
        return case

    def fetcher(self, url, max_bytes):
        if "/GSA/GSA-Acquisition-FAR/" in url and url.endswith("/dita/52.204-21.dita"):
            return FAR_DITA, url
        if "/GSA/GSA-Acquisition-DFARS/" in url and url.endswith("/dita/252.204-7012.dita"):
            return DFARS_DITA, url
        raise AssertionError(f"unexpected sync URL {url}")

    def test_missing_rule_creates_p0_approved_source_task(self):
        case = self.proposal()
        tasks = rule_sync_work_items(case)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["priority"], "P0")
        self.assertEqual(task["actor"], "AUTOMATED_APPROVED_SOURCE")
        self.assertTrue(task["can_auto_execute"])
        self.assertFalse(task["metadata"]["can_auto_apply"])
        self.assertEqual(task["metadata"]["rules"][0]["citation"], "52.204-21")

    def test_work_queue_prefers_sync_before_human_version_review(self):
        queue = build_work_queue(self.proposal())
        keys = [t["task_key"] for t in queue["tasks"]]
        self.assertIn("rules:sync-missing-pinned-sources", keys)
        self.assertIn("rules:review-candidates", keys)
        self.assertLess(
            keys.index("rules:sync-missing-pinned-sources"),
            keys.index("rules:review-candidates"),
        )
        sync = next(t for t in queue["tasks"] if t["task_key"] == "rules:sync-missing-pinned-sources")
        review = next(t for t in queue["tasks"] if t["task_key"] == "rules:review-candidates")
        self.assertEqual(sync["priority"], "P0")
        self.assertEqual(review["priority"], "P1")

    def test_sync_refreshes_proposal_and_preserves_old_proposal(self):
        case = self.proposal()
        old_sha = case["packet"]["rule_candidate_proposal"]["proposal_sha256"]
        updated, transition = sync_missing_rule_candidates_for_case(
            case,
            self.registry,
            self.catalog,
            observed_at="2026-09-21T17:00:00Z",
            fetcher=self.fetcher,
        )
        proposal = updated["packet"]["rule_candidate_proposal"]
        self.assertEqual(transition["status"], "MISSING_PINNED_RULES_SYNCED")
        self.assertNotEqual(proposal["proposal_sha256"], old_sha)
        self.assertEqual(proposal["refreshed_from_proposal_sha256"], old_sha)
        self.assertEqual(proposal["matches"][0]["candidate_count"], 1)
        self.assertEqual(proposal["matches"][0]["candidate_versions"][0]["edition"], "Nov 2021")
        self.assertEqual(updated["packet"]["rule_candidate_proposal_history"][0]["proposal_sha256"], old_sha)
        self.assertEqual(rule_sync_work_items(updated), [])
        self.assertFalse(transition["can_auto_apply"])

    def test_sync_deduplicates_same_missing_citation(self):
        case = self.proposal("FAR 52.204-21 is listed twice: 52.204-21.")
        updated, transition = sync_missing_rule_candidates_for_case(
            case, self.registry, self.catalog,
            observed_at="2026-09-21T17:00:00Z", fetcher=self.fetcher,
        )
        self.assertEqual(len(transition["synced"]), 1)
        self.assertTrue(all(row["candidate_count"] == 1 for row in updated["packet"]["rule_candidate_proposal"]["matches"]))

    def test_existing_unresolved_review_is_archived_and_invalidated(self):
        case = self.proposal()
        occurrence = case["packet"]["rule_candidate_proposal"]["matches"][0]["occurrence_id"]
        reviewed, _ = attach_rule_candidate_review(case, {
            "reviewer": "Human reviewer",
            "reviewed_at": "2026-09-21T16:45:00Z",
            "decisions": [{
                "occurrence_id": occurrence,
                "decision": "UNRESOLVED",
                "reason": "No pinned source version was available yet.",
            }],
        })
        self.assertTrue(rule_candidate_review_is_current(reviewed))
        updated, transition = sync_missing_rule_candidates_for_case(
            reviewed, self.registry, self.catalog,
            observed_at="2026-09-21T17:00:00Z", fetcher=self.fetcher,
        )
        self.assertTrue(transition["review_invalidated"])
        self.assertNotIn("rule_candidate_review", updated["packet"])
        self.assertEqual(len(updated["packet"]["rule_candidate_review_history"]), 1)
        self.assertFalse(rule_candidate_review_is_current(updated))
        queue = build_work_queue(updated)
        self.assertTrue(any(t["task_key"] == "rules:review-candidates" for t in queue["tasks"]))

    def test_no_missing_rule_is_noop(self):
        case = self.proposal()
        case, _ = sync_missing_rule_candidates_for_case(
            case, self.registry, self.catalog,
            observed_at="2026-09-21T17:00:00Z", fetcher=self.fetcher,
        )
        before = copy.deepcopy(case)
        again, transition = sync_missing_rule_candidates_for_case(
            case, self.registry, self.catalog,
            observed_at="2026-09-21T17:01:00Z", fetcher=self.fetcher,
        )
        self.assertEqual(transition["status"], "NO_MISSING_PINNED_RULES")
        self.assertFalse(transition["case_changed"])
        self.assertEqual(again, before)

    def test_unknown_namespace_is_not_auto_fetched(self):
        case = self.proposal("100.123 appears as a bare numeric reference.")
        self.assertEqual(rule_sync_work_items(case), [])

    def test_case_not_mutated_if_later_sync_fails(self):
        case = self.proposal("FAR 52.204-21 and DFARS 252.204-7012 are listed.")
        before = copy.deepcopy(case)
        calls = 0
        def fail_second(url, max_bytes):
            nonlocal calls
            calls += 1
            if calls == 1:
                return self.fetcher(url, max_bytes)
            raise RuntimeError("simulated network failure")
        with self.assertRaises(RuntimeError):
            sync_missing_rule_candidates_for_case(
                case, self.registry, self.catalog,
                observed_at="2026-09-21T17:00:00Z", fetcher=fail_second,
            )
        self.assertEqual(case, before)


if __name__ == "__main__":
    unittest.main()
