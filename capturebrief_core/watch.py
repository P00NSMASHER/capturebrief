from __future__ import annotations
from typing import Any

def _artifacts(case):
    return {str(a.get("artifact_id")):a for a in (case.get("packet") or {}).get("artifacts",[]) if a.get("artifact_id")}

def compare_cases(before:dict[str,Any],after:dict[str,Any])->dict[str,Any]:
    events=[]; b=before.get("packet") or {}; a=after.get("packet") or {}
    bh=set(map(str,b.get("history_action_ids") or [])); ah=set(map(str,a.get("history_action_ids") or []))
    for x in sorted(ah-bh): events.append({"type":"ACTION_ADDED","key":"CURRENT_ACTION_CHANGE","action_id":x})
    for x in sorted(bh-ah): events.append({"type":"ACTION_DISAPPEARED","key":"CURRENT_ACTION_CHANGE","action_id":x})
    if b.get("manifest_sha256")!=a.get("manifest_sha256"): events.append({"type":"MANIFEST_CHANGED","key":"PACKET_MANIFEST_CHANGE"})
    if b.get("history_complete")!=a.get("history_complete"): events.append({"type":"HISTORY_COMPLETENESS_CHANGED","key":"CURRENT_ACTION_CHANGE"})
    if b.get("manifest_complete")!=a.get("manifest_complete"): events.append({"type":"MANIFEST_COMPLETENESS_CHANGED","key":"PACKET_MANIFEST_CHANGE"})
    ba,aa=_artifacts(before),_artifacts(after)
    for aid in sorted(set(ba)|set(aa)):
        x,y=ba.get(aid),aa.get(aid)
        if x is None: events.append({"type":"ARTIFACT_ADDED","key":f"ARTIFACT:{aid}","artifact_id":aid})
        elif y is None: events.append({"type":"ARTIFACT_DISAPPEARED","key":f"ARTIFACT:{aid}","artifact_id":aid})
        elif (x.get("sha256"),x.get("state"),x.get("name"))!=(y.get("sha256"),y.get("state"),y.get("name")): events.append({"type":"ARTIFACT_CHANGED","key":f"ARTIFACT:{aid}","artifact_id":aid})
    keys={e["key"] for e in events}; reopened=[]
    for item in after.get("assumptions") or []:
        matched=sorted(set(map(str,item.get("reopen_triggers") or [])) & keys)
        if matched: reopened.append({"assumption_id":item.get("assumption_id"),"matched_triggers":matched})
    return {"events":events,"reopened_assumptions":reopened}
