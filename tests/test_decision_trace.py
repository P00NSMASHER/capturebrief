"""Synthetic source text only. These fixtures are not actual government rules."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from capturebrief_core.decision_trace import (
    PROFILE, dependency_inputs, initialize_trace, render_trace_markdown,
    review_input_digest, trace_change_impact, validate_decision_trace,
)
from capturebrief_core.model import sha256_hex

NOW = datetime(2026, 9, 21, 17, tzinfo=timezone.utc)


def source(sid, version, text, authority="CONTROLLING_CURRENT"):
    return {
        "source_id": sid, "title": "SYNTHETIC " + sid,
        "url": "https://example.invalid/synthetic/" + sid,
        "version_label": version, "artifact_state": "PUBLIC", "authority": authority,
        "observed_at": "2026-09-21T14:00:00+00:00",
        "content_sha256": sha256_hex(text), "text_snapshot": text,
        "text_sha256": sha256_hex(text),
    }


def cite(s, quote=None, **extra):
    return {"source_id": s["source_id"], "content_sha256": s["content_sha256"],
            "locator": "Section L, paragraph 2", "quote": quote or s["text_snapshot"], **extra}


def approve(case, aid="A1"):
    entry = next(e for e in case["decision_trace"]["assumption_traces"] if e["assumption_id"] == aid)
    entry["review"] = {"kind": "HUMAN_REVIEW", "reviewer": "Synthetic reviewer; NOT actual approval",
                       "reviewed_at": "2026-09-21T16:00:00+00:00", "input_sha256": review_input_digest(case, aid)}


def example():
    old = source("S1", "Original issue", "Submit two project examples.", "HISTORICAL_SUPERSEDED")
    current = source("S2", "Amendment 0002", "Replace Section L.2: Submit three project examples. Apply DEMO-01 (June 2025), Basic.")
    rule = source("R1", "June 2025", "SYNTHETIC RULE: Three project examples are required.", "SUPPORTING")
    case = {"case_schema_version": "0.2", "case_id": "DEMO-TRACE", "family_id": "SYNTHETIC-NOT-A-SOLICITATION",
            "current_posture": "HOLD", "sources": [old, current, rule],
            "assumptions": [{"assumption_id": "A1", "text": "Two project examples are sufficient.",
                             "evidence_state": "CONTRADICTED", "decision_class": "GATE_CHANGING",
                             "source_ids": ["S2"], "next_action": "Confirm a third eligible example before proposal kickoff.",
                             "owner": "Capture lead"}]}
    case = initialize_trace(case, decision_at="2026-09-21T15:00:00+00:00")
    trace = case["decision_trace"]
    trace["rule_versions"] = [{"rule_version_id": "DEMO-01:2025-06:BASIC", "namespace": "SOLICITATION_RULE",
        "rule_id": "DEMO-01", "version_label": "June 2025", "alternate": "BASIC", "deviation_id": None,
        "effective_date": None, "citation": cite(rule)}]
    trace["source_changes"] = [{"change_id": "CHANGE-2", "predecessor_source_id": "S1", "successor_source_id": "S2",
        "change_type": "REPLACES", "scope": "Section L.2 only", "explanation": "Two examples changed to three; unrelated requirements not decided.",
        "evidence": cite(current), "recorded_at": "2026-09-21T14:00:00+00:00"}]
    entry = trace["assumption_traces"][0]
    entry.update(citations=[cite(current, role="CONTROLLING")], rule_review="LINKED",
                 rule_review_reason="The amended instructions expressly incorporate the named version.",
                 rule_bindings=[{"rule_version_id": "DEMO-01:2025-06:BASIC", "status": "APPLIES",
                                 "reason": "Express incorporation in the amended instructions, not latest publication date.", "basis": cite(current)}],
                 history_review="REVIEWED", history_note="Original and amended passages retained; packet gates are independently required.")
    approve(case)
    return case


class DecisionTraceTests(unittest.TestCase):
    def codes(self, case):
        return {f.code for f in validate_decision_trace(case, now=NOW)}

    def test_reviewed_trace(self):
        self.assertEqual(set(), self.codes(example()))

    def test_initializer_has_no_approval(self):
        c = example(); del c["decision_trace"]
        c = initialize_trace(c, decision_at="2026-09-21T15:00:00Z")
        self.assertEqual(PROFILE, c["evidence_profile"])
        self.assertIsNone(c["decision_trace"]["assumption_traces"][0]["review"])
        self.assertIn("TRACE_HUMAN_REVIEW", self.codes(c))

    def test_initializer_preserves_original(self):
        c = {"sources": [], "assumptions": []}; original = deepcopy(c)
        initialize_trace(c, decision_at="2026-09-21T15:00:00Z")
        self.assertEqual(c, original)

    def test_no_overwrite_existing_history(self):
        with self.assertRaises(ValueError):
            initialize_trace(example(), decision_at="2026-09-21T15:00:00Z")

    def test_legacy_not_promoted(self):
        c = {"case_id": "legacy"}
        self.assertEqual([], validate_decision_trace(c))
        self.assertIn("No exact-history claim", render_trace_markdown(c))

    def test_profile_cannot_drop_trace(self):
        c = example(); del c["decision_trace"]
        self.assertIn("TRACE_MISSING", self.codes(c))

    def test_hash_mutation_invalidates_review(self):
        c = example(); c["sources"][1]["content_sha256"] = "a" * 64
        self.assertTrue({"TRACE_SOURCE_HASH", "TRACE_STALE_REVIEW"} <= self.codes(c))

    def test_quote_must_match_text(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["citations"][0]["quote"] = "Not present in source."
        approve(c)
        self.assertIn("TRACE_QUOTE_MISMATCH", self.codes(c))

    def test_bad_text_digest(self):
        c = example(); c["sources"][1]["text_sha256"] = "b" * 64; approve(c)
        self.assertIn("TRACE_TEXT_HASH", self.codes(c))

    def test_missing_locator(self):
        c = example(); del c["decision_trace"]["assumption_traces"][0]["citations"][0]["locator"]
        self.assertIn("TRACE_EXACT_PASSAGE", self.codes(c))

    def test_missing_source(self):
        c = example(); c["sources"] = c["sources"][:1]
        self.assertIn("TRACE_SOURCE_MISSING", self.codes(c))

    def test_source_ids_bound(self):
        c = example(); c["assumptions"][0]["source_ids"] = []; approve(c)
        self.assertIn("TRACE_UNLINKED_SOURCE", self.codes(c))

    def test_restricted_source_not_evidence(self):
        c = example(); c["sources"][1]["artifact_state"] = "RESTRICTED"; approve(c)
        self.assertIn("TRACE_SOURCE_LIMITED", self.codes(c))

    def test_historical_source_not_controlling(self):
        c = example(); c["sources"][1]["authority"] = "HISTORICAL_SUPERSEDED"; approve(c)
        self.assertIn("TRACE_CONTROLLING_PASSAGE", self.codes(c))

    def test_source_version_required(self):
        c = example(); del c["sources"][1]["version_label"]; approve(c)
        self.assertIn("TRACE_SOURCE_VERSION", self.codes(c))

    def test_rule_date_is_not_commit_date(self):
        c = example(); rule = c["decision_trace"]["rule_versions"][0]
        del rule["version_label"]; rule["git_commit_date"] = "2026-09-21"; approve(c)
        self.assertIn("TRACE_RULE_VERSION", self.codes(c))

    def test_rule_not_auto_selected_by_recency(self):
        c = example(); new_rule = deepcopy(c["decision_trace"]["rule_versions"][0])
        new_rule.update(rule_version_id="DEMO-01:2026-09:BASIC", version_label="September 2026")
        c["decision_trace"]["rule_versions"].append(new_rule)
        self.assertEqual(set(), self.codes(c))
        self.assertEqual([], trace_change_impact(example(), c)["reopened_assumptions"])

    def test_rule_requires_pursuit_basis(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["rule_bindings"][0]["basis"] = cite(c["sources"][2]); approve(c)
        self.assertIn("TRACE_APPLICABILITY_BASIS", self.codes(c))

    def test_unknown_applicability_stays_unknown(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["rule_bindings"][0]["status"] = "UNRESOLVED"; approve(c)
        self.assertIn("TRACE_APPLICABILITY_UNRESOLVED", self.codes(c))

    def test_not_rule_dependent_is_explicit(self):
        c = example(); entry = c["decision_trace"]["assumption_traces"][0]
        entry.update(rule_review="NOT_RULE_DEPENDENT", rule_bindings=[], rule_review_reason="Only an express solicitation instruction is being tested.")
        approve(c)
        self.assertEqual(set(), self.codes(c))

    def test_deviation_identity_required(self):
        c = example(); c["decision_trace"]["rule_versions"][0]["namespace"] = "CLASS_DEVIATION"; approve(c)
        self.assertIn("TRACE_DEVIATION_ID", self.codes(c))

    def test_no_day_invented_for_month_version(self):
        c = example(); c["decision_trace"]["rule_versions"][0]["effective_date"] = "2025-06"; approve(c)
        self.assertIn("TRACE_RULE_DATE", self.codes(c))

    def test_duplicate_source_identity(self):
        c = example(); c["sources"].append(deepcopy(c["sources"][1]))
        self.assertIn("TRACE_IDENTITY", self.codes(c))

    def test_duplicate_trace_identity(self):
        c = example(); c["decision_trace"]["assumption_traces"].append(deepcopy(c["decision_trace"]["assumption_traces"][0]))
        self.assertIn("TRACE_IDENTITY", self.codes(c))

    def test_missing_assumption_trace(self):
        c = example(); c["decision_trace"]["assumption_traces"] = []
        self.assertIn("TRACE_COVERAGE", self.codes(c))

    def test_change_cycle(self):
        c = example(); edge = deepcopy(c["decision_trace"]["source_changes"][0])
        edge.update(change_id="CYCLE", predecessor_source_id="S2", successor_source_id="S1")
        c["decision_trace"]["source_changes"].append(edge); approve(c)
        self.assertIn("TRACE_CHANGE_CYCLE", self.codes(c))

    def test_unproven_change_endpoint(self):
        c = example(); c["decision_trace"]["source_changes"][0]["predecessor_source_id"] = "LOST"; approve(c)
        self.assertIn("TRACE_CHANGE_ENDPOINT", self.codes(c))

    def test_future_evidence_blocks_historical_decision(self):
        c = example(); c["sources"][1]["observed_at"] = "2026-09-21T15:30:00Z"; approve(c)
        self.assertIn("TRACE_SOURCE_TIME", self.codes(c))

    def test_naive_decision_time(self):
        c = example(); c["decision_trace"]["decision_at"] = "2026-09-21T15:00:00"; approve(c)
        self.assertIn("TRACE_DECISION_TIME", self.codes(c))

    def test_future_review_blocked(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["review"]["reviewed_at"] = "2027-01-01T00:00:00Z"
        self.assertIn("TRACE_HUMAN_REVIEW", self.codes(c))

    def test_review_digest_does_not_approve(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["review"] = {"input_sha256": review_input_digest(c, "A1")}
        self.assertIn("TRACE_HUMAN_REVIEW", self.codes(c))

    def test_reviewed_with_limits_not_resolved(self):
        c = example(); c["decision_trace"]["assumption_traces"][0]["history_review"] = "SOURCE_LIMITED"; approve(c)
        self.assertIn("TRACE_HISTORY_LIMITED", self.codes(c))
        c["assumptions"][0].update(evidence_state="UNPROVEN", decision_class="VERIFY_NOW"); approve(c)
        self.assertEqual(set(), self.codes(c))

    def test_bound_rule_change_reopens(self):
        b = example(); a = deepcopy(b)
        a["decision_trace"]["rule_versions"][0]["version_label"] = "September 2026"
        impact = trace_change_impact(b, a)
        self.assertEqual(["A1"], [x["assumption_id"] for x in impact["reopened_assumptions"]])
        self.assertIn("TRACE_STALE_REVIEW", self.codes(a))

    def test_new_successor_reopens_original_dependency(self):
        b = example(); a = deepcopy(b); newer = source("S3", "Amendment 0003", "Revise examples to four.")
        a["sources"].append(newer)
        a["decision_trace"]["source_changes"].append({"change_id": "CHANGE-3", "predecessor_source_id": "S2", "successor_source_id": "S3", "change_type": "AMENDS", "scope": "L.2", "explanation": "Now four", "evidence": cite(newer), "recorded_at": "2026-09-21T14:00:00Z"})
        self.assertEqual(1, len(trace_change_impact(b, a)["reopened_assumptions"]))
        self.assertIn("S3", dependency_inputs(a, "A1")["sources"])

    def test_unrelated_source_does_not_reopen(self):
        b = example(); a = deepcopy(b); a["sources"].append(source("UNRELATED", "v2", "Unrelated document"))
        self.assertEqual([], trace_change_impact(b, a)["reopened_assumptions"])
        self.assertEqual(review_input_digest(b, "A1"), review_input_digest(a, "A1"))

    def test_dropped_dependency_cannot_hide_change(self):
        b = example(); a = deepcopy(b)
        a["decision_trace"]["assumption_traces"][0]["rule_bindings"] = []
        self.assertEqual(1, len(trace_change_impact(b, a)["reopened_assumptions"]))

    def test_prior_state_not_modified(self):
        b = example(); a = deepcopy(b); original = deepcopy(b)
        a["sources"][1]["content_sha256"] = "f" * 64
        trace_change_impact(b, a)
        self.assertEqual(original, b)

    def test_render_exact_history_and_boundary(self):
        text = render_trace_markdown(example())
        for expected in ["Section L, paragraph 2", "June 2025", "S1", "S2", "REPLACES", "SHA-256", "APPLIES", "Three project examples", "does not authenticate", "Capture lead"]:
            self.assertIn(expected, text)

    def test_malformed_collections_block(self):
        for name in ["rule_versions", "source_changes", "assumption_traces"]:
            c = example(); c["decision_trace"][name] = "invalid"
            with self.subTest(name=name):
                self.assertIn("TRACE_COLLECTION", self.codes(c))

    def test_unsafe_source_link_blocks(self):
        c = example(); c["sources"][1]["url"] = "javascript:alert(1)"; approve(c)
        self.assertIn("TRACE_SOURCE_VERSION", self.codes(c))

    def test_predecessor_hash_is_required(self):
        c = example(); del c["sources"][0]["content_sha256"]; approve(c)
        self.assertIn("TRACE_HISTORY_SOURCE_VERSION", self.codes(c))

    def test_unavailable_predecessor_cannot_prove_complete_history(self):
        c = example(); c["sources"][0]["artifact_state"] = "UNAVAILABLE"; approve(c)
        self.assertIn("TRACE_HISTORY_SOURCE_LIMITED", self.codes(c))

    def test_cli_review_input_not_an_approval(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "case.json"; path.write_text(json.dumps(example()))
            proc = subprocess.run([sys.executable, "-m", "capturebrief_core.decision_trace", "review-input", str(path), "--assumption-id", "A1"], capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertIs(False, json.loads(proc.stdout)["review_performed"])


if __name__ == "__main__":
    unittest.main()
