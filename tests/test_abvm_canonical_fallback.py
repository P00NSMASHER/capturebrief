"""Offline provenance and privacy checks for the canonical ABVM fallback."""
import copy
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_abvm_canonical_fallback import sanitized_candidate, FallbackError

NOW = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
CHECKED = "2026-11-01T05:00:00Z"
CAPTURED = "2026-10-29T16:54:08.074Z"
TITLES = ["Home", "Homework", "Reading Work", "Weekly Spelling List", "Tests", "Religion"]


def example():
    return {
        "source": "ABVM Grade 2 public teacher pages and uploaded school notices",
        "delivery": "verified",
        "sourceCapturedAt": CAPTURED,
        "sourceLastSeenAt": CHECKED,
        "sourceLastCheckedAt": CHECKED,
        "sourcePages": [
            {"title": name, "checkedAt": CHECKED, "contentHash": chr(97 + i) * 64}
            for i, name in enumerate(TITLES)
        ],
        "uploadedNotices": {"private": "PRIVATE-FAMILY-NOTE"},
        "pack": {
            "schemaVersion": 2,
            "sourceHash": "teacher-pages-7e345f8ef837196ec349",
            "sourceCapturedAt": CAPTURED,
            "sourceSufficient": True,
            "weekLabel": "Week of November 2, 2026",
            "summary": "Public Grade 2 study guidance.",
            "questions": [{"id": "q1", "prompt": "2 + 2?", "answer": "4"}],
            "homework": [{"day": "Monday", "subject": "Math", "task": "Review facts"}],
            "importantDates": [
                {"date": "2026-11-04", "label": "Public teacher test", "kind": "test", "source": "teacher-tests"},
                {"date": "2026-11-05", "label": "PRIVATE-FAMILY-NOTE", "source": "uploaded-notice"},
            ],
            "parentNotices": ["PRIVATE-FAMILY-NOTE"],
            "contentPipeline": {"private": "PRIVATE-FAMILY-NOTE"},
        },
    }


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def prepare(record=None, published=None, now=NOW):
    original = encoded(record if record is not None else example())
    return sanitized_candidate(original, original if published is None else encoded(published), now)


class CanonicalFallbackTests(unittest.TestCase):
    def test_exact_provenance_and_sanitized_teacher_fields(self):
        result = prepare()
        self.assertEqual(result["sourceCapturedAt"], CAPTURED)
        self.assertEqual(result["pack"]["sourceCapturedAt"], CAPTURED)
        self.assertRegex(result["pack"]["sourceHash"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["sourceProof"]["teacherPages"], sorted(TITLES))
        self.assertEqual(len(result["pack"]["importantDates"]), 1)
        self.assertNotIn("PRIVATE-FAMILY-NOTE", json.dumps(result))
        self.assertNotIn("parentNotices", result["pack"])
        self.assertNotIn("uploadedNotices", result)
        self.assertTrue(result["pack"]["sourceSufficient"])

    def test_deterministic_semantics_and_source_identity(self):
        self.assertEqual(prepare(), prepare())
        changed = example()
        changed["pack"]["questions"][0]["answer"] = "5"
        self.assertNotEqual(prepare()["pack"]["sourceHash"], prepare(record=changed)["pack"]["sourceHash"])

    def test_reject_repo_and_published_pages_mismatch(self):
        changed = example()
        changed["pack"]["questions"][0]["answer"] = "5"
        with self.assertRaisesRegex(FallbackError, "CANONICAL_PUBLICATION_BYTES_MISMATCH"):
            prepare(published=changed)

    def test_reject_missing_teacher_page_or_inconsistent_source_digest(self):
        for bad in ("page", "hash", "checked"):
            source = example()
            if bad == "page":
                source["sourcePages"].pop()
            elif bad == "hash":
                source["sourcePages"][0]["contentHash"] = "not-a-digest"
            else:
                source["sourcePages"][0]["checkedAt"] = "2026-10-31T00:00:00Z"
            with self.subTest(bad=bad), self.assertRaises(FallbackError):
                prepare(record=source)

    def test_reject_unverified_school_and_bad_identity(self):
        for bad in ("delivery", "sufficient", "sourcehash", "questions"):
            source = example()
            if bad == "delivery":
                source["delivery"] = "unverified"
            if bad == "sufficient":
                source["pack"]["sourceSufficient"] = False
            if bad == "sourcehash":
                source["pack"]["sourceHash"] = "0" * 64
            if bad == "questions":
                source["pack"]["questions"] = []
            with self.subTest(bad=bad), self.assertRaises(FallbackError):
                prepare(record=source)

    def test_reject_old_capture_without_rewriting_timestamp(self):
        source = example()
        source["sourceCapturedAt"] = "2026-10-01T05:00:00Z"
        source["pack"]["sourceCapturedAt"] = source["sourceCapturedAt"]
        with self.assertRaisesRegex(FallbackError, "STALE_SOURCE"):
            prepare(record=source)

    def test_reject_old_source_review_even_with_recent_capture(self):
        source = example()
        source["sourceLastCheckedAt"] = "2026-10-31T05:00:00Z"
        source["sourceLastSeenAt"] = source["sourceLastCheckedAt"]
        for item in source["sourcePages"]:
            item["checkedAt"] = source["sourceLastCheckedAt"]
        with self.assertRaisesRegex(FallbackError, "CANONICAL_REVIEW_TOO_OLD"):
            prepare(record=source)

    def test_reject_source_time_mismatch_or_future_clock(self):
        source = example()
        source["pack"]["sourceCapturedAt"] = "2026-10-30T05:00:00Z"
        with self.assertRaisesRegex(FallbackError, "CANONICAL_SOURCE_TIME_CONFLICT"):
            prepare(record=source)
        source = example()
        source["sourceLastCheckedAt"] = "2026-11-03T00:00:00Z"
        source["sourceLastSeenAt"] = source["sourceLastCheckedAt"]
        for page in source["sourcePages"]:
            page["checkedAt"] = source["sourceLastCheckedAt"]
        with self.assertRaisesRegex(FallbackError, "CANONICAL_SOURCE_TIME_CONFLICT"):
            prepare(record=source)

    def test_no_false_freshness_from_generated_timestamp(self):
        source = example()
        source["pack"]["generatedAt"] = "2026-11-01T05:55:00Z"
        source["freshnessHours"] = 0
        result = prepare(record=source)
        self.assertNotIn("freshnessHours", result)
        self.assertNotIn("generatedAt", result["pack"])


if __name__ == "__main__":
    unittest.main()
