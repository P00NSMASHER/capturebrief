"""Content-addressed FAR/DFARS/deviation source registry for CaptureBrief.

The registry preserves exact source snapshots and version metadata. It does not
select legal applicability. A newer source version is evidence that review may
be needed, not evidence that it governs a solicitation.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

SCHEMA_VERSION = "1.0"
RULE_NAMESPACES = {"FAR", "DFARS", "AGENCY_SUPPLEMENT", "CLASS_DEVIATION"}
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_CITATION_RE = re.compile(r"^\d{1,3}\.\d+(?:-\d+)?$")
_ENTITY_RE = re.compile(r"<!\s*ENTITY\b", re.I)
_DOCTYPE_ANY_RE = re.compile(r"<!DOCTYPE\b", re.I)
_GSA_DITA_DOCTYPE_RE = re.compile(
    r'<!DOCTYPE\s+dita\s+PUBLIC\s+"-//OASIS//DTD DITA Composite//EN"\s+"ditabase\.dtd"\s*>',
    re.I | re.S,
)
_EDITION_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b",
    re.I,
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _safe_https(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _prepare_gsa_dita_xml(dita_text: str) -> tuple[str, bool]:
    """Allow only GSA's known external OASIS DITA declaration, without resolving it."""
    if _ENTITY_RE.search(dita_text):
        raise ValueError("XML entity declarations are not accepted")
    doctypes = list(_DOCTYPE_ANY_RE.finditer(dita_text))
    if not doctypes:
        return dita_text, False
    allowed = _GSA_DITA_DOCTYPE_RE.search(dita_text)
    if allowed is None or len(doctypes) != 1 or allowed.start() != doctypes[0].start():
        raise ValueError("unrecognized DTD/DOCTYPE declaration")
    sanitized = dita_text[:allowed.start()] + dita_text[allowed.end():]
    if _DOCTYPE_ANY_RE.search(sanitized) or _ENTITY_RE.search(sanitized):
        raise ValueError("additional DTD/entity declarations are not accepted")
    return sanitized, True


def _embedded_rule_edition(root: ET.Element) -> tuple[str | None, str | None]:
    """Extract clause/provision month-year label from the rule heading when present."""
    for el in root.iter():
        if _local(el.tag) != "p":
            continue
        outputclass = str(el.attrib.get("outputclass") or "").lower()
        if "smcaps" not in outputclass:
            continue
        value = _clean_text(el)
        match = _EDITION_RE.search(value)
        if match:
            month = match.group(1).title()
            return f"{month} {match.group(2)}", str(el.attrib.get("id") or "")
    return None, None


def _validate_effective_dates(start: str | None, end: str | None) -> None:
    a, b = _date(start), _date(end)
    if start not in (None, "") and a is None:
        raise ValueError("effective_from must be an ISO date or null")
    if end not in (None, "") and b is None:
        raise ValueError("effective_until must be an ISO date or null")
    if a and b and b < a:
        raise ValueError("effective_until cannot precede effective_from")


