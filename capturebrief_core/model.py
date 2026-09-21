from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

EVIDENCE_STATES={"SUPPORTED","CONTRADICTED","UNPROVEN","SUPERSEDED","SOURCE_LIMITED"}
DECISION_CLASSES={"GATE_CHANGING","VERIFY_NOW","MONITOR_ONLY"}
SOURCE_AUTHORITIES={"CONTROLLING_CURRENT","SUPPORTING","HISTORICAL_SUPERSEDED","CORRECTED_REUPLOADED","SOURCE_LIMITED_RESTRICTED"}
ARTIFACT_STATES={"PUBLIC","RESTRICTED","EXPORT_CONTROLLED","DELETED","EXTERNAL","UNAVAILABLE","UNKNOWN"}
FAMILY_STATUSES={"ACTIVE","INACTIVE","ARCHIVED","CANCELLED","DELETED","UNKNOWN"}
RECEIPT_SEMANTICS={"CURRENT_ACTIVE","TERMINAL_CANCELLED","TERMINAL_ARCHIVED"}

@dataclass(frozen=True)
class Finding:
    code:str; severity:str; message:str; path:str|None=None

@dataclass(frozen=True)
class AuditResult:
    release_state:str; currentness_verdict:str; current_action_id:str|None; findings:tuple[Finding,...]
    def to_dict(self)->dict[str,Any]:
        return {"release_state":self.release_state,"currentness_verdict":self.currentness_verdict,"current_action_id":self.current_action_id,"findings":[asdict(x) for x in self.findings]}

def canonical_json(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def sha256_hex(value:bytes|str)->str:
    if isinstance(value,str): value=value.encode()
    return hashlib.sha256(value).hexdigest()

def history_set_digest(ids:Iterable[str])->str:
    return sha256_hex(canonical_json(sorted({str(x) for x in ids if str(x)})))

def parse_dt(value:Any)->datetime|None:
    if not isinstance(value,str) or not value: return None
    try: d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: return None
    return d.astimezone(timezone.utc) if d.tzinfo else None

def valid_sha256(value:Any)->bool:
    if not isinstance(value,str) or len(value)!=64: return False
    try: int(value,16); return True
    except ValueError: return False

def first_party_sam(url:Any)->bool:
    if not isinstance(url,str): return False
    try: p=urlparse(url)
    except ValueError: return False
    h=(p.hostname or "").lower()
    return p.scheme=="https" and (h=="sam.gov" or h.endswith(".sam.gov"))
