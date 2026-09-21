"""Assumption-level source, rule-version and change history.

This module checks evidence bindings, not legal applicability or source authenticity.
A digest binds a human review to its inputs; it is not a signature or a review.
No network calls, source acquisition, customer messages or automatic approvals.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .model import Finding, canonical_json, parse_dt, sha256_hex, valid_sha256

VERSION = "1.0"
PROFILE = "ASSUMPTION_SOURCE_RULE_HISTORY_V1"
NAMESPACES = {"FAR", "DFARS", "AGENCY_SUPPLEMENT", "CLASS_DEVIATION", "SOLICITATION_RULE"}
ROLES = {"CONTROLLING", "SUPPORTING", "CONTRADICTING", "HISTORICAL"}
CHANGE_TYPES = {"AMENDS", "REPLACES", "CORRECTS", "WITHDRAWS"}
RESOLVED = {"SUPPORTED", "CONTRADICTED", "SUPERSEDED"}


def _rows(value: Any) -> list[dict]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _index(value: Any, key: str) -> dict[str, dict]:
    return {str(x[key]): x for x in _rows(value) if _text(x.get(key))}


def _https(value: Any) -> bool:
    try:
        p = urlsplit(value if isinstance(value, str) else "")
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def initialize_trace(case: dict, *, decision_at: str) -> dict:
    """Return a copy with pending trace work. Never overwrite an existing trace."""
    if "decision_trace" in case:
        raise ValueError("decision_trace already exists; preserve its history")
    if parse_dt(decision_at) is None:
        raise ValueError("decision_at must include a timezone")
    out = deepcopy(case)
    out["evidence_profile"] = PROFILE
    out["decision_trace"] = {
        "schema_version": VERSION, "decision_at": decision_at,
        "rule_versions": [], "source_changes": [],
        "assumption_traces": [{
            "assumption_id": a.get("assumption_id"), "citations": [],
            "rule_review": "UNRESOLVED", "rule_review_reason": "Rule dependencies not yet reviewed.",
            "rule_bindings": [], "history_review": "PENDING",
            "history_note": "Identify exact passages and documented changes before review.",
            "review": None,
        } for a in _rows(case.get("assumptions"))],
    }
    return out


def dependency_inputs(case: dict, assumption_id: str) -> dict:
    """Pin both predecessors and successors. A new amendment cannot evade the watch."""
    trace = case.get("decision_trace") if isinstance(case.get("decision_trace"), dict) else {}
    item = _index(case.get("assumptions"), "assumption_id").get(assumption_id, {})
    entry = _index(trace.get("assumption_traces"), "assumption_id").get(assumption_id, {})
    rules = _index(trace.get("rule_versions"), "rule_version_id")
    bound_rules = {str(b.get("rule_version_id")) for b in _rows(entry.get("rule_bindings"))}
    source_ids = {str(c.get("source_id")) for c in _rows(entry.get("citations"))}
    source_ids.update(s for s in (item.get("source_ids") if isinstance(item.get("source_ids"), list) else []) if isinstance(s, str))
    for binding in _rows(entry.get("rule_bindings")):
        for c in (binding.get("basis"), rules.get(str(binding.get("rule_version_id")), {}).get("citation")):
            if isinstance(c, dict) and c.get("source_id"):
                source_ids.add(str(c["source_id"]))
    changes = _rows(trace.get("source_changes"))
    relevant: dict[str, dict] = {}
    while True:
        prior = len(source_ids)
        for change in changes:
            ends = {str(change.get("predecessor_source_id")), str(change.get("successor_source_id"))}
            if ends & source_ids:
                relevant[str(change.get("change_id"))] = change
                source_ids.update(ends)
                c = change.get("evidence")
                if isinstance(c, dict) and c.get("source_id"):
                    source_ids.add(str(c["source_id"]))
        if len(source_ids) == prior:
            break
    sources = _index(case.get("sources"), "source_id")
    return {
        "profile": case.get("evidence_profile"), "trace_version": trace.get("schema_version"),
        "case_id": case.get("case_id"), "family_id": case.get("family_id"),
        "posture": case.get("current_posture"), "decision_at": trace.get("decision_at"),
        "assumption": item,
        "trace": {k: v for k, v in entry.items() if k != "review"},
        "sources": {sid: sources.get(sid) for sid in sorted(source_ids)},
        "rules": {rid: rules.get(rid) for rid in sorted(bound_rules)},
        "changes": {cid: relevant[cid] for cid in sorted(relevant)},
    }


def review_input_digest(case: dict, assumption_id: str) -> str:
    return sha256_hex(canonical_json(dependency_inputs(case, assumption_id)))


def validate_decision_trace(case: dict, *, now: datetime | None = None) -> list[Finding]:
    findings: list[Finding] = []

    def block(code: str, message: str, path: str = "decision_trace") -> None:
        findings.append(Finding("TRACE_" + code, "BLOCK", message, path))

    required = case.get("evidence_profile") == PROFILE
    if "decision_trace" not in case:
        if required:
            block("MISSING", "This evidence profile requires assumption-level history.")
        return findings  # Legacy cases remain legacy; the renderer explicitly labels them.
    trace = case["decision_trace"]
    if not isinstance(trace, dict):
        block("SHAPE", "decision_trace must be an object.")
        return findings
    if trace.get("schema_version") != VERSION:
        block("VERSION", "Unsupported decision trace version.")
    now = now or datetime.now(timezone.utc)
    decision_at = parse_dt(trace.get("decision_at"))
    if decision_at is None or decision_at > now:
        block("DECISION_TIME", "Decision as-of time must include a timezone and not be in the future.")

    def unique(value: Any, key: str, path: str) -> dict[str, dict]:
        rows = _rows(value)
        if not isinstance(value, list) or len(rows) != len(value):
            block("COLLECTION", "Expected an array of objects.", path)
        out = _index(value, key)
        if len(out) != len(rows):
            block("IDENTITY", f"Missing or duplicate {key}.", path)
        return out

    sources = unique(case.get("sources", []), "source_id", "sources")
    assumptions = unique(case.get("assumptions", []), "assumption_id", "assumptions")
    rules = unique(trace.get("rule_versions"), "rule_version_id", "decision_trace.rule_versions")
    changes = unique(trace.get("source_changes"), "change_id", "decision_trace.source_changes")
    entries = unique(trace.get("assumption_traces"), "assumption_id", "decision_trace.assumption_traces")
    if not assumptions or set(entries) != set(assumptions):
        block("COVERAGE", "Every assumption needs exactly one trace, with no orphan traces.")

    def citation(c: Any, path: str) -> dict:
        if not isinstance(c, dict):
            block("CITATION", "Missing exact source citation.", path)
            return {}
        s = sources.get(str(c.get("source_id")))
        if s is None:
            block("SOURCE_MISSING", "Citation source is not retained in the source manifest.", path)
            return {}
        if not valid_sha256(c.get("content_sha256")) or c.get("content_sha256") != s.get("content_sha256"):
            block("SOURCE_HASH", "Citation does not match the retained source content hash.", path)
        if not _text(c.get("locator")) or not _text(c.get("quote")):
            block("EXACT_PASSAGE", "A page/section/paragraph locator and exact passage are required.", path)
        if not _text(s.get("version_label")) or not _https(s.get("url")):
            block("SOURCE_VERSION", "Cited source needs a version label and HTTPS source URL.", path)
        observed = parse_dt(s.get("observed_at"))
        if observed is None or (decision_at is not None and observed > decision_at):
            block("SOURCE_TIME", "Source observation is missing or later than the decision snapshot.", path)
        if s.get("artifact_state") != "PUBLIC" or s.get("authority") == "SOURCE_LIMITED_RESTRICTED":
            block("SOURCE_LIMITED", "Unavailable/restricted material cannot supply a verified passage.", path)
        # When a text snapshot is present, validate actual membership as well as the binding.
        if "text_snapshot" in s:
            text = s["text_snapshot"]
            if not isinstance(text, str) or sha256_hex(text) != s.get("text_sha256"):
                block("TEXT_HASH", "Text snapshot digest does not match retained text.", path)
            elif not _text(c.get("quote")) or c["quote"] not in text:
                block("QUOTE_MISMATCH", "Quoted passage is absent from the supplied text snapshot.", path)
        return s

    for rid, rule in rules.items():
        path = f"decision_trace.rule_versions[{rid}]"
        if str(rule.get("namespace")) not in NAMESPACES or any(not _text(rule.get(k)) for k in ("rule_id", "version_label", "alternate")):
            block("RULE_VERSION", "Rule identity requires namespace, citation, dated/version label and explicit alternate.", path)
        if rule.get("namespace") == "CLASS_DEVIATION" and not _text(rule.get("deviation_id")):
            block("DEVIATION_ID", "Class deviations require their own identifier.", path)
        if rule.get("effective_date") is not None:
            try:
                date.fromisoformat(rule["effective_date"])
            except (TypeError, ValueError):
                block("RULE_DATE", "effective_date must be YYYY-MM-DD or null; do not invent a day.", path)
        citation(rule.get("citation"), path)

    graph: dict[str, set[str]] = {}
    for cid, change in changes.items():
        path = f"decision_trace.source_changes[{cid}]"
        pred, succ = change.get("predecessor_source_id"), change.get("successor_source_id")
        if not _text(pred) or not _text(succ) or pred not in sources or succ not in sources or pred == succ:
            block("CHANGE_ENDPOINT", "Changes must link two distinct retained source versions.", path)
        else:
            graph.setdefault(pred, set()).add(succ)
        if str(change.get("change_type")) not in CHANGE_TYPES or not _text(change.get("scope")) or not _text(change.get("explanation")):
            block("CHANGE_SCOPE", "Each change needs type, exact affected scope and explanation.", path)
        citation(change.get("evidence"), path)
        recorded = parse_dt(change.get("recorded_at"))
        if recorded is None or (decision_at is not None and recorded > decision_at):
            block("CHANGE_TIME", "Change observation must not postdate the decision snapshot.", path)
    # Iterative topological check avoids recursion limits on large amendment chains.
    nodes = set(graph) | {s for children in graph.values() for s in children}
    incoming = {n: 0 for n in nodes}
    for children in graph.values():
        for n in children:
            incoming[n] += 1
    ready = [n for n in nodes if incoming[n] == 0]
    visited = 0
    while ready:
        n = ready.pop(); visited += 1
        for child in graph.get(n, set()):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        block("CHANGE_CYCLE", "Source amendment/supersession history contains a cycle.")

    for aid, entry in entries.items():
        path = f"decision_trace.assumption_traces[{aid}]"
        item = assumptions.get(aid, {})
        resolved = str(item.get("evidence_state")) in RESOLVED
        citations = _rows(entry.get("citations"))
        if not isinstance(entry.get("citations"), list) or len(citations) != len(entry.get("citations", [])):
            block("CITATION_SHAPE", "citations must be an array of objects.", path)
        controlling = False
        for c in citations:
            s = citation(c, path)
            if str(c.get("role")) not in ROLES:
                block("CITATION_ROLE", "Specify controlling, contradicting, supporting or historical evidence.", path)
            if c.get("source_id") not in (item.get("source_ids") or []):
                block("UNLINKED_SOURCE", "Trace passage is not linked to the assumption source IDs.", path)
            if str(c.get("role")) in {"CONTROLLING", "CONTRADICTING"} and s.get("authority") == "CONTROLLING_CURRENT":
                controlling = True
        if resolved and not controlling:
            block("CONTROLLING_PASSAGE", "Resolved assumptions need a passage from controlling current evidence.", path)
        review_state = str(entry.get("rule_review"))
        bindings = _rows(entry.get("rule_bindings"))
        if not isinstance(entry.get("rule_bindings"), list) or len(bindings) != len(entry.get("rule_bindings", [])):
            block("BINDING_SHAPE", "rule_bindings must be an array of objects.", path)
        if review_state not in {"LINKED", "NOT_RULE_DEPENDENT", "UNRESOLVED"} or not _text(entry.get("rule_review_reason")):
            block("RULE_REVIEW", "Record the rule dependency review and its reason.", path)
        if (review_state == "LINKED" and not bindings) or (review_state == "NOT_RULE_DEPENDENT" and bindings):
            block("RULE_COVERAGE", "Rule-review state conflicts with the rule bindings.", path)
        if resolved and review_state == "UNRESOLVED":
            block("RULE_UNRESOLVED", "Unresolved rule dependence cannot support a resolved conclusion.", path)
        seen_bindings = set()
        for binding in bindings:
            raw_rid = binding.get("rule_version_id")
            rid = raw_rid if isinstance(raw_rid, str) else ""
            if not _text(rid) or rid not in rules or rid in seen_bindings:
                block("RULE_BINDING", "Unknown or duplicate rule-version binding.", path)
            if _text(rid):
                seen_bindings.add(rid)
            status = str(binding.get("status"))
            if status not in {"APPLIES", "DOES_NOT_APPLY", "UNRESOLVED"} or not _text(binding.get("reason")):
                block("APPLICABILITY", "Rule applicability must be explicit with a reason.", path)
            if status in {"APPLIES", "DOES_NOT_APPLY"}:
                basis = citation(binding.get("basis"), path)
                if basis.get("authority") != "CONTROLLING_CURRENT":
                    block("APPLICABILITY_BASIS", "Applicability must cite controlling pursuit evidence, not publication recency.", path)
            elif resolved:
                block("APPLICABILITY_UNRESOLVED", "Rule applicability is unresolved; retain VERIFY_NOW rather than a resolved conclusion.", path)
        history = str(entry.get("history_review"))
        if history not in {"REVIEWED", "SOURCE_LIMITED"} or not _text(entry.get("history_note")):
            block("HISTORY_REVIEW", "Review the retained version chain and document remaining limits.", path)
        if resolved and history != "REVIEWED":
            block("HISTORY_LIMITED", "Source-limited history cannot prove a resolved assumption.", path)
        for sid, s in dependency_inputs(case, aid)["sources"].items():
            s = s or {}
            if not valid_sha256(s.get("content_sha256")) or not _text(s.get("version_label")) or not _https(s.get("url")):
                block("HISTORY_SOURCE_VERSION", f"Retained history source {sid} lacks exact version/hash/URL evidence.", path)
            observed = parse_dt(s.get("observed_at"))
            if observed is None or (decision_at is not None and observed > decision_at):
                block("HISTORY_SOURCE_TIME", f"Retained history source {sid} is missing an admissible observation time.", path)
            if resolved and (s.get("artifact_state") != "PUBLIC" or s.get("authority") == "SOURCE_LIMITED_RESTRICTED"):
                block("HISTORY_SOURCE_LIMITED", f"Retained history source {sid} cannot support a complete resolved history.", path)
        review = entry.get("review") if isinstance(entry.get("review"), dict) else {}
        reviewed = parse_dt(review.get("reviewed_at"))
        if review.get("kind") != "HUMAN_REVIEW" or not _text(review.get("reviewer")) or reviewed is None or reviewed > now or (decision_at is not None and reviewed < decision_at):
            block("HUMAN_REVIEW", "A named, dated human review of this decision snapshot is required.", path)
        if review.get("input_sha256") != review_input_digest(case, aid):
            block("STALE_REVIEW", "Evidence or decision inputs differ from the reviewed snapshot.", path)
    return findings


def trace_change_impact(before: dict, after: dict) -> dict:
    """Compare both sides of dependency bindings; removed links do not hide changes."""
    if "decision_trace" not in before and "decision_trace" not in after:
        return {"events": [], "reopened_assumptions": []}
    ids = set(_index(before.get("assumptions"), "assumption_id")) | set(_index(after.get("assumptions"), "assumption_id"))
    events, reopened = [], []
    for aid in sorted(ids):
        b, a = dependency_inputs(before, aid), dependency_inputs(after, aid)
        # An observation clock alone does not establish a material source/rule change.
        b.pop("decision_at", None); a.pop("decision_at", None)
        changed = [k for k in sorted(set(b) | set(a)) if b.get(k) != a.get(k)]
        if changed:
            key = f"DECISION_TRACE:{aid}"
            events.append({"type": "ASSUMPTION_DEPENDENCIES_CHANGED", "key": key, "assumption_id": aid, "changed_planes": changed})
            reopened.append({"assumption_id": aid, "matched_triggers": [key], "requires_human_review": True})
    return {"events": events, "reopened_assumptions": reopened}


def render_trace_markdown(case: dict) -> str:
    """Buyer-readable history, with machine integrity separated from reviewer judgement."""
    def e(value: Any) -> str:
        return escape(str(value if value is not None else "Not established")).replace("|", "\\|").replace("\n", " ")

    trace = case.get("decision_trace")
    if not isinstance(trace, dict):
        return "## Assumption source / rule / version history\n\nNot collected for this legacy case. No exact-history claim is made.\n"
    lines = ["## Assumption source / rule / version history", "", f"Decision snapshot: {e(trace.get('decision_at'))}", ""]
    for aid, entry in _index(trace.get("assumption_traces"), "assumption_id").items():
        inputs = dependency_inputs(case, aid)
        item = inputs["assumption"]
        lines += [f"### {e(aid)} — {e(item.get('text'))}", f"**Conclusion:** {e(item.get('evidence_state'))} / {e(item.get('decision_class'))}", f"**History review:** {e(entry.get('history_review'))} — {e(entry.get('history_note'))}"]
        for c in _rows(entry.get("citations")):
            s = inputs["sources"].get(str(c.get("source_id"))) or {}
            lines += [f"**{e(c.get('role'))}:** {e(s.get('title') or c.get('source_id'))} · {e(s.get('version_label'))} · {e(c.get('locator'))}", f"> {e(c.get('quote'))}", f"Source: {e(s.get('url'))} · SHA-256: `{e(c.get('content_sha256'))}`"]
        lines += [f"**Rule dependency review:** {e(entry.get('rule_review'))} — {e(entry.get('rule_review_reason'))}"]
        for b in _rows(entry.get("rule_bindings")):
            rule = inputs["rules"].get(str(b.get("rule_version_id"))) or {}
            c = rule.get("citation") or {}; s = inputs["sources"].get(str(c.get("source_id"))) or {}
            basis = b.get("basis") or {}
            lines += [f"**Rule:** {e(rule.get('namespace'))} {e(rule.get('rule_id'))} · {e(rule.get('version_label'))} · {e(rule.get('alternate'))} · deviation {e(rule.get('deviation_id'))}", f"Effective date: {e(rule.get('effective_date'))}. **Applicability:** {e(b.get('status'))} — {e(b.get('reason'))}", f"Rule passage: {e(c.get('locator'))} — {e(c.get('quote'))}", f"Rule source: {e(s.get('url'))} · SHA-256: `{e(c.get('content_sha256'))}`", f"Pursuit-specific basis: {e(basis.get('source_id'))} · {e(basis.get('locator'))} — {e(basis.get('quote'))}"]
        for change in inputs["changes"].values():
            c = change.get("evidence") or {}
            lines += [f"**{e(change.get('change_type'))}:** {e(change.get('predecessor_source_id'))} → {e(change.get('successor_source_id'))} · {e(change.get('scope'))}", e(change.get("explanation")), f"Change evidence: {e(c.get('source_id'))} · {e(c.get('locator'))} — {e(c.get('quote'))}"]
        lines += ["", "| Retained source version | Authority | Observed | SHA-256 |", "|---|---|---|---|"]
        for sid, s in inputs["sources"].items():
            s = s or {}
            lines.append(f"| {e(sid)} · {e(s.get('version_label'))} | {e(s.get('authority'))} | {e(s.get('observed_at'))} | {e(s.get('content_sha256'))} |")
        review = entry.get("review") if isinstance(entry.get("review"), dict) else {}
        lines += ["", f"**Reviewed by:** {e(review.get('reviewer'))} · {e(review.get('reviewed_at'))}", f"**Review input fingerprint:** `{review_input_digest(case, aid)}`", f"**Next action:** {e(item.get('next_action'))} · **Owner / request:** {e(item.get('owner') or item.get('evidence_request'))}", "Changes to these dependencies reopen this assumption for review; they do not automatically change the bid decision.", ""]
    lines += ["A source hash binds the retained bytes; it does not authenticate the publisher or prove legal applicability. Exact-passage accuracy remains human-reviewed unless a matching text snapshot is supplied. Packet completeness and current-action authority still pass the existing independent release checks.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["initialize", "validate", "render", "review-input"])
    parser.add_argument("case")
    parser.add_argument("--decision-at")
    parser.add_argument("--assumption-id")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()
    try:
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        if not isinstance(case, dict):
            raise ValueError("case must be a JSON object")
        if args.command == "initialize":
            result: Any = initialize_trace(case, decision_at=args.decision_at or "")
        elif args.command == "review-input":
            if args.assumption_id not in _index(case.get("assumptions"), "assumption_id"):
                raise ValueError("--assumption-id must identify an existing assumption")
            result = {"assumption_id": args.assumption_id, "input_sha256": review_input_digest(case, args.assumption_id), "review_performed": False}
        elif args.command == "render":
            result = render_trace_markdown(case)
        else:
            findings = validate_decision_trace(case)
            collected = isinstance(case.get("decision_trace"), dict)
            result = {"state": "FAIL_CLOSED" if findings else ("TRACE_REVIEWED" if collected else "NOT_COLLECTED"), "findings": [asdict(f) for f in findings], "case_release_authorized": False}
        text = result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)
        return 2 if args.command == "validate" and result["state"] != "TRACE_REVIEWED" else 0
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"decision-trace: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
