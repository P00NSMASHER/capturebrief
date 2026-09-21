import unittest
from datetime import datetime, timezone

from capturebrief_core.intake import IntakeError, build_case_from_intake
from capturebrief_core.workqueue import build_work_queue

NOW = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)


def intake():
    return {
        "email": "buyer@example.com",
        "company": "Example Federal",
        "public_opportunity": "https://sam.gov/opp/example/view",
        "current_posture": "GO",
        "assumption_1": "The current deadline is still Friday.",
        "assumption_2": "We can submit revised pages only.",
        "question": "Please focus on submission mechanics.",
        "public_only_confirmation": "yes",
    }


class OperatorWorkflowTests(unittest.TestCase):
    def test_intake_builds_unproven_case_without_invented_sources(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        self.assertEqual(case["current_posture"], "GO")
        self.assertEqual(len(case["assumptions"]), 2)
        self.assertTrue(
            all(x["evidence_state"] == "UNPROVEN" for x in case["assumptions"])
        )
        self.assertTrue(
            all(x["decision_class"] == "VERIFY_NOW" for x in case["assumptions"])
        )
        self.assertTrue(all(x["source_ids"] == [] for x in case["assumptions"]))
        self.assertEqual(case["sources"], [])

    def test_intake_requires_public_only_confirmation(self):
        data = intake()
        data["public_only_confirmation"] = "no"
        with self.assertRaises(IntakeError):
            build_case_from_intake(data)

    def test_initial_work_queue_is_actionable_and_deduplicated(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        queue = build_work_queue(case, now=NOW)
        keys = [x["task_key"] for x in queue["tasks"]]

        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("history:establish", keys)
        self.assertIn("family:status", keys)
        self.assertIn("references:propose", keys)
        self.assertIn("assumption-source:A1", keys)
        self.assertTrue(queue["release_blocked"])
        self.assertGreaterEqual(queue["summary"]["auto_executable"], 2)

    def test_complete_shared_index_queues_history_receipt_issue(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        plan = {
            "complete": True,
            "fiscal_year": 2026,
            "download_plan": [],
        }
        observation = {
            "record": {
                "noticeId": "current-action",
                "solicitationNumber": "SOL-123",
            },
            "resource_links": [],
        }
        queue = build_work_queue(
            case,
            api_observation=observation,
            history_index_plan=plan,
            now=NOW,
        )
        keys = {x["task_key"] for x in queue["tasks"]}
        self.assertIn("history:issue-from-index", keys)
        self.assertNotIn("history:establish", keys)
        task = next(x for x in queue["tasks"] if x["task_key"] == "history:issue-from-index")
        self.assertTrue(task["can_auto_execute"])
        self.assertEqual(task["metadata"]["seed_notice_id"], "current-action")

    def test_complete_index_without_api_seed_queues_seed_observation(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        queue = build_work_queue(
            case,
            history_index_plan={"complete": True, "fiscal_year": 2026, "download_plan": []},
            now=NOW,
        )
        keys = {x["task_key"] for x in queue["tasks"]}
        self.assertIn("history:seed-current-action", keys)
        self.assertNotIn("history:establish", keys)

    def test_incomplete_shared_index_queues_exact_refresh_plan(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        plan = {
            "complete": False,
            "fiscal_year": 2026,
            "download_plan": [
                {"slot": "ACTIVE", "reason": "STALE", "source_url": "https://sam.gov/example-active"},
                {"slot": "ARCHIVE:2026", "reason": "MISSING", "source_url": "https://sam.gov/example-archive"},
                {"slot": "ARCHIVE:2025", "reason": "UNVERIFIED", "source_url": "https://sam.gov/example-archive-2"},
            ],
        }
        queue = build_work_queue(case, history_index_plan=plan, now=NOW)
        task = next(x for x in queue["tasks"] if x["task_key"] == "history-index:refresh")
        self.assertTrue(task["can_auto_execute"])
        self.assertEqual(task["metadata"]["reason_counts"], {"STALE": 1, "MISSING": 1, "UNVERIFIED": 1})
        self.assertEqual(len(task["metadata"]["download_plan"]), 3)
        self.assertNotIn("history:establish", {x["task_key"] for x in queue["tasks"]})

    def test_proposed_reference_scan_requires_human_review(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        case["packet"]["reference_scan"] = {
            "status": "PROPOSED",
            "proposal_sha256": "a" * 64,
        }
        queue = build_work_queue(case, now=NOW)
        keys = {x["task_key"] for x in queue["tasks"]}
        self.assertIn("references:review-proposal", keys)
        self.assertNotIn("references:propose", keys)
        task = next(x for x in queue["tasks"] if x["task_key"] == "references:review-proposal")
        self.assertFalse(task["can_auto_execute"])
        self.assertEqual(task["actor"], "HUMAN_REVIEW")

    def test_required_current_api_resource_can_be_auto_executable(self):
        case = build_case_from_intake(
            intake(),
            submitted_at="2026-09-21T15:00:00+00:00",
        )
        link = (
            "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/"
            "r1/download"
        )
        case["packet"]["artifacts"] = [{
            "artifact_id": "r1",
            "name": "Current solicitation.pdf",
            "state": "PUBLIC",
            "required_for_analysis": True,
            "sha256": None,
            "byte_state": "BYTES_NOT_YET_CHECKED",
            "resource_url": link,
        }]

        queue = build_work_queue(
            case,
            api_observation={"resource_links": [link]},
            now=NOW,
        )
        task = next(x for x in queue["tasks"] if x["task_key"] == "bytes:r1")
        self.assertTrue(task["can_auto_execute"])
        self.assertEqual(task["actor"], "AUTOMATED_APPROVED_SOURCE")


if __name__ == "__main__":
    unittest.main()
