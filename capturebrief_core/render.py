from __future__ import annotations
from typing import Any
from .audit import audit_case
from .model import AuditResult

def _e(v): return str(v or "").replace("|","\\|").strip()

def render_markdown(case:dict[str,Any],audit:AuditResult|None=None)->str:
    audit=audit or audit_case(case); rank={"GATE_CHANGING":0,"VERIFY_NOW":1,"MONITOR_ONLY":2}
    items=sorted(case.get("assumptions") or [],key=lambda x:(rank.get(str(x.get("decision_class","")).upper(),9),str(x.get("assumption_id",""))))
    handoff=[x for x in items if str(x.get("decision_class","")).upper() in {"GATE_CHANGING","VERIFY_NOW"}][:5]
    lines=[f"# CaptureBrief Pursuit QA — {_e(case.get('case_id'))}","",f"**Release state:** {audit.release_state}  ",f"**Current posture:** {_e(case.get('current_posture'))}  ",f"**Authority state:** {audit.currentness_verdict}  "]
    if audit.current_action_id: lines.append(f"**Verified action:** {_e(audit.current_action_id)}  ")
    lines += ["","## 90-second handoff",""]
    if not handoff: lines.append("No GATE_CHANGING or VERIFY_NOW items are currently retained.")
    for i in handoff:
        lines += [f"### {_e(i.get('assumption_id'))} — {_e(i.get('decision_class'))}",f"**Assumption:** {_e(i.get('text'))}",f"**Evidence:** {_e(i.get('evidence_state'))}",f"**Finding:** {_e(i.get('finding'))}",f"**Next action:** {_e(i.get('next_action'))}",f"**Owner / request:** {_e(i.get('owner') or i.get('evidence_request'))}",""]
    lines += ["## Forensic appendix","","### Release checks",""]
    if audit.findings:
        for f in audit.findings: lines.append(f"- **{f.severity} / {f.code}**: {_e(f.message)}" + (f" — {f.path}" if f.path else ""))
    else: lines.append("- No release-blocking or warning findings.")
    lines += ["","### Source manifest","","| Source | Authority | Artifact state | Observed | URL |","|---|---|---|---|---|"]
    for s in case.get("sources") or []: lines.append("| "+" | ".join(_e(s.get(k)) for k in ("source_id","authority","artifact_state","observed_at","url"))+" |")
    lines += ["","### Product boundary","","Public-source, human-supervised Pursuit QA only. Final pursuit decisions stay with the customer; no PWin scoring, bid submission, legal advice, or protected-portal authorization.",""]
    return "\n".join(lines)
