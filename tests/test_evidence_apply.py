import unittest
from datetime import datetime, timezone

from capturebrief_core.current_api import make_current_action_receipt
from capturebrief_core.data_services import (
    ACTIVE_DATA_SERVICES_PAGE,
    ACTIVE_DOWNLOAD,
    ARCHIVE_DOWNLOAD,
)
from capturebrief_core.evidence_apply import (
    EvidenceApplyError,
    apply_approved_evidence,
    apply_byte_receipt,
    apply_current_api_evidence,
    apply_history_receipt,
)
from capturebrief_core.intake import build_case_from_intake
from capturebrief_core.model import canonical_json, history_set_digest, sha256_hex
from capturebrief_core.workqueue import build_work_queue

NOW = datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc)
LINK = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/r2/download"


def base_case():
    return build_case_from_intake({
        "email": "buyer@example.com",
        "company": "Example Federal",
        "public_opportunity": "https://sam.gov/opp/a2/view",
        "current_posture": "GO",
        "assumption_1": "The deadline is still Friday.",
        "public_only_confirmation": "yes",
    }, submitted_at=NOW.isoformat())


def history(actions=("a1", "a2")):
    action_ids = list(actions)
    action_rows = [
        {
            "notice_id": action_id,
            "observations": [{"row_sha256": sha256_hex(action_id)}],
        }
        for action_id in action_ids
    ]
    payload = {
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
        "family": {
            "solicitation_number": "SOL-1",
            "aac_code": "AAC1",
            "office": "Office",
            "seed_notice_id": action_ids[-1],
        },
        "scope": {
            "start_fy": 2026,
            "end_fy": 2026,
            "scope_confirmed": True,
            "required_archive_fys": [2026],
            "supplied_archive_fys": [2026],
            "missing_archive_fys": [],
            "active_extract_present": True,
        },
        "actions": action_rows,
        "source_snapshots": [
            {
                "source_kind": "ACTIVE",
                "fiscal_year": None,
                "source_url": ACTIVE_DOWNLOAD,
                "extract_sha256": "c" * 64,
                "rows_scanned": 100,
            },
            {
                "source_kind": "ARCHIVE",
                "fiscal_year": 2026,
                "source_url": ARCHIVE_DOWNLOAD.format(fy=2026),
                "extract_sha256": "d" * 64,
                "rows_scanned": 200,
            },
        ],
        "ordering_authoritative": False,
        "current_action_authoritative": False,
    }
    return {
        "source_surface": "SAM_DATA_SERVICES",
        "source_url": ACTIVE_DATA_SERVICES_PAGE,
        "observed_at": NOW.isoformat(),
        "status": "COMPLETE",
        "action_ids": action_ids,
        "history_set_sha256": history_set_digest(action_ids),
        "evidence_payload_sha256": sha256_hex(canonical_json(payload)),
        "evidence_payload": payload,
        "automation_mode": "APPROVED_EXTRACT",
    }


def observation(action="a2"):
    payload = {"opportunitiesData": [{"noticeId": action}]}
    return {
        "record": {
            "noticeId": action,
            "solicitationNumber": "SOL-1",
            "postedDate": "2026-09-20",
            "active": "Yes",
            "resourceLinks": [LINK],
        },
        "source_url": "https://api.sam.gov/opportunities/v2/search",
        "observed_at": NOW.isoformat(),
        "payload_sha256": sha256_hex(canonical_json(payload)),
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
        "resource_links": [LINK],
    }


def byte_receipt():
    return {
        "source_contract": "SAM_GET_OPPORTUNITIES_RESOURCE_LINK",
        "automation_mode": "APPROVED_API",
        "source_url": LINK,
        "final_url": "https://objects.example/r2",
        "observed_at": NOW.isoformat(),
        "byte_state": "BYTES_VERIFIED_HASHED",
        "sha256": "e" * 64,
        "size": 1234,
        "api_payload_sha256": "f" * 64,
    }


