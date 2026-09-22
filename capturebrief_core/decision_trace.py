"""Exact source/rule/version evidence for CaptureBrief bid assumptions."""
from __future__ import annotations
import copy, hashlib, json, re
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

SCHEMA="1.0"; STATES={"SUPPORTED","CONTRADICTED","UNPROVEN","SUPERSEDED","SOURCE_LIMITED"}; RESOLVED_STATES={"SUPPORTED","CONTRADICTED","SUPERSEDED"}; CITATION_ROLES={"SUPPORTS","CONTRADICTS","CONTEXT"}; RULES={"FAR","DFARS","AGENCY_SUPPLEMENT","CLASS_DEVIATION","ILLUSTRATIVE"}

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(v): return hashlib.sha256(v.encode() if isinstance(v,str) else v).hexdigest()
def _text(v): return isinstance(v,str) and bool(v.strip())
def _sha(v): return isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v) is not None
def _dt(v):
    try:
        d=datetime.fromisoformat(v.replace("Z","+00:00")); return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,AttributeError): return None
def _date(v):
    try: return date.fromisoformat(v) if v else None
    except (ValueError,TypeError): return None
def _url(v,synthetic=False):
    try: p=urlsplit(v)
    except (ValueError,TypeError): return False
    if p.scheme!="https" or not p.hostname or p.username or p.password or re.search(r"(?:api[_-]?key|token|secret|signature|credential)=",p.query,re.I): return False
    return synthetic or not p.hostname.endswith((".example",".invalid"))
def _seal(prefix,payload): return prefix+digest(canonical(payload))

def freeze_text_snapshot(*,source,source_key,kind,version_label,text,capture_method,captured_by,mapping_note,published_at=None):
    if source.get("artifact_state")!="PUBLIC" or not _sha(source.get("content_sha256")): raise ValueError("PUBLIC content-addressed source required")
    if kind not in {"SOLICITATION","AMENDMENT","RULE","DEVIATION","CONTEXT"} or capture_method not in {"NATIVE_TEXT","REVIEWED_EXTRACTION"}: raise ValueError("invalid snapshot type")
    if not all(_text(x) for x in (source.get("source_id"),source_key,version_label,text,captured_by,mapping_note)) or not _dt(source.get("observed_at")): raise ValueError("incomplete snapshot provenance")
    p={"source_id":source["source_id"],"source_key":source_key,"kind":kind,"title":source.get("title") or source_key,"url":source.get("url"),"version_label":version_label,"document_sha256":source["content_sha256"],"text_sha256":digest(text),"text":text,"observed_at":source["observed_at"],"published_at":published_at,"artifact_state":"PUBLIC","capture_method":capture_method,"captured_by":captured_by,"mapping_note":mapping_note}
    return {"snapshot_id":_seal("SNAP:",p),**p}

def passage(snapshot,start,end,*,locator):
    lines=str(snapshot.get("text") or "").splitlines()
    if type(start) is not int or type(end) is not int or start<1 or end<start or end>len(lines) or not _text(locator): raise ValueError("invalid passage")
    return {"snapshot_id":snapshot["snapshot_id"],"line_start":start,"line_end":end,"locator":locator,"quote":"\n".join(lines[start-1:end])}

def freeze_rule_version(*,namespace,citation,edition,agency,text_passage,effective_from,effective_until=None,effective_date_passage=None,revision_ref=None):
    if namespace not in RULES or not all(_text(x) for x in (citation,edition,agency)): raise ValueError("invalid rule identity")
    a,b=_date(effective_from),_date(effective_until)
    if effective_from and not a or effective_until and not b or a and b and b<a: raise ValueError("invalid effective dates")
    p={"rule_key":f"{namespace}:{agency}:{citation}","namespace":namespace,"citation":citation,"edition":edition,"agency":agency,"text_passage":copy.deepcopy(text_passage),"effective_from":effective_from,"effective_until":effective_until,"effective_date_passage":copy.deepcopy(effective_date_passage),"revision_ref":revision_ref}
    return {"rule_version_id":_seal("RULE:",p),**p}

def _pass(p,snaps,add,path):
    if not isinstance(p,dict) or p.get("snapshot_id") not in snaps: add("TRACE_PASSAGE_SNAPSHOT_MISSING","Passage references an unknown retained source version.",path); return None
    s=snaps[p["snapshot_id"]]; lines=str(s.get("text") or "").splitlines(); a,b=p.get("line_start"),p.get("line_end")
    if type(a) is not int or type(b) is not int or a<1 or b<a or b>len(lines): add("TRACE_PASSAGE_RANGE_INVALID","Passage line range is invalid.",path); return s
    if not _text(p.get("locator")): add("TRACE_LOCATOR_MISSING","Passage needs a page/section/paragraph locator.",path)
    if p.get("quote")!="\n".join(lines[a-1:b]): add("TRACE_QUOTE_MISMATCH","Quoted evidence must exactly match retained source text.",path)
    return s

