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
        self.assertIn("references:scan", keys)
        self.assertIn("assumption-source:A1", keys)
        self.assertTrue(queue["release_blocked"])
        self.assertGreaterEqual(queue["summary"]["auto_executable"], 2)

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
