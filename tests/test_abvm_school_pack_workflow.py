import copy
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "abvm-school-pack.yml"
VALIDATOR = ROOT / "scripts" / "validate_abvm_school_pack.py"


def load_validator():
    if not VALIDATOR.exists():
        raise unittest.SkipTest("validator not implemented yet")
    spec = importlib.util.spec_from_file_location("validate_abvm_school_pack", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fresh_payload():
    return {
        "source": "ABVM Grade 2 sanitized study feed",
        "sourceLastSeenAt": "2026-10-15T13:00:00Z",
        "sourceCapturedAt": "2026-10-15T12:00:00Z",
        "freshnessHours": 14.0,
        "pack": {
            "schemaVersion": 2,
            "weekLabel": "Thursday October 15, 2026",
            "sourceCapturedAt": "2026-10-15T12:00:00Z",
            "sourceSufficient": True,
            "sourceHash": "a" * 64,
            "generatedAt": "2026-10-15T13:00:00Z",
            "questions": [
                {"id": "q1", "prompt": "What is two plus two?", "answer": "four"}
            ],
        },
    }


class AbvmSchoolPackWorkflowPolicyTests(unittest.TestCase):
    def test_workflow_uses_trusted_fail_closed_validator(self):
        text = WORKFLOW.read_text()
        self.assertIn("scripts/validate_abvm_school_pack.py", text)
        self.assertIn("Verify exact current main before write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("target.write_text(json.dumps(data", text)


    def test_only_stale_primary_bridge_invokes_exact_publication_fallback(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("ABVM_PACK_REJECTED:STALE_SOURCE:age_hours=", workflow)
        self.assertIn("prepare_abvm_canonical_fallback.py", workflow)
        self.assertIn(
            "raw.githubusercontent.com/P00NSMASHER/abvmschoolstarworld/main/pages/data/study-pack.json",
            workflow,
        )
        self.assertIn(
            "p00nsmasher.github.io/abvmschoolstarworld/data/study-pack.json",
            workflow,
        )
        self.assertEqual(
            workflow.count("python .trusted/scripts/validate_abvm_school_pack.py"), 2
        )
        self.assertNotIn("continue-on-error: true", workflow)


class AbvmSchoolPackValidationTests(unittest.TestCase):
    NOW = datetime(2026, 10, 16, 2, 0, tzinfo=timezone.utc)

    def test_current_pack_is_accepted_and_normalized(self):
        module = load_validator()
        normalized, changed = module.prepare_school_pack(
            fresh_payload(), existing=None, now=self.NOW
        )
        self.assertTrue(changed)
        self.assertNotIn("freshnessHours", normalized)
        self.assertNotIn("sourceLastSeenAt", normalized)
        self.assertNotIn("generatedAt", normalized["pack"])

    def test_stale_pack_fails_closed(self):
        module = load_validator()
        payload = fresh_payload()
        payload["sourceCapturedAt"] = "2026-09-18T00:37:35.100Z"
        payload["pack"]["sourceCapturedAt"] = payload["sourceCapturedAt"]
        with self.assertRaisesRegex(module.PackValidationError, "STALE_SOURCE"):
            module.prepare_school_pack(payload, existing=None, now=self.NOW)

    def test_bridge_freshness_uses_last_seen_not_original_content_capture(self):
        module = load_validator()
        payload = fresh_payload()
        payload["sourceCapturedAt"] = "2026-10-12T12:00:00Z"
        payload["pack"]["sourceCapturedAt"] = payload["sourceCapturedAt"]
        payload["pack"]["weekLabel"] = "Monday October 12, 2026"
        payload["sourceLastSeenAt"] = "2026-10-16T01:55:00Z"
        payload["freshnessHours"] = 5 / 60
        normalized, changed = module.prepare_school_pack(
            payload, existing=None, now=self.NOW
        )
        self.assertTrue(changed)
        self.assertEqual(normalized["sourceCapturedAt"], payload["sourceCapturedAt"])
        self.assertNotIn("sourceLastSeenAt", normalized)

    def test_a_recent_recheck_does_not_resurrect_content_over_seven_days_old(self):
        module = load_validator()
        payload = fresh_payload()
        payload["sourceCapturedAt"] = "2026-10-08T00:00:00Z"
        payload["pack"]["sourceCapturedAt"] = payload["sourceCapturedAt"]
        payload["pack"]["weekLabel"] = "Thursday October 8, 2026"
        payload["sourceLastSeenAt"] = "2026-10-16T01:55:00Z"
        payload["freshnessHours"] = 5 / 60
        with self.assertRaisesRegex(module.PackValidationError, "STALE_SOURCE"):
            module.prepare_school_pack(payload, existing=None, now=self.NOW)

    def test_bridge_freshness_cannot_disagree_with_last_source_check(self):
        module = load_validator()
        payload = fresh_payload()
        payload["sourceLastSeenAt"] = "2026-10-16T01:55:00Z"
        payload["freshnessHours"] = 14.0  # capture age, not the five-minute check age
        with self.assertRaisesRegex(module.PackValidationError, "FRESHNESS_TIMESTAMP_MISMATCH"):
            module.prepare_school_pack(payload, existing=None, now=self.NOW)

    def test_freshness_without_optional_last_seen_uses_capture_age(self):
        module = load_validator()
        payload = fresh_payload()
        payload.pop("sourceLastSeenAt")
        payload["freshnessHours"] = 14.0
        normalized, changed = module.prepare_school_pack(
            payload, existing=None, now=self.NOW
        )
        self.assertTrue(changed)
        self.assertEqual(normalized["pack"]["sourceHash"], payload["pack"]["sourceHash"])

    def test_same_source_hash_cannot_change_semantic_content(self):
        module = load_validator()
        existing, _ = module.prepare_school_pack(
            fresh_payload(), existing=None, now=self.NOW
        )
        incoming = fresh_payload()
        incoming["pack"]["questions"][0]["answer"] = "five"
        with self.assertRaisesRegex(
            module.PackValidationError, "SOURCE_HASH_REUSE_WITH_CHANGED_CONTENT"
        ):
            module.prepare_school_pack(incoming, existing=existing, now=self.NOW)

    def test_observation_only_fields_do_not_create_publication_change(self):
        module = load_validator()
        existing, _ = module.prepare_school_pack(
            fresh_payload(), existing=None, now=self.NOW
        )
        incoming = copy.deepcopy(fresh_payload())
        incoming["sourceLastSeenAt"] = "2026-10-16T01:55:00Z"
        incoming["freshnessHours"] = 13.9167
        incoming["pack"]["generatedAt"] = "2026-10-16T01:55:00Z"
        normalized, changed = module.prepare_school_pack(
            incoming, existing=existing, now=self.NOW
        )
        self.assertFalse(changed)
        self.assertEqual(existing, normalized)


if __name__ == "__main__":
    unittest.main()
