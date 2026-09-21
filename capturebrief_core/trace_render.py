from __future__ import annotations
import html
from typing import Any
from .decision_trace import evaluate_decision_trace


def render_trace_markdown(case: dict[str, Any]) -> str:
    report = evaluate_decision_trace(case)
    lines = ["## Decision evidence", "", "**Exact source / rule / version history behind the assumptions used in this pursuit.**", "",
             f"Trace state: **{report['trace_state']}**", ""]
    for card in report["assumptions"]:
        lines += [f"### {card['assumption_id']} — {card.get('evidence_state')}",
                  f"**Assumption:** {card.get('assumption') or ''}",
                  f"**Finding:** {card.get('finding') or ''}"]
        if card.get("next_action"): lines.append(f"**Next action:** {card['next_action']}")
        lines.append("")
        for cite in card.get("citations") or []:
            src = cite.get("source") or {}
            lines += [f"- **{src.get('title') or src.get('source_id')} — {src.get('version_label') or 'version not labeled'}**",
                      f"  - Locator: {cite.get('locator')}", f"  - Exact passage: “{str(cite.get('quote') or '').replace(chr(10), ' / ')}”",
                      f"  - Document SHA-256: `{src.get('document_sha256') or ''}`"]
        for rule in card.get("rule_links") or []:
            lines.append(
                f"- Rule review: **{rule.get('namespace')} {rule.get('citation')} — "
                f"{rule.get('edition')}** → {rule.get('applicability')}"
            )
            lines.append(
                f"  - Applicability basis: {rule.get('basis') or 'not recorded'}"
            )
            if rule.get("incorporated_edition"):
                lines.append(
                    f"  - Incorporated edition: {rule.get('incorporated_edition')}"
                )
            lines.append(f"  - Reviewer rationale: {rule.get('rationale') or ''}")
            if rule.get("reviewed_by") or rule.get("reviewed_at"):
                lines.append(
                    f"  - Reviewed by: {rule.get('reviewed_by') or 'unknown'}"
                    f" · {rule.get('reviewed_at') or 'time not recorded'}"
                )
            basis_passage = rule.get("basis_passage")
            if isinstance(basis_passage, dict):
                lines.append(
                    f"  - Pursuit-specific basis: {basis_passage.get('locator') or ''}"
                )
                lines.append(
                    f"  - Exact basis passage: “"
                    f"{str(basis_passage.get('quote') or '').replace(chr(10), ' / ')}”"
                )
        for change in card.get("changes") or []:
            lines.append(f"- Version change: **{change.get('relation')}** — {change.get('summary')}")
            before=change.get("from_source") or {}
            after=change.get("to_source") or {}
            if before:
                lines.append(
                    f"  - Before: **{before.get('title') or before.get('source_id')} — "
                    f"{before.get('version_label') or 'version not labeled'}**"
                )
                if change.get("from_passage"):
                    lines.append(f"    - Locator: {change['from_passage'].get('locator') or ''}")
                    lines.append(
                        f"    - Exact passage: “{str(change['from_passage'].get('quote') or '').replace(chr(10), ' / ')}”"
                    )
                lines.append(f"    - Document SHA-256: `{before.get('document_sha256') or ''}`")
            if after:
                lines.append(
                    f"  - After: **{after.get('title') or after.get('source_id')} — "
                    f"{after.get('version_label') or 'version not labeled'}**"
                )
                if change.get("to_passage"):
                    lines.append(f"    - Locator: {change['to_passage'].get('locator') or ''}")
                    lines.append(
                        f"    - Exact passage: “{str(change['to_passage'].get('quote') or '').replace(chr(10), ' / ')}”"
                    )
                lines.append(f"    - Document SHA-256: `{after.get('document_sha256') or ''}`")
        lines.append("")
    if report["findings"]:
        lines += ["### Trace review gaps", ""] + [f"- **{x['code']}**: {x['message']}" for x in report["findings"]]
    lines += ["", "_This evidence trail supports human pursuit QA. It does not make the bid decision or automatically decide legal applicability._"]
    return "\n".join(lines)


