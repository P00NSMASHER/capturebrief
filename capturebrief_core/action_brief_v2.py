"""CaptureBrief 2.0: print-ready, action-first HTML for approved buyer bundles.

Inputs MUST be the independently evaluated delivery-ready case/audit/trace.
This module does not grant delivery authority, decide legal applicability,
invent cost exposure, change source state or authorize automated contact.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

RANK = {"GATE_CHANGING": 0, "VERIFY_NOW": 1, "MONITOR_ONLY": 2}
LABEL = {
    "GATE_CHANGING": "Action-changing",
    "VERIFY_NOW": "Verify before relying",
    "MONITOR_ONLY": "Monitor",
}
STATE = {
    "SUPPORTED": "Supported",
    "CONTRADICTED": "Contradicted",
    "SUPERSEDED": "Superseded",
    "UNPROVEN": "Unproven",
    "SOURCE_LIMITED": "Source limited",
}
STYLES = r"""
:root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:#132337;background:#f1f5f8}
*{box-sizing:border-box}body{margin:0}.shell{max-width:960px;margin:0 auto;padding:32px 24px 52px}
header{background:#0a2338;color:#fff;padding:29px 35px;border-radius:16px 16px 0 0}
.kicker{font-size:11px;font-weight:800;letter-spacing:.15em;text-transform:uppercase;color:#70d5b9}
h1{margin:9px 0 5px;font-size:clamp(26px,4vw,37px);line-height:1.17;letter-spacing:-.025em}
.muted{color:#a4bdca;font-size:13px}.meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}
.meta span{border:1px solid #517083;border-radius:999px;padding:5px 10px;font-size:12px}
.note{padding:17px 27px;background:#fff7e8;color:#614b22;border-left:5px solid #d9932e;font-size:13px;line-height:1.5}
main{background:white;padding:27px 35px;border:1px solid #d5e0e8;border-top:0}
h2{font-size:17px;letter-spacing:-.01em;margin:0 0 12px}.overview{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:22px}
.stat{border:1px solid #d4e2eb;background:#f5f9fb;padding:14px;border-radius:10px}
.stat strong{display:block;font-size:27px;line-height:1.1;color:#113855}.stat span{font-size:11px;color:#5c6e80}
.summary{border:1px solid #b8d9d6;background:#f1faf9;border-radius:12px;padding:17px 18px;margin:18px 0 25px}
.summary p{font-size:14px;line-height:1.6;margin:0}.summary .small{font-size:12px;color:#49645f;margin-top:8px}
.finding{border:1px solid #d5e0e8;border-left:5px solid #58748c;padding:17px 18px;margin:0 0 13px;border-radius:11px;break-inside:avoid}
.finding[data-priority="GATE_CHANGING"]{border-left-color:#b84637}
.finding[data-priority="VERIFY_NOW"]{border-left-color:#b98b28}
.badges{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:11px;font-weight:800;letter-spacing:.025em}
.badge{background:#eaf1f6;border-radius:999px;padding:4px 8px}
.priority{color:#4a6070}.finding h3{font-size:16px;margin:10px 0 10px;color:#122c3d}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.columns strong{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#496779}
.columns p{margin:5px 0 0;font-size:13px;line-height:1.48;overflow-wrap:anywhere}
.proof{margin-top:13px;padding-top:11px;border-top:1px solid #e2ebf0;font-size:12px;line-height:1.5}
.proof strong{color:#466678}.proof p{margin:5px 0}.proof a{color:#086d68}
.proof code{font-size:10px;overflow-wrap:anywhere}.proof .line{color:#41556a}
.owner{color:#586a7a;font-size:12px;margin:10px 0 0}
.footer{border-top:1px solid #d5e0e8;padding-top:20px;margin-top:22px;color:#52697a;font-size:12px;line-height:1.65}
.footer p{margin:4px 0}.footer a{color:#0a6b64}.doc-actions{margin:0 0 18px;display:flex;gap:10px}
.doc-actions a{display:inline-flex;padding:9px 13px;background:#0f766e;color:white;text-decoration:none;border-radius:8px;font-size:13px;font-weight:700}
@media(max-width:580px){.shell{padding:10px 8px 25px}header,main{padding:22px 17px}
  .overview{grid-template-columns:repeat(3,1fr)}.stat{padding:10px}.stat strong{font-size:21px}
  .columns{grid-template-columns:1fr;gap:13px}.finding{padding:13px}}
@page{size:letter;margin:11mm}
@media print{
  :root{color:#132337;background:#fff}body{background:#fff}
  .shell{max-width:none;padding:0}header{border-radius:0;padding:16px 20px;print-color-adjust:exact}
  main{padding:17px 20px;border:0}.note{padding:10px 16px;print-color-adjust:exact}
  .doc-actions{display:none}.overview{margin-bottom:13px}.stat{padding:9px;print-color-adjust:exact}
  .finding{margin-bottom:9px;padding:10px 13px;break-inside:avoid;print-color-adjust:exact}
  .finding h3{font-size:14px;margin:6px 0}.columns p{font-size:11px}
  .proof{padding-top:7px;margin-top:8px}.proof p{font-size:10px}
  .footer{font-size:10px;padding-top:9px;margin-top:12px}
  a{color:inherit}h1{font-size:25px}
}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _link(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 2048 or any(
        ord(ch) < 32 or ord(ch) == 127 for ch in value
    ):
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != "https" or not u.hostname or u.username or u.password
                or u.fragment or u.port not in (None, 443)):
            return None
        if any(x in u.query.casefold() for x in ("api_key=", "token=", "secret=", "signature=")):
            return None
    except ValueError:
        return None
    return value


def _cite_html(citation: dict[str, Any]) -> str:
    src = citation.get("source") or {}
    if not isinstance(src, dict):
        src = {}
    title = _esc(src.get("title") or src.get("source_id") or "Public source")
    version = _esc(src.get("version_label") or "Version not labeled")
    locator = _esc(citation.get("locator") or "Locator not recorded")
    digest = str(src.get("document_sha256") or "")
    if not (len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)):
        digest = "not recorded"
    url = _link(src.get("url"))
    source = (f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
              if url else title + " <em>(Unverified source link)</em>")
    quote = _esc(citation.get("quote") or "")
    return (
        f'<div class="proof"><strong>Source trail:</strong> {source} · {version}'
        f'<p class="line">{locator}</p>'
        f'<p>Retained passage: “{quote}”</p>'
        f'<p>Document SHA-256: <code>{_esc(digest)}</code></p></div>'
    )


def render_action_brief_v2(
    case: dict[str, Any], trace: dict[str, Any], audit: Any,
    *, now: datetime,
) -> str:
    """Render buyer-safe, standalone HTML only after existing release gates pass."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Review timestamp must include a timezone")
    if not isinstance(case, dict) or not isinstance(trace, dict):
        raise ValueError("Source case and trace must be verified")
    if (trace.get("trace_state") != "TRACE_COMPLETE"
            or getattr(audit, "release_state", None) != "READY_FOR_HUMAN_RELEASE"):
        raise ValueError("Incomplete source history or release gates cannot render as ready")
    cards = trace.get("assumptions")
    if not isinstance(cards, list) or not 1 <= len(cards) <= 5:
        raise ValueError("The one-pursuit brief requires one to five reviewed assumptions")
    if any(not isinstance(c, dict)
           or not c.get("assumption_id")
           or not c.get("finding")
           or c.get("evidence_state") not in STATE
           or c.get("decision_class") not in RANK for c in cards):
        raise ValueError("Buyer-facing review card lacks supported evidence or decision class")
    cards = sorted(cards, key=lambda card: (
        RANK[card["decision_class"]], str(card["assumption_id"])))
    high = sum(c["decision_class"] == "GATE_CHANGING" for c in cards)
    verify = sum(c["decision_class"] == "VERIFY_NOW" for c in cards)
    watch = sum(c["decision_class"] == "MONITOR_ONLY" for c in cards)
    top = next((c for c in cards if c["decision_class"] != "MONITOR_ONLY"), cards[0])
    top_next = top.get("next_action") or top.get("evidence_request") or (
        "Recheck the cited public evidence before the next pursuit decision."
    )
    blocks = []
    for card in cards:
        key = str(card["assumption_id"])
        state = str(card["evidence_state"])
        cls = str(card["decision_class"])
        action = card.get("next_action") or card.get("evidence_request") or (
            "Retain this assumption on the monitored source baseline."
            if cls == "MONITOR_ONLY" else "Obtain the missing controlling source.")
        cites = card.get("citations")
        first = (next((x for x in cites if isinstance(x, dict)), None)
                 if isinstance(cites, list) else None)
        proof = _cite_html(first) if first else (
            '<div class="proof"><strong>Source trail:</strong> No resolved '
            'passage in this review. See the evidence appendix and retain HOLD '
            'until the controlling record is obtained.</div>'
        )
        if state in {"SOURCE_LIMITED", "UNPROVEN"}:
            request = card.get("evidence_request") or (
                "Obtain the controlling source before making this assumption.")
            proof += ('<p class="owner"><strong>Evidence to request:</strong> '
                      + _esc(request) + '</p>')
        owner = card.get("owner") or "Buyer-designated pursuit lead"
        blocks.append(
            f'<article class="finding" id="finding-{_esc(key)}" data-priority="{_esc(cls)}">'
            f'<div class="badges"><span class="badge">{_esc(key)}</span>'
            f'<span class="badge">{_esc(STATE[state])}</span>'
            f'<span class="priority">{_esc(LABEL[cls])}</span></div>'
            f'<h3>{_esc(card.get("assumption") or "Reviewed assumption")}</h3>'
            '<div class="columns">'
            f'<div><strong>What we found</strong><p>{_esc(card["finding"])}</p></div>'
            f'<div><strong>What to do</strong><p>{_esc(action)}</p></div>'
            '</div>' + proof +
            f'<p class="owner">Owner / handoff: {_esc(owner)}</p></article>'
        )
    evaluated = now.astimezone(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")
    markup = "\n".join(blocks)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>CaptureBrief 2.0 · 90-second decision brief</title>'
        '<meta name="robots" content="noindex,nofollow">'
        '<style>' + STYLES + '</style></head><body><div class="shell">'
        '<header><div class="kicker">CaptureBrief 2.0 · Buyer handoff</div>'
        '<h1>90-second decision brief</h1>'
        '<div class="muted">One public federal pursuit · Source-linked assumption review</div>'
        '<div class="meta"><span>Case: ' + _esc(case.get("case_id")) + '</span>'
        '<span>Posture: ' + _esc(case.get("current_posture") or "UNSPECIFIED") + '</span>'
        '<span>Reviewed: ' + _esc(evaluated) + '</span></div></header>'
        '<div class="note"><strong>Review stage:</strong> Evidence-based internal handoff. '
        'Human authorization is required before any external delivery. '
        'No automated bid decision or legal determination.</div>'
        '<main><div class="doc-actions"><a href="decision-evidence.html">'
        'Open full source trail</a></div>'
        '<h2>Decision flags</h2><div class="overview">'
        f'<div class="stat"><strong>{high}</strong><span>Action-changing</span></div>'
        f'<div class="stat"><strong>{verify}</strong><span>Verify now</span></div>'
        f'<div class="stat"><strong>{watch}</strong><span>Monitor only</span></div>'
        '</div><section class="summary"><h2>First action</h2><p>'
        + _esc(top_next) + '</p><p class="small">Evidence status is not a predicted '
        'award outcome. Follow the reviewed source trail before acting.</p></section>'
        '<h2>Findings, highest priority first</h2>' + markup
        + '<footer class="footer"><p><strong>Source trail:</strong> Exact retained passages, '
        'document hashes, version history and applicability review are in '
        '<a href="decision-evidence.html">decision-evidence.html</a>; see '
        '<strong>source-version-manifest.json</strong> for source identities and '
        '<strong>watch-baseline.json</strong> for the targeted watch.</p>'
        '<p><strong>Boundaries:</strong> Not a bid decision, eligibility certification, '
        'probability-of-win score or legal advice. No automatic approval, payment, '
        'customer contact or provider send. Customer retains the final decision.</p>'
        '<p>To export a PDF, open this HTML in a browser and use Print → Save as PDF. '
        'This file contains its own print styling and no remote scripts or trackers.</p>'
        '</footer></main></div></body></html>'
    )