class EvidenceApplyTests(unittest.TestCase):
    def test_history_evidence_does_not_upgrade_assumption(self):
        case = apply_history_receipt(base_case(), history())
        self.assertEqual(case["family_id"], "SAM-SOL-1-AAC1")
        self.assertEqual(case["packet"]["history_action_ids"], ["a1", "a2"])
        self.assertEqual(case["assumptions"][0]["evidence_state"], "UNPROVEN")
        self.assertEqual(case["assumptions"][0]["source_ids"], [])

        keys = {
            task["task_key"]
            for task in build_work_queue(case, now=NOW)["tasks"]
        }
        self.assertNotIn("history:establish", keys)
        self.assertIn("family:status", keys)

    def test_semantically_invalid_history_receipt_is_rejected_before_mutation(self):
        bad = history()
        bad["evidence_payload"]["current_action_authoritative"] = True
        bad["evidence_payload_sha256"] = sha256_hex(
            canonical_json(bad["evidence_payload"])
        )
        original = base_case()
        with self.assertRaises(EvidenceApplyError):
            apply_history_receipt(original, bad)
        self.assertEqual(original["packet"]["history_action_ids"], [])

    def test_current_evidence_binds_to_history_and_shrinks_queue(self):
        case = apply_history_receipt(base_case(), history())
        obs = observation()
        receipt = make_current_action_receipt(
            obs,
            history_action_ids=["a1", "a2"],
        )
        case = apply_current_api_evidence(case, receipt, obs)

        self.assertEqual(case["packet"]["family_status"], "ACTIVE")
        self.assertEqual(case["packet"]["current_action_id"], "a2")
        self.assertEqual(case["packet"]["artifacts"][0]["artifact_id"], "r2")
        self.assertEqual(case["packet"]["artifacts"][0]["state"], "UNKNOWN")

        keys = {
            task["task_key"]
            for task in build_work_queue(case, now=NOW)["tasks"]
        }
        self.assertNotIn("family:status", keys)
        self.assertNotIn("current:authority", keys)
        self.assertIn("manifest:a1", keys)
        self.assertIn("manifest:a2", keys)
        self.assertEqual(case["assumptions"][0]["evidence_state"], "UNPROVEN")

    def test_history_change_invalidates_old_current_receipt(self):
        case = apply_history_receipt(base_case(), history())
        obs = observation()
        receipt = make_current_action_receipt(
            obs,
            history_action_ids=["a1", "a2"],
        )
        case = apply_current_api_evidence(case, receipt, obs)
        case = apply_history_receipt(case, history(("a1", "a3")))

        self.assertEqual(case["current_action_receipts"], [])
        self.assertEqual(case["packet"]["family_status"], "UNKNOWN")
        self.assertNotIn("current_action_id", case["packet"])
        self.assertEqual(
            len(case["packet"]["prior_current_action_receipts"]),
            1,
        )

    def test_byte_receipt_promotes_artifact_and_clears_byte_task(self):
        case = apply_history_receipt(base_case(), history())
        obs = observation()
        receipt = make_current_action_receipt(
            obs,
            history_action_ids=["a1", "a2"],
        )
        case = apply_current_api_evidence(case, receipt, obs)
        case["packet"]["artifacts"][0]["required_for_analysis"] = True

        keys = {
            task["task_key"]
            for task in build_work_queue(case, now=NOW)["tasks"]
        }
        self.assertIn("bytes:r2", keys)

        case = apply_byte_receipt(
            case,
            byte_receipt(),
            required_for_analysis=True,
        )
        artifact = next(
            artifact
            for artifact in case["packet"]["artifacts"]
            if artifact["artifact_id"] == "r2"
        )
        self.assertEqual(artifact["state"], "PUBLIC")
        self.assertEqual(artifact["byte_state"], "BYTES_VERIFIED_HASHED")
        self.assertEqual(artifact["sha256"], "e" * 64)

        keys = {
            task["task_key"]
            for task in build_work_queue(case, now=NOW)["tasks"]
        }
        self.assertNotIn("bytes:r2", keys)

    def test_combined_apply_is_idempotent(self):
        obs = observation()
        hist = history()
        receipt = make_current_action_receipt(
            obs,
            history_action_ids=["a1", "a2"],
        )
        case = apply_approved_evidence(
            base_case(),
            history_receipt=hist,
            current_receipt=receipt,
            api_observation=obs,
        )
        case2 = apply_approved_evidence(
            case,
            history_receipt=hist,
            current_receipt=receipt,
            api_observation=obs,
        )
        source_ids = [source["source_id"] for source in case2["sources"]]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(len(case2["current_action_receipts"]), 1)
        self.assertEqual(
            len([
                artifact
                for artifact in case2["packet"]["artifacts"]
                if artifact["artifact_id"] == "r2"
            ]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