def render_trace_html(case: dict[str, Any]) -> str:
    report = evaluate_decision_trace(case)
    cards = []
    for card in report["assumptions"]:
        evidence = []
        for cite in card.get("citations") or []:
            src = cite.get("source") or {}
            evidence.append(f"<li><strong>{html.escape(str(src.get('title') or src.get('source_id') or 'Source'))}</strong> · {html.escape(str(src.get('version_label') or 'version unlabeled'))}<br><span>{html.escape(str(cite.get('locator') or ''))}</span><blockquote>{html.escape(str(cite.get('quote') or ''))}</blockquote></li>")
        rule_items = []
        for rule in card.get("rule_links") or []:
            basis_passage = rule.get("basis_passage")
            basis_html = ""
            if isinstance(basis_passage, dict):
                basis_html = (
                    "<br><span><strong>Pursuit-specific basis:</strong> "
                    + html.escape(str(basis_passage.get("locator") or ""))
                    + "</span><blockquote>"
                    + html.escape(str(basis_passage.get("quote") or ""))
                    + "</blockquote>"
                )
            incorporated = (
                "<br><span><strong>Incorporated edition:</strong> "
                + html.escape(str(rule.get("incorporated_edition")))
                + "</span>"
                if rule.get("incorporated_edition")
                else ""
            )
            reviewer = ""
            if rule.get("reviewed_by") or rule.get("reviewed_at"):
                reviewer = (
                    "<br><span><strong>Reviewed by:</strong> "
                    + html.escape(str(rule.get("reviewed_by") or "unknown"))
                    + " · "
                    + html.escape(str(rule.get("reviewed_at") or "time not recorded"))
                    + "</span>"
                )
            rule_items.append(
                "<li><strong>"
                + html.escape(str(rule.get("namespace") or ""))
                + " "
                + html.escape(str(rule.get("citation") or ""))
                + " · "
                + html.escape(str(rule.get("edition") or ""))
                + "</strong> — "
                + html.escape(str(rule.get("applicability") or ""))
                + "<br><span><strong>Basis:</strong> "
                + html.escape(str(rule.get("basis") or "not recorded"))
                + "</span>"
                + incorporated
                + "<br>"
                + html.escape(str(rule.get("rationale") or ""))
                + reviewer
                + basis_html
                + "</li>"
            )
        rules = "".join(rule_items)
        change_items=[]
        for c in card.get("changes") or []:
            before=c.get("from_source") or {}
            after=c.get("to_source") or {}
            def version_block(label,meta,passage_value):
                if not meta:
                    return ""
                passage_html=""
                if isinstance(passage_value,dict):
                    passage_html=(
                        "<div class='delta-locator'>"+html.escape(str(passage_value.get("locator") or ""))+"</div>"
                        "<blockquote>"+html.escape(str(passage_value.get("quote") or ""))+"</blockquote>"
                    )
                return (
                    "<div class='delta-side'><span class='delta-label'>"+label+"</span>"
                    "<strong>"+html.escape(str(meta.get("title") or meta.get("source_id") or "Source"))+"</strong>"
                    "<span>"+html.escape(str(meta.get("version_label") or "version not labeled"))+"</span>"
                    +passage_html+
                    "<code>"+html.escape(str(meta.get("document_sha256") or ""))+"</code></div>"
                )
            change_items.append(
                "<li class='version-change'><strong>"
                +html.escape(str(c.get("relation") or ""))
                +"</strong> — "
                +html.escape(str(c.get("summary") or ""))
                +"<div class='version-grid'>"
                +version_block("BEFORE",before,c.get("from_passage"))
                +version_block("AFTER",after,c.get("to_passage"))
                +"</div></li>"
            )
        changes="".join(change_items)
        cards.append(f"<article><div class='eyebrow'>{html.escape(str(card.get('assumption_id')))} · {html.escape(str(card.get('evidence_state')))}</div><h2>{html.escape(str(card.get('assumption') or ''))}</h2><p class='finding'>{html.escape(str(card.get('finding') or ''))}</p><p><strong>Next:</strong> {html.escape(str(card.get('next_action') or card.get('evidence_request') or 'Human review'))}</p><details><summary>Inspect the evidence trail</summary><h3>Exact passages</h3><ul>{''.join(evidence) or '<li>No passage retained yet.</li>'}</ul><h3>Rule version review</h3><ul>{rules or '<li>No rule review required for this bounded finding.</li>'}</ul><h3>What changed</h3><ul>{changes or '<li>No version change recorded.</li>'}</ul></details></article>")
    gaps = "".join(f"<li><strong>{html.escape(x['code'])}</strong> — {html.escape(x['message'])}</li>" for x in report["findings"])
    return "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>CaptureBrief Decision Evidence</title><style>body{font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;background:#f6f7fb;color:#171b26;margin:0}.wrap{max-width:880px;margin:auto;padding:32px 18px 64px}header{background:white;border:1px solid #e3e6ef;border-radius:18px;padding:26px;margin-bottom:18px}h1{font-size:clamp(28px,5vw,44px);line-height:1.05;margin:.2em 0}article{background:white;border:1px solid #e3e6ef;border-radius:16px;padding:22px;margin:14px 0}.eyebrow{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#5a6275}h2{font-size:21px;margin:.4em 0}.finding{font-size:17px;line-height:1.5}details{border-top:1px solid #eceef4;margin-top:18px;padding-top:14px}summary{cursor:pointer;font-weight:750}blockquote{margin:8px 0;padding:12px 14px;background:#f7f8fb;border-left:3px solid #a2aabd;border-radius:5px;white-space:pre-wrap}li{margin:9px 0;line-height:1.45}.version-change{list-style:none;margin-left:-20px}.version-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}.delta-side{background:#f7f8fb;border:1px solid #e3e6ef;border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:5px;min-width:0}.delta-label{font-size:10px;font-weight:800;letter-spacing:.08em;color:#687187}.delta-locator{font-size:12px;color:#5a6275}.delta-side code{font-size:10px;overflow-wrap:anywhere;color:#626b7e}.gaps{background:#fff8e7;border:1px solid #f0d894;border-radius:16px;padding:18px;margin-top:18px}@media(max-width:620px){.version-grid{grid-template-columns:1fr}}@media(max-width:420px){.wrap{padding:18px 12px 44px}header,article{padding:18px}}</style></head><body><main class='wrap'><header><div class='eyebrow'>CaptureBrief · Pursuit QA</div><h1>Know what your bid decision rests on.</h1><p>Exact passages, source versions, rule editions, and what changed behind the assumptions your team is using.</p></header>" + "".join(cards) + (f"<section class='gaps'><h2>Evidence still needed</h2><ul>{gaps}</ul></section>" if gaps else "") + "</main></body></html>"