def evaluate_decision_trace(case,*,now=None,allow_synthetic=False):
    findings=[]; cards=[]; now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("now must be timezone-aware")
    def add(code,msg,path="decision_trace",severity="BLOCK"): findings.append({"code":code,"severity":severity,"message":msg,"path":path})
    t=case.get("decision_trace")
    if not isinstance(t,dict): add("TRACE_MISSING","Attach an exact source/rule/version trace before release."); return _result(case,findings,cards,False)
    synthetic=t.get("synthetic") is True
    if synthetic and not allow_synthetic: add("SYNTHETIC_TRACE_NOT_FOR_RELEASE","Illustrative evidence cannot authorize customer release.")
    if t.get("schema_version")!=SCHEMA: add("TRACE_SCHEMA_UNSUPPORTED","Decision trace schema must be 1.0.")
    if t.get("family_id")!=case.get("family_id"): add("TRACE_FAMILY_MISMATCH","Trace and case must identify the same pursuit family.")
    decision_time=_dt(t.get("decision_at"))
    if not decision_time or decision_time>now: add("TRACE_DECISION_TIME_INVALID","Decision time must be timezone-aware and not in the future.")
    sources={str(x.get("source_id")):x for x in case.get("sources",[]) if isinstance(x,dict) and x.get("source_id")}; snaps={}
    for i,s in enumerate(t.get("snapshots",[]) if isinstance(t.get("snapshots"),list) else []):
        p=f"decision_trace.snapshots[{i}]"; sid=s.get("snapshot_id") if isinstance(s,dict) else None
        if not _text(sid) or sid in snaps: add("TRACE_ID_INVALID","Snapshot IDs must be unique.",p); continue
        snaps[sid]=s
        if sid!=_seal("SNAP:",{k:v for k,v in s.items() if k!="snapshot_id"}): add("TRACE_SNAPSHOT_TAMPERED","Snapshot identity does not match its content/metadata.",p)
        if digest(str(s.get("text") or ""))!=s.get("text_sha256"): add("TRACE_TEXT_HASH_MISMATCH","Retained text hash does not match.",p)
        src=sources.get(str(s.get("source_id")))
        if not src: add("TRACE_SOURCE_MISSING","Snapshot source is missing from case manifest.",p); continue
        if src.get("artifact_state")!="PUBLIC": add("TRACE_SOURCE_NOT_PUBLIC","Decision evidence must use public evidence or remain source-limited.",p)
        if src.get("content_sha256")!=s.get("document_sha256"): add("TRACE_SOURCE_BINDING_MISMATCH","Snapshot is not bound to retained source bytes.",p)
        if s.get("url")!=src.get("url") or s.get("observed_at")!=src.get("observed_at"):
            add("TRACE_SOURCE_METADATA_MISMATCH","Snapshot URL and observation time must match the bound source record.",p)
        observed=_dt(s.get("observed_at"))
        if not observed or observed>now: add("TRACE_LOOKAHEAD_EVIDENCE","Snapshot time is invalid or after review.",p)
        if decision_time and observed and observed>decision_time:
            add("TRACE_LOOKAHEAD_DECISION_EVIDENCE","A decision cannot rely on evidence observed after its declared decision time.",p)
        if not _url(s.get("url"),synthetic): add("TRACE_SOURCE_URL_INVALID","Evidence URL must be safe HTTPS without embedded credentials.",p)
    rules={}
    for i,r in enumerate(t.get("rule_versions",[]) if isinstance(t.get("rule_versions"),list) else []):
        p=f"decision_trace.rule_versions[{i}]"; rid=r.get("rule_version_id") if isinstance(r,dict) else None
        if not _text(rid) or rid in rules: add("TRACE_ID_INVALID","Rule-version IDs must be unique.",p); continue
        rules[rid]=r
        if r.get("namespace") not in RULES or (not synthetic and r.get("namespace")=="ILLUSTRATIVE"): add("TRACE_RULE_NAMESPACE_INVALID","Rule namespace is invalid for this release.",p)
        if rid!=_seal("RULE:",{k:v for k,v in r.items() if k!="rule_version_id"}): add("TRACE_RULE_TAMPERED","Rule-version identity does not match its content/metadata.",p)
        _pass(r.get("text_passage"),snaps,add,p+".text_passage")
    assumptions={str(a.get("assumption_id")):a for a in case.get("assumptions",[]) if isinstance(a,dict) and a.get("assumption_id")}; seen=set()
    if not assumptions: add("TRACE_ASSUMPTIONS_EMPTY","Trace requires at least one bounded assumption.")
    for i,rv in enumerate(t.get("reviews",[]) if isinstance(t.get("reviews"),list) else []):
        aid=str(rv.get("assumption_id") or "") if isinstance(rv,dict) else ""; path=f"decision_trace.reviews.{aid or i}"
        if aid not in assumptions or aid in seen: add("TRACE_REVIEW_ASSUMPTION_INVALID","Each assumption needs exactly one trace review.",path); continue
        seen.add(aid); a=assumptions[aid]; state=str(rv.get("evidence_state") or "")
        if state not in STATES or state!=a.get("evidence_state"): add("TRACE_REVIEW_STATE_MISMATCH","Trace state must match the buyer handoff.",path)
        if rv.get("finding")!=a.get("finding"): add("TRACE_REVIEW_FINDING_MISMATCH","Trace finding must match buyer-facing finding.",path)
        reviewed_at=_dt(rv.get("reviewed_at"))
        if not _text(rv.get("reviewed_by")) or not reviewed_at: add("TRACE_REVIEW_MISSING","Named reviewer and timezone-aware review time required.",path)
        elif reviewed_at>now: add("TRACE_REVIEW_TIME_INVALID","Review time cannot be in the future.",path)
        elif decision_time and reviewed_at>decision_time: add("TRACE_REVIEW_AFTER_DECISION","The declared decision time cannot precede the human evidence review.",path)
        checked=[]; cited=set(); citation_roles=[]
        for n,citation in enumerate(rv.get("citations",[]) if isinstance(rv.get("citations"),list) else []):
            cp=path+f".citations[{n}]"
            role=citation.get("role") if isinstance(citation,dict) else None
            if role is not None and role not in CITATION_ROLES:
                add("TRACE_CITATION_ROLE_INVALID","Citation role must be SUPPORTS, CONTRADICTS, or CONTEXT.",cp)
            elif role in CITATION_ROLES:
                citation_roles.append(role)
            s=_pass(citation,snaps,add,cp)
            if s:
                cited.add(str(s.get("source_id")))
                checked.append({**citation,"source":{k:s.get(k) for k in ("source_id","title","url","version_label","document_sha256","observed_at")}})
        if state in RESOLVED_STATES and not checked:
            add("TRACE_RESOLVED_EVIDENCE_MISSING","Resolved findings require at least one exact retained evidence passage.",path)
        required_role={"SUPPORTED":"SUPPORTS","CONTRADICTED":"CONTRADICTS"}.get(state)
        if required_role and required_role not in citation_roles:
            add("TRACE_RESOLVED_EVIDENCE_ROLE_MISSING",f"{state} findings require at least one {required_role} citation.",path)
        if not cited.issubset(set(map(str,a.get("source_ids") or []))): add("TRACE_ASSUMPTION_SOURCE_MISMATCH","Every cited source must be linked from the assumption.",path)
        scope=rv.get("rule_scope") if isinstance(rv.get("rule_scope"),dict) else {}
        if scope.get("status") not in {"REQUIRED","NOT_RELEVANT","UNRESOLVED"} or not _text(scope.get("rationale")): add("TRACE_RULE_SCOPE_MISSING","Record rule-review scope and rationale.",path)
        if state in RESOLVED_STATES and scope.get("status")=="UNRESOLVED":
            add("TRACE_RESOLVED_RULE_SCOPE_UNRESOLVED","A resolved buyer finding cannot retain unresolved rule scope.",path)
        links=rv.get("rule_links",[]) if isinstance(rv.get("rule_links"),list) else []
        if scope.get("status")=="REQUIRED" and not links: add("TRACE_RULE_REVIEW_MISSING","Rule-dependent assumption lacks applicability review.",path)
        if state in {"UNPROVEN","SOURCE_LIMITED"} and not _text(rv.get("evidence_request")): add("TRACE_EVIDENCE_REQUEST_MISSING","Unresolved assumption needs a concrete evidence request.",path)
        checked_rules=[]
        for n,l in enumerate(links):
            lp=path+f".rule_links[{n}]"; r=rules.get(l.get("rule_version_id")) if isinstance(l,dict) else None
            if not r: add("TRACE_RULE_VERSION_MISSING","Applicability review references unknown rule edition.",lp); continue
            if l.get("family_id")!=case.get("family_id"): add("TRACE_RULE_FAMILY_MISMATCH","Rule review is not bound to this pursuit.",lp)
            applicability=l.get("applicability")
            if applicability not in {"APPLIES","DOES_NOT_APPLY","UNRESOLVED"} or not _text(l.get("rationale")): add("TRACE_RULE_APPLICABILITY_INVALID","Applicability needs reviewed state and rationale.",lp)
            if state in RESOLVED_STATES and applicability=="UNRESOLVED":
                add("TRACE_RESOLVED_RULE_APPLICABILITY_UNRESOLVED","A resolved buyer finding cannot depend on unresolved rule applicability.",lp)
            if l.get("basis")=="INCORPORATED_EDITION" and l.get("incorporated_edition")!=r.get("edition"): add("TRACE_INCORPORATED_EDITION_MISMATCH","Do not replace incorporated edition with newest publication.",lp)
            basis_passage=l.get("basis_passage")
            if applicability in {"APPLIES","DOES_NOT_APPLY"} and not isinstance(basis_passage,dict):
                add("TRACE_RULE_BASIS_PASSAGE_MISSING","Resolved rule applicability requires an exact pursuit-specific basis passage.",lp)
            elif basis_passage:
                basis_source=_pass(basis_passage,snaps,add,lp+".basis_passage")
                if basis_source and basis_source.get("kind") in {"RULE","DEVIATION"}:
                    add("TRACE_RULE_BASIS_NOT_PURSUIT_SPECIFIC","Rule text cannot serve as its own pursuit-specific applicability basis.",lp+".basis_passage")
            checked_rules.append({**l,"rule_key":r.get("rule_key"),"namespace":r.get("namespace"),"citation":r.get("citation"),"edition":r.get("edition")})
        changes=rv.get("changes",[]) if isinstance(rv.get("changes"),list) else []
        resolved_changes=[]
        for n,c in enumerate(changes):
            cp=path+f".changes[{n}]"; old=snaps.get(c.get("from_snapshot_id")) if isinstance(c,dict) else None; new=snaps.get(c.get("to_snapshot_id")) if isinstance(c,dict) else None
            if not old or not new or old.get("source_key")!=new.get("source_key") or old.get("snapshot_id")==new.get("snapshot_id"): add("TRACE_CHANGE_LINEAGE_INVALID","Change must join distinct versions of same logical source.",cp)
            if not isinstance(c,dict) or c.get("relation") not in {"SUPERSEDES","AMENDS","CORRECTS"} or not _text(c.get("summary")): add("TRACE_CHANGE_RELATION_INVALID","Version change needs sourced relation and summary.",cp)
            from_passage=c.get("from_passage") if isinstance(c,dict) else None
            to_passage=c.get("to_passage") if isinstance(c,dict) else None
            if bool(from_passage) != bool(to_passage):
                add("TRACE_CHANGE_PASSAGE_PAIR_INCOMPLETE","Version delta must retain both before and after passages when either is supplied.",cp)
            elif from_passage and to_passage:
                from_source=_pass(from_passage,snaps,add,cp+".from_passage")
                to_source=_pass(to_passage,snaps,add,cp+".to_passage")
                if from_source and old and from_source.get("snapshot_id")!=old.get("snapshot_id"):
                    add("TRACE_CHANGE_PASSAGE_VERSION_MISMATCH","Before passage must belong to the declared from-version.",cp+".from_passage")
                if to_source and new and to_source.get("snapshot_id")!=new.get("snapshot_id"):
                    add("TRACE_CHANGE_PASSAGE_VERSION_MISMATCH","After passage must belong to the declared to-version.",cp+".to_passage")
            else:
                add("TRACE_CHANGE_PASSAGES_MISSING","Version relation is retained, but no exact before/after passages are attached.",cp,"WARN")
            enriched=copy.deepcopy(c) if isinstance(c,dict) else {}
            if old:
                enriched["from_source"]={k:old.get(k) for k in ("snapshot_id","source_id","title","url","version_label","document_sha256","observed_at","published_at")}
            if new:
                enriched["to_source"]={k:new.get(k) for k in ("snapshot_id","source_id","title","url","version_label","document_sha256","observed_at","published_at")}
            resolved_changes.append(enriched)
        cards.append({"assumption_id":aid,"assumption":a.get("text"),"evidence_state":state,"decision_class":a.get("decision_class"),"finding":rv.get("finding"),"next_action":a.get("next_action"),"owner":a.get("owner"),"evidence_request":rv.get("evidence_request"),"reviewed_by":rv.get("reviewed_by"),"reviewed_at":rv.get("reviewed_at"),"rule_scope":scope,"citations":checked,"rule_links":checked_rules,"changes":resolved_changes})
    for aid in sorted(set(assumptions)-seen): add("TRACE_REVIEW_MISSING_FOR_ASSUMPTION",f"Assumption {aid} has no source/rule/version review.",f"decision_trace.reviews.{aid}")
    return _result(case,findings,cards,synthetic)

