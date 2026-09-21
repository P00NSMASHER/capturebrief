from __future__ import annotations
from typing import Any
from .audit import audit_case
from .history import validate_history_receipts
from .manifest import validate_manifest_receipts
from .packet import validate_reference_closure
from .model import AuditResult


def _e(v): return str(v or "").replace("|","\\|").strip()


def render_markdown(case:dict[str,Any],audit:AuditResult|None=None)->str:
    audit=audit or audit_case(case); rank={"GATE_CHANGING":0,"VERIFY_NOW":1,"MONITOR_ONLY":2}
    packet=case.get("packet") or {}
    history_state,_=validate_history_receipts(packet.get("history_action_ids") or [],packet.get("history_receipts") or [])
    manifest_state,manifest_summary,_=validate_manifest_receipts(packet.get("history_action_ids") or [],packet.get("manifest_receipts") or [])
    reference_state,_=validate_reference_closure(packet)
    items=sorted(case.get("assumptions") or [],key=lambda x:(rank.get(str(x.get("decision_class","")).upper(),9),str(x.get("assumption_id",""))))
    handoff=[x for x in items if str(x.get("decision_class","")).upper() in {"GATE_CHANGING","VERIFY_NOW"}][:5]
    lines=[
        f"# CaptureBrief Pursuit QA — {_e(case.get('case_id'))}","",
        f"**Release state:** {audit.release_state}  ",
        f"**Current posture:** {_e(case.get('current_posture'))}  ",
        f"**Authority state:** {audit.currentness_verdict}  ",
        f"**History:** {history_state}  ",
        f"**Attachment manifests:** {manifest_state}  ",
        f"**Reference closure:** {reference_state}  ",
    ]
    if audit.current_action_id: lines.append(f"**Verified action:** {_e(audit.current_action_id)}  ")
    lines += ["","## 90-second handoff",""]
    if not handoff: lines.append("No GATE_CHANGING or VERIFY_NOW items are currently retained.")
    for i in handoff:
        lines += [f"### {_e(i.get('assumption_id'))} — {_e(i.get('decision_class'))}",f"**Assumption:** {_e(i.get('text'))}",f"**Evidence:** {_e(i.get('evidence_state'))}",f"**Finding:** {_e(i.get('finding'))}",f"**Next action:** {_e(i.get('next_action'))}",f"**Owner / request:** {_e(i.get('owner') or i.get('evidence_request'))}",""]
    lines += ["## Forensic appendix","","### Release checks",""]
    if audit.findings:
        for f in audit.findings: lines.append(f"- **{f.severity} / {f.code}**: {_e(f.message)}" + (f" — {f.path}" if f.path else ""))
    else: lines.append("- No release-blocking or warning findings.")

    lines += ["","### Packet integrity",""]
    lines.append(f"- Observed history actions: {len(set(packet.get('history_action_ids') or []))}")
    lines.append(f"- Actions with verified deletion-inclusive manifests: {len(manifest_summary.get('covered_actions', []))}")
    lines.append(f"- Uncovered actions: {len(manifest_summary.get('missing_actions', []))}")
    lines.append(f"- Named/incorporated references tracked: {len(packet.get('references') or [])}")

    lines += ["","### Manifest observations","","| Action | Status | Observed | Raw manifest SHA-256 |","|---|---|---|---|"]
    for r in packet.get("manifest_receipts") or []:
        lines.append("| "+" | ".join(_e(r.get(k)) for k in ("action_id","status","observed_at","raw_manifest_sha256"))+" |")

    if packet.get("references"):
        lines += ["","### Reference closure","","| Reference | Resolution | Source object | Bytes |","|---|---|---|---|"]
        for r in packet.get("references") or []:
            lines.append("| "+" | ".join(_e(r.get(k)) for k in ("reference_id","resolution","source_object_state","byte_state"))+" |")

    lines += ["","### Source manifest","","| Source | Authority | Artifact state | Observed | URL |","|---|---|---|---|---|"]
    for s in case.get("sources") or []: lines.append("| "+" | ".join(_e(s.get(k)) for k in ("source_id","authority","artifact_state","observed_at","url"))+" |")
    lines += ["","### Product boundary","","Public-source, human-supervised Pursuit QA only. Final pursuit decisions stay with the customer; no PWin scoring, bid submission, legal advice, or protected-portal authorization.",""]
    return "\n".join(lines)
