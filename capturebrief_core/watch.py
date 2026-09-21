from __future__ import annotations
from typing import Any
from .model import parse_dt
from .packet import diff_manifest_receipts


def _artifacts(case):
    return {str(a.get("artifact_id")):a for a in (case.get("packet") or {}).get("artifacts",[]) if a.get("artifact_id")}


def _latest_receipts(case):
    out={}
    for r in (case.get("packet") or {}).get("manifest_receipts",[]) or []:
        aid=str(r.get("action_id",""))
        if not aid: continue
        current=out.get(aid)
        if current is None or (parse_dt(r.get("observed_at")) or 0) > (parse_dt(current.get("observed_at")) or 0): out[aid]=r
    return out


def _references(case):
    return {str(r.get("reference_id")):r for r in (case.get("packet") or {}).get("references",[]) if r.get("reference_id")}


def compare_cases(before:dict[str,Any],after:dict[str,Any])->dict[str,Any]:
    events=[]; b=before.get("packet") or {}; a=after.get("packet") or {}
    bh=set(map(str,b.get("history_action_ids") or [])); ah=set(map(str,a.get("history_action_ids") or []))
    for x in sorted(ah-bh): events.append({"type":"ACTION_ADDED","key":"CURRENT_ACTION_CHANGE","action_id":x})
    for x in sorted(bh-ah): events.append({"type":"ACTION_DISAPPEARED","key":"CURRENT_ACTION_CHANGE","action_id":x})

    bm,am=_latest_receipts(before),_latest_receipts(after)
    for action_id in sorted(set(bm)&set(am)):
        if bm[action_id].get("raw_manifest_sha256") != am[action_id].get("raw_manifest_sha256"):
            events.append({"type":"MANIFEST_CHANGED","key":f"MANIFEST:{action_id}","action_id":action_id})
            for change in diff_manifest_receipts(bm[action_id],am[action_id]):
                e={**change,"action_id":action_id}
                rid=change.get("resource_id")
                name=change.get("name")
                e["key"]=f"RESOURCE:{rid}" if rid else (f"FILENAME:{name}" if name else f"MANIFEST:{action_id}")
                events.append(e)

    ba,aa=_artifacts(before),_artifacts(after)
    for aid in sorted(set(ba)|set(aa)):
        x,y=ba.get(aid),aa.get(aid)
        if x is None: events.append({"type":"ARTIFACT_ADDED","key":f"ARTIFACT:{aid}","artifact_id":aid})
        elif y is None: events.append({"type":"ARTIFACT_DISAPPEARED","key":f"ARTIFACT:{aid}","artifact_id":aid})
        elif (x.get("sha256"),x.get("state"),x.get("name"),x.get("byte_state"))!=(y.get("sha256"),y.get("state"),y.get("name"),y.get("byte_state")): events.append({"type":"ARTIFACT_CHANGED","key":f"ARTIFACT:{aid}","artifact_id":aid})

    br,ar=_references(before),_references(after)
    for rid in sorted(set(br)|set(ar)):
        x,y=br.get(rid),ar.get(rid)
        if x is None or y is None or (x.get("resolution"),x.get("resource_id"),x.get("successor_resource_id"),x.get("byte_state")) != (y.get("resolution"),y.get("resource_id"),y.get("successor_resource_id"),y.get("byte_state")):
            events.append({"type":"REFERENCE_CLOSURE_CHANGED","key":f"REFERENCE:{rid}","reference_id":rid})
            events.append({"type":"PACKET_REFERENCE_CLOSURE_CHANGED","key":"PACKET_REFERENCE_CLOSURE"})

    keys={e["key"] for e in events}; reopened=[]
    for item in after.get("assumptions") or []:
        matched=sorted(set(map(str,item.get("reopen_triggers") or [])) & keys)
        if matched: reopened.append({"assumption_id":item.get("assumption_id"),"matched_triggers":matched})
    if "decision_trace" in before or "decision_trace" in after:
        from .decision_trace import compare_decision_traces
        trace_changes = compare_decision_traces(before, after)
        events.extend(trace_changes["events"])
        by_id = {x["assumption_id"]: x for x in reopened}
        for row in trace_changes["reopened_assumptions"]:
            target = by_id.setdefault(
                row["assumption_id"],
                {"assumption_id": row["assumption_id"], "matched_triggers": []},
            )
            target["matched_triggers"] = sorted(
                set(target["matched_triggers"])
                | {"TRACE:" + key for key in row["matched_dependencies"]}
            )
        return {
            "events": events,
            "reopened_assumptions": list(by_id.values()),
            "trace_integrity_violations": trace_changes["integrity_violations"],
            "automatic_applicability_change": False,
        }
    return {"events":events,"reopened_assumptions":reopened}
