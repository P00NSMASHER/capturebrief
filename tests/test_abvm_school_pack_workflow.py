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