def _result(case,findings,cards,synthetic):
    bad=any(x["severity"]=="BLOCK" for x in findings)
    return {"trace_schema_version":SCHEMA,"case_id":case.get("case_id"),"family_id":case.get("family_id"),"trace_state":"TRACE_INCOMPLETE" if bad else "ILLUSTRATIVE_TRACE_COMPLETE" if synthetic else "TRACE_COMPLETE","customer_release_authorized":False,"synthetic":synthetic,"decision_at":(case.get("decision_trace") or {}).get("decision_at") if isinstance(case.get("decision_trace"),dict) else None,"assumptions":cards,"findings":findings,"case_sha256":digest(canonical(case))}

def compare_decision_traces(before,after):
    if (before.get("case_id"),before.get("family_id"))!=(after.get("case_id"),after.get("family_id")): raise ValueError("cannot compare different cases")
    bt,at=before.get("decision_trace") or {},after.get("decision_trace") or {}; events=[]; violations=[]; changed_sources=set(); changed_rules=set()
    for key,idk,gk,changed in (("snapshots","snapshot_id","source_key",changed_sources),("rule_versions","rule_version_id","rule_key",changed_rules)):
        b={x[idk]:x for x in bt.get(key,[]) if isinstance(x,dict) and x.get(idk)}; a={x[idk]:x for x in at.get(key,[]) if isinstance(x,dict) and x.get(idk)}; oldgroups={x.get(gk) for x in b.values()}
        for ident in set(b)-set(a): violations.append({"code":"TRACE_HISTORY_REMOVED","id":ident}); changed.add(b[ident].get(gk))
        for ident in set(b)&set(a):
            if canonical(b[ident])!=canonical(a[ident]): violations.append({"code":"TRACE_HISTORY_REWRITTEN","id":ident}); changed.add(b[ident].get(gk))
        for ident in set(a)-set(b):
            group=a[ident].get(gk); same=key=="snapshots" and any(x.get(gk)==group and all(x.get(k)==a[ident].get(k) for k in ("document_sha256","text_sha256","version_label","artifact_state")) for x in b.values())
            if group in oldgroups and not same: changed.add(group); events.append({"type":"SOURCE_VERSION_CHANGED" if key=="snapshots" else "RULE_VERSION_OBSERVED","dependency_key":group,"new_id":ident,"applicability":"REVIEW_REQUIRED"})
    oldsnaps={s["snapshot_id"]:s for s in bt.get("snapshots",[]) if isinstance(s,dict) and s.get("snapshot_id")}; oldrules={r["rule_version_id"]:r for r in bt.get("rule_versions",[]) if isinstance(r,dict) and r.get("rule_version_id")}; reopened=[]
    for rv in bt.get("reviews",[]):
        sdeps={oldsnaps[p.get("snapshot_id")].get("source_key") for p in rv.get("citations",[]) if p.get("snapshot_id") in oldsnaps}; rdeps={oldrules[x.get("rule_version_id")].get("rule_key") for x in rv.get("rule_links",[]) if x.get("rule_version_id") in oldrules}; matched=sorted((sdeps&changed_sources)|(rdeps&changed_rules))
        if matched: reopened.append({"assumption_id":rv.get("assumption_id"),"matched_dependencies":matched,"status":"REVIEW_REQUIRED","previous_decision_preserved":True})
    return {"events":events,"reopened_assumptions":reopened,"integrity_violations":violations,"automatic_applicability_change":False}

def trace_work_items(case,*,now=None):
    groups={}
    for f in evaluate_decision_trace(case,now=now)["findings"]:
        m=re.match(r"decision_trace\.reviews\.([^.[\]]+)",f.get("path") or ""); key="trace:assumption:"+m.group(1) if m else "trace:integrity"; groups.setdefault(key,[]).append(f)
    return [{"task_key":k,"priority":"P0","title":"Complete source/rule/version review"+(" for "+k.rsplit(":",1)[1] if k!="trace:integrity" else " and snapshot integrity"),"actor":"HUMAN_REVIEW","can_auto_execute":False,"status":"OPEN","reason":"; ".join(dict.fromkeys(x["message"] for x in v)),"evidence_needed":"Pinned exact passages, source editions, applicability basis and named reviewer.","metadata":{"finding_codes":sorted({x["code"] for x in v})}} for k,v in sorted(groups.items())]