def parse_gsa_dita(
    dita_text: str,
    *,
    namespace: str,
    agency: str,
    edition: str | None = None,
    source_repository: str,
    source_revision: str,
    source_path: str,
    source_url: str,
    observed_at: str,
    effective_from: str | None = None,
    effective_until: str | None = None,
) -> dict[str, Any]:
    """Normalize one pinned GSA FAR/DFARS DITA topic into an immutable rule source.

    Effective dates are never inferred from commit dates or publication order.
    If known, they must be supplied explicitly by a reviewer/source-specific
    process and remain separate from the Git revision and observed-at time.
    """
    namespace = str(namespace or "").upper()
    if namespace not in {"FAR", "DFARS"}:
        raise ValueError("GSA DITA parser accepts FAR or DFARS namespace")
    if not all(_text(v) for v in (agency, source_repository, source_path, dita_text)):
        raise ValueError("rule source identity, path, and DITA text are required")
    if not _COMMIT_RE.fullmatch(str(source_revision or "")):
        raise ValueError("source_revision must be a full 40-character Git commit")
    if not _safe_https(source_url):
        raise ValueError("source_url must be safe HTTPS")
    if _dt(observed_at) is None:
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    _validate_effective_dates(effective_from, effective_until)
    parse_text, standard_doctype_stripped = _prepare_gsa_dita_xml(dita_text)
    try:
        root = ET.fromstring(parse_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid DITA XML: {exc}") from exc

    title_el = next((e for e in root.iter() if _local(e.tag) == "title"), None)
    title = _clean_text(title_el) if title_el is not None else ""
    autonumber = None
    if title_el is not None:
        for el in title_el.iter():
            if _local(el.tag) == "ph" and "autonumber" in str(el.attrib.get("props") or "").lower():
                candidate = _clean_text(el)
                if _CITATION_RE.fullmatch(candidate):
                    autonumber = candidate
                    break
    if autonumber is None:
        match = re.search(r"\b(\d{1,3}\.\d+(?:-\d+)?)\b", title)
        autonumber = match.group(1) if match else None
    if autonumber is None or not _CITATION_RE.fullmatch(autonumber):
        raise ValueError("could not derive FAR/DFARS citation from DITA title")

    embedded_edition, embedded_edition_locator = _embedded_rule_edition(root)
    supplied_edition = edition.strip() if _text(edition) else None
    resolved_edition = embedded_edition or supplied_edition
    if resolved_edition is None:
        raise ValueError("rule edition must be embedded in rule text or supplied as a source label")
    edition_basis = "EMBEDDED_RULE_TEXT" if embedded_edition else "OPERATOR_SOURCE_LABEL"
    source_snapshot_label = (
        supplied_edition
        if embedded_edition and supplied_edition and supplied_edition != embedded_edition
        else None
    )

    paragraphs: list[dict[str, Any]] = []
    for el in root.iter():
        if _local(el.tag) != "p":
            continue
        value = _clean_text(el)
        if not value:
            continue
        locator = str(el.attrib.get("id") or f"p{len(paragraphs)+1}")
        paragraphs.append({
            "line": len(paragraphs) + 2,
            "locator": locator,
            "text": value,
            "text_sha256": digest(value),
        })
    if not paragraphs:
        raise ValueError("DITA topic contains no usable paragraph text")

    normalized_lines = [f"{autonumber} {title[len(autonumber):].strip()}" if title.startswith(autonumber) else title]
    normalized_lines.extend(f"[{p['locator']}] {p['text']}" for p in paragraphs)
    normalized_text = "\n".join(normalized_lines).strip()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "namespace": namespace,
        "citation": autonumber,
        "rule_key": f"{namespace}:{agency}:{autonumber}",
        "agency": agency,
        "edition": resolved_edition,
        "edition_basis": edition_basis,
        "embedded_edition_locator": embedded_edition_locator,
        "source_snapshot_label": source_snapshot_label,
        "standard_doctype_stripped": standard_doctype_stripped,
        "title": title,
        "source_kind": "GSA_DITA",
        "source_repository": source_repository,
        "source_revision": source_revision,
        "source_path": source_path,
        "source_url": source_url,
        "observed_at": observed_at,
        "effective_from": effective_from,
        "effective_until": effective_until,
        "effective_date_authority": "EXPLICIT_REVIEWED_SOURCE" if effective_from or effective_until else "UNKNOWN",
        "source_sha256": digest(dita_text),
        "normalized_text_sha256": digest(normalized_text),
        "text": normalized_text,
        "paragraphs": paragraphs,
        "applicability_authoritative": False,
        "currentness_authoritative": False,
    }
    return {"rule_source_id": "RULESRC:" + digest(canonical(payload)), **payload}


def validate_rule_source(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if record.get("namespace") not in RULE_NAMESPACES:
        errors.append("namespace")
    if not _CITATION_RE.fullmatch(str(record.get("citation") or "")):
        errors.append("citation")
    if not all(_text(record.get(k)) for k in ("agency", "edition", "title", "source_repository", "source_path", "text")):
        errors.append("required_text")
    if not _COMMIT_RE.fullmatch(str(record.get("source_revision") or "")):
        errors.append("source_revision")
    if not _safe_https(record.get("source_url")):
        errors.append("source_url")
    if _dt(record.get("observed_at")) is None:
        errors.append("observed_at")
    if not _SHA_RE.fullmatch(str(record.get("source_sha256") or "")):
        errors.append("source_sha256")
    if digest(str(record.get("text") or "")) != record.get("normalized_text_sha256"):
        errors.append("normalized_text_sha256")
    _validate_effective_dates(record.get("effective_from"), record.get("effective_until"))
    payload = {k: v for k, v in record.items() if k != "rule_source_id"}
    if record.get("rule_source_id") != "RULESRC:" + digest(canonical(payload)):
        errors.append("rule_source_id")
    expected_key = f"{record.get('namespace')}:{record.get('agency')}:{record.get('citation')}"
    if record.get("rule_key") != expected_key:
        errors.append("rule_key")
    if record.get("applicability_authoritative") is not False:
        errors.append("applicability_authoritative")
    return sorted(set(errors))


def init_registry(path: str | Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS rule_versions (
          rule_source_id TEXT PRIMARY KEY,
          rule_key TEXT NOT NULL,
          namespace TEXT NOT NULL,
          citation TEXT NOT NULL,
          agency TEXT NOT NULL,
          edition TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          source_revision TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          normalized_text_sha256 TEXT NOT NULL,
          payload_json TEXT NOT NULL
        )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_rule_versions_key ON rule_versions(rule_key, observed_at, edition)")
        db.commit()


def add_rule_version(path: str | Path, record: dict[str, Any]) -> str:
    errors = validate_rule_source(record)
    if errors:
        raise ValueError("invalid rule source: " + ",".join(errors))
    init_registry(path)
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT payload_json FROM rule_versions WHERE rule_source_id=?", (record["rule_source_id"],)).fetchone()
        if row:
            if row[0] != payload:
                raise ValueError("content-addressed rule source collision")
            return "EXISTS"
        db.execute(
            "INSERT INTO rule_versions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (record["rule_source_id"], record["rule_key"], record["namespace"], record["citation"], record["agency"], record["edition"], record["observed_at"], record["source_revision"], record["source_sha256"], record["normalized_text_sha256"], payload),
        )
        db.commit()
    return "INSERTED"


def get_rule_version(path: str | Path, rule_source_id: str) -> dict[str, Any] | None:
    """Return one exact content-addressed rule source without falling back to latest."""
    if not isinstance(rule_source_id, str) or not rule_source_id.startswith("RULESRC:"):
        raise ValueError("rule_source_id must be a content-addressed RULESRC identifier")
    init_registry(path)
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT payload_json FROM rule_versions WHERE rule_source_id=?",
            (rule_source_id,),
        ).fetchone()
    if row is None:
        return None
    value = json.loads(row[0])
    errors = validate_rule_source(value)
    if errors:
        raise ValueError("stored rule source failed validation: " + ",".join(errors))
    return value


def list_rule_versions(path: str | Path, *, rule_key: str | None = None, namespace: str | None = None, citation: str | None = None, agency: str | None = None) -> list[dict[str, Any]]:
    init_registry(path)
    clauses: list[str] = []
    values: list[Any] = []
    for column, value in (("rule_key", rule_key), ("namespace", namespace), ("citation", citation), ("agency", agency)):
        if value is not None:
            clauses.append(f"{column}=?")
            values.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT payload_json FROM rule_versions" + where + " ORDER BY observed_at, edition, rule_source_id", values).fetchall()
    return [json.loads(row[0]) for row in rows]


def diff_rule_versions(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before.get("rule_key") != after.get("rule_key"):
        raise ValueError("rule versions must share the same rule_key")
    old = str(before.get("text") or "").splitlines()
    new = str(after.get("text") or "").splitlines()
    patch = list(difflib.unified_diff(old, new, fromfile=str(before.get("edition")), tofile=str(after.get("edition")), lineterm=""))
    return {
        "rule_key": before.get("rule_key"),
        "from_rule_source_id": before.get("rule_source_id"),
        "to_rule_source_id": after.get("rule_source_id"),
        "from_edition": before.get("edition"),
        "to_edition": after.get("edition"),
        "changed": bool(patch),
        "diff": patch[:500],
        "review_required": bool(patch),
        "automatic_applicability_change": False,
    }


def parse_deviation_manifest(csv_text: str, *, source_repository: str, source_revision: str, observed_at: str) -> dict[str, Any]:
    if not _COMMIT_RE.fullmatch(str(source_revision or "")):
        raise ValueError("source_revision must be a full Git commit")
    if _dt(observed_at) is None:
        raise ValueError("observed_at must be timezone-aware")
    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"on_disk_filename", "url_hash", "original_filename", "agency", "part_number", "is_dod", "source_url", "pdf_size_bytes"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("deviation manifest missing required columns")
    rows: list[dict[str, Any]] = []
    for n, row in enumerate(reader, start=2):
        if not any(str(v or "").strip() for v in row.values()):
            continue
        if not _text(row.get("agency")) or not _text(row.get("original_filename")) or not _safe_https(row.get("source_url")):
            raise ValueError(f"invalid deviation manifest row {n}")
        if not re.fullmatch(r"[0-9a-f]{16}", str(row.get("url_hash") or "")):
            raise ValueError(f"invalid deviation url_hash row {n}")
        source_url=str(row.get("source_url") or "").strip()
        if row.get("url_hash") != digest(source_url)[:16]:
            raise ValueError(f"deviation url_hash/source_url mismatch row {n}")
        try:
            size = int(str(row.get("pdf_size_bytes") or ""))
            part = int(str(row.get("part_number") or ""))
            is_dod = int(str(row.get("is_dod") or ""))
        except ValueError as exc:
            raise ValueError(f"invalid numeric deviation fields row {n}") from exc
        if size <= 0 or part < -1 or part > 53 or is_dod not in (0, 1):
            raise ValueError(f"invalid deviation values row {n}")
        payload = {
            "agency": row["agency"].strip(),
            "part_number": part,
            "is_dod": bool(is_dod),
            "original_filename": row["original_filename"].strip(),
            "on_disk_filename": str(row.get("on_disk_filename") or "").strip(),
            "url_hash": row["url_hash"],
            "source_url": row["source_url"].strip(),
            "pdf_size_bytes": size,
            "source_repository": source_repository,
            "source_revision": source_revision,
            "observed_at": observed_at,
            "applicability_authoritative": False,
            "effective_date_authoritative": False,
        }
        rows.append({"deviation_source_id": "DEVSRC:" + digest(canonical(payload)), **payload})
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": digest(csv_text),
        "source_repository": source_repository,
        "source_revision": source_revision,
        "observed_at": observed_at,
        "row_count": len(rows),
        "rows": rows,
    }


def filter_deviation_sources(manifest: dict[str, Any], *, agency: str | None = None, part_number: int | None = None, is_dod: bool | None = None) -> list[dict[str, Any]]:
    out = []
    for row in manifest.get("rows") or []:
        if agency is not None and str(row.get("agency")).casefold() != agency.casefold():
            continue
        if part_number is not None and row.get("part_number") != part_number:
            continue
        if is_dod is not None and row.get("is_dod") is not is_dod:
            continue
        out.append(row)
    return out


def to_trace_source_snapshot(record: dict[str, Any], *, source_id: str, reviewer: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a CaptureBrief source-manifest row + Decision Evidence snapshot.

    This function does not create an applicability decision. It only makes a
    reviewed normalized rule source available to a later decision-trace review.
    """
    errors = validate_rule_source(record)
    if errors:
        raise ValueError("invalid rule source: " + ",".join(errors))
    if not _text(source_id) or not _text(reviewer):
        raise ValueError("source_id and reviewer are required")
    from .decision_trace import freeze_text_snapshot
    source = {
        "source_id": source_id,
        "title": record["title"],
        "authority": "SUPPORTING",
        "artifact_state": "PUBLIC",
        "url": record["source_url"],
        "observed_at": record["observed_at"],
        "content_sha256": record["source_sha256"],
    }
    snap = freeze_text_snapshot(
        source=source,
        source_key=record["rule_key"],
        kind="RULE",
        version_label=record["edition"],
        text=record["text"],
        capture_method="REVIEWED_EXTRACTION",
        captured_by=reviewer,
        mapping_note=f"Normalized from {record['source_repository']}:{record['source_path']} at {record['source_revision']}; raw source SHA-256 retained separately.",
        published_at=None,
    )
    return source, snap


def load_source_catalog(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != SCHEMA_VERSION or not isinstance(value.get("sources"), list):
        raise ValueError("invalid rule source catalog")
    for item in value["sources"]:
        if item.get("namespace") not in RULE_NAMESPACES:
            raise ValueError("catalog namespace invalid")
        if not _text(item.get("repository")) or not _COMMIT_RE.fullmatch(str(item.get("revision") or "")):
            raise ValueError("catalog repository/revision invalid")
        if not _safe_https(item.get("repository_url")):
            raise ValueError("catalog repository URL invalid")
    return value
