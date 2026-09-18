"""CaptureBrief's offline, deterministic evidence and document-coverage foundation.

This module does no network access, filesystem access, model execution, eligibility
determination, or delivery. Retrieved text is inert data, including instructions.
Only UTF-8 TXT and Markdown are supported. Document names never become paths.

Text-equivalent page accounting is deliberately conservative: split decoded text
on U+000C (form feed); each segment, including an empty segment, counts as at least
one page and otherwise ceil(number of Unicode code points / 4000). These are NOT
PDF/printed pages. The entire manifest is limited to ten files and 100 such pages.
Every listed document affects coverage, including documents marked optional.

Line numbers are one-based, columns are zero-based Unicode code-point indices,
and end columns are exclusive. Only LF separates lines; CR is preserved exactly.
No deadline or timezone is inferred. Missing timezone or competing deadline
wordings require review. A valid report still requires independent human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import ipaddress
import json
import math
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit


MAX_FILES = 10
MAX_TEXT_EQUIVALENT_PAGES = 100
CHARACTERS_PER_PAGE = 4000
_FORMATS = {"text/plain", "text/markdown"}


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON deterministically, rejecting non-JSON values and NaN/Infinity."""
    def check(item: Any) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list or type(item) is tuple:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ValueError("Only finite JSON values with string object keys are accepted")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def safe_source_url(value: str) -> str:
    """Validate an inert source identifier; this does NOT authorize fetching it.

    All queries and fragments are rejected so keys or signed URLs cannot enter
    reports. Callers must provide a public, credential-free canonical source URL.
    Production fetching additionally needs an independent allowlisted egress gate.
    """
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Source URL contains whitespace/control characters")
    if "\\" in value or any(ord(c) == 127 for c in value):
        raise ValueError("Unsafe source URL")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
        if (parts.scheme not in ("http", "https") or not host
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or "?" in value or "#" in value
                or "%" in parts.netloc):
            raise ValueError("Expected public HTTP(S) URL without credentials, query, or fragment")
        host.encode("ascii")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if ("." not in host or host.endswith((".localhost", ".local", ".internal"))
                    or not re.fullmatch(r"[A-Za-z0-9.-]+", host)):
                raise ValueError("Source host must be public")
        else:
            if not address.is_global:
                raise ValueError("Non-public source addresses are not accepted")
        if port is not None and port not in (80, 443):
            raise ValueError("Nonstandard source ports are not accepted")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Unsafe source URL") from exc
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", "", ""))


@dataclass(frozen=True)
class DocumentInput:
    document_id: str
    name: str
    source_url: str
    media_type: str
    content: bytes | None
    required: bool = True


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    name: str
    source_url: str
    media_type: str
    required: bool
    status: str
    content_sha256: str | None
    raw_content: bytes | None
    text: str | None
    text_equivalent_pages: int | None


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    source_url: str
    retrieved_at: str
    original_fields_json: str
    metadata_sha256: str
    documents: tuple[SourceDocument, ...]
    source_version: str
    coverage_blockers: tuple[str, ...]

    @property
    def coverage_complete(self) -> bool:
        return not self.coverage_blockers


@dataclass(frozen=True)
class EvidenceSpan:
    source_version: str
    document_id: str
    content_sha256: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    section: str | None
    quote: str


@dataclass(frozen=True)
class MaterialFinding:
    finding_id: str
    statement: str
    evidence: EvidenceSpan
    uncertainty: str = ""


@dataclass(frozen=True)
class DeadlineFinding:
    kind: str
    raw_wording: str
    evidence: EvidenceSpan
    timezone_wording: str | None = None
    precision: str = "unresolved"


@dataclass(frozen=True)
class ValidationResult:
    state: str
    blockers: tuple[str, ...]
    review_reasons: tuple[str, ...]
    material_findings: tuple[MaterialFinding, ...]
    deadlines: tuple[DeadlineFinding, ...]

    @property
    def evidence_valid(self) -> bool:
        return not self.blockers


def text_equivalent_pages(text: str) -> int:
    return sum(max(1, math.ceil(len(segment) / CHARACTERS_PER_PAGE))
               for segment in text.split("\f"))


def _parse_document(item: DocumentInput) -> SourceDocument:
    if not item.document_id or not isinstance(item.document_id, str):
        raise ValueError("Every document needs a nonempty identifier")
    if not isinstance(item.name, str) or not isinstance(item.media_type, str):
        raise ValueError("Document name and media type must be strings")
    if type(item.required) is not bool:
        raise ValueError("required must be a boolean")
    url = safe_source_url(item.source_url)
    raw = item.content
    if raw is not None and type(raw) is not bytes:
        raise ValueError("Document content must be immutable bytes or None")
    digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
    text = None
    pages = None
    if raw is None:
        status = "missing"
    elif item.media_type not in _FORMATS:
        status = "unsupported"
    else:
        try:
            text = raw.decode("utf-8", errors="strict")
            if "\x00" in text:
                raise UnicodeError("NUL content is not accepted as plain text")
        except UnicodeError:
            status = "unreadable"
            text = None
        else:
            pages = text_equivalent_pages(text)
            status = "parsed" if text.strip() else "empty"
    return SourceDocument(item.document_id, item.name, url, item.media_type,
                          item.required, status, digest, raw, text, pages)


def _manifest(documents: tuple[SourceDocument, ...]) -> list[dict[str, Any]]:
    return [{"document_id": d.document_id, "name": d.name, "source_url": d.source_url,
             "media_type": d.media_type, "required": d.required, "status": d.status,
             "content_sha256": d.content_sha256,
             "text_equivalent_pages": d.text_equivalent_pages} for d in documents]


def _version(source_id: str, source_url: str, retrieved_at: str,
             original_fields_json: str, documents: tuple[SourceDocument, ...]) -> str:
    return canonical_hash({"schema_version": 1, "source_id": source_id,
                           "source_url": source_url, "retrieved_at": retrieved_at,
                           "original_fields": json.loads(original_fields_json),
                           "manifest": _manifest(documents)})


def _coverage(documents: tuple[SourceDocument, ...]) -> tuple[str, ...]:
    blockers = []
    if not documents:
        blockers.append("empty_document_manifest")
    if len(documents) > MAX_FILES:
        blockers.append(f"file_limit_exceeded:{len(documents)}>{MAX_FILES}")
    for doc in documents:
        if doc.status != "parsed":
            blockers.append(f"document_{doc.status}:{doc.document_id}")
    pages = sum(doc.text_equivalent_pages or 0 for doc in documents)
    if pages > MAX_TEXT_EQUIVALENT_PAGES:
        blockers.append(f"text_equivalent_page_limit_exceeded:{pages}>{MAX_TEXT_EQUIVALENT_PAGES}")
    return tuple(blockers)


def build_snapshot(source_id: str, source_url: str, retrieved_at: str,
                   original_fields: Mapping[str, Any],
                   documents: Iterable[DocumentInput]) -> SourceSnapshot:
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("source_id must be a nonempty string")
    when = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("retrieved_at must contain an explicit timezone")
    url = safe_source_url(source_url)
    original_json = canonical_json_bytes(dict(original_fields)).decode("utf-8")
    parsed = tuple(_parse_document(doc) for doc in documents)
    ids = [doc.document_id for doc in parsed]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document identifiers are not accepted")
    return SourceSnapshot(source_id, url, retrieved_at, original_json,
                          hashlib.sha256(original_json.encode("utf-8")).hexdigest(),
                          parsed, _version(source_id, url, retrieved_at, original_json, parsed),
                          _coverage(parsed))


def snapshot_manifest(snapshot: SourceSnapshot) -> dict[str, Any]:
    return {"source_id": snapshot.source_id, "source_url": snapshot.source_url,
            "source_version": snapshot.source_version, "retrieved_at": snapshot.retrieved_at,
            "metadata_sha256": snapshot.metadata_sha256,
            "original_fields": json.loads(snapshot.original_fields_json),
            "documents": _manifest(snapshot.documents),
            "coverage_complete": snapshot.coverage_complete,
            "coverage_blockers": list(snapshot.coverage_blockers),
            "coverage_scope": "Caller-declared manifest only; remote completeness not established",
            "page_accounting": "Each formfeed segment: max(1, ceil(Unicode code points / 4000)); total <=100"}


def _document(snapshot: SourceSnapshot, document_id: str) -> SourceDocument:
    for doc in snapshot.documents:
        if doc.document_id == document_id:
            if doc.status != "parsed" or doc.text is None or not doc.content_sha256:
                raise ValueError("Cited document is not readable")
            return doc
    raise ValueError("Cited document is absent from current manifest")


def cite_lines(snapshot: SourceSnapshot, document_id: str, start_line: int,
               end_line: int | None = None, *, start_column: int = 0,
               end_column: int | None = None) -> EvidenceSpan:
    doc = _document(snapshot, document_id)
    lines = doc.text.split("\n")
    end_line = start_line if end_line is None else end_line
    if (type(start_line) is not int or type(end_line) is not int
            or not 1 <= start_line <= end_line <= len(lines)):
        raise ValueError("Invalid line range")
    end_column = len(lines[end_line - 1]) if end_column is None else end_column
    if (type(start_column) is not int or type(end_column) is not int
            or not 0 <= start_column <= len(lines[start_line - 1])
            or not 0 <= end_column <= len(lines[end_line - 1])
            or (start_line == end_line and start_column >= end_column)):
        raise ValueError("Invalid or empty column range")
    if start_line == end_line:
        quote = lines[start_line - 1][start_column:end_column]
    else:
        pieces = lines[start_line - 1:end_line]
        pieces[0] = pieces[0][start_column:]
        pieces[-1] = pieces[-1][:end_column]
        quote = "\n".join(pieces)
    if not quote.strip():
        raise ValueError("Evidence cannot be empty/whitespace")
    section = None
    if doc.media_type == "text/markdown":
        for line in lines[:start_line]:
            match = re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)\r?$", line)
            if match:
                section = match.group(1)
    return EvidenceSpan(snapshot.source_version, document_id, doc.content_sha256,
                        start_line, end_line, start_column, end_column, section, quote)


def validate_span(snapshot: SourceSnapshot, span: EvidenceSpan) -> tuple[str, ...]:
    errors = []
    if span.source_version != snapshot.source_version:
        errors.append("wrong_source_version")
    try:
        expected = cite_lines(snapshot, span.document_id, span.start_line, span.end_line,
                              start_column=span.start_column, end_column=span.end_column)
    except ValueError:
        errors.append("invalid_document_or_position")
    else:
        if span.content_sha256 != expected.content_sha256:
            errors.append("wrong_document_hash")
        if span.quote != expected.quote:
            errors.append("quote_position_mismatch")
        if span.section != expected.section:
            errors.append("section_mismatch")
    return tuple(errors)


def _integrity(snapshot: SourceSnapshot) -> tuple[str, ...]:
    try:
        rebuilt = build_snapshot(snapshot.source_id, snapshot.source_url, snapshot.retrieved_at,
                                 json.loads(snapshot.original_fields_json),
                                 [DocumentInput(d.document_id, d.name, d.source_url,
                                                d.media_type, d.raw_content, d.required)
                                  for d in snapshot.documents])
        return () if rebuilt == snapshot else ("source_snapshot_integrity_failure",)
    except (ValueError, TypeError, AttributeError):
        return ("source_snapshot_integrity_failure",)


def validate_report(snapshot: SourceSnapshot, findings: Iterable[MaterialFinding] = (),
                    deadlines: Iterable[DeadlineFinding] = ()) -> ValidationResult:
    findings, deadlines = tuple(findings), tuple(deadlines)
    blockers = list(_integrity(snapshot)) + list(_coverage(snapshot.documents))
    review = ["independent_human_review_required", "remote_manifest_completeness_unverified"]
    seen_ids = set()
    for finding in findings:
        if not finding.finding_id or finding.finding_id in seen_ids:
            blockers.append("missing_or_duplicate_finding_id")
        seen_ids.add(finding.finding_id)
        if not finding.statement.strip():
            blockers.append(f"empty_finding:{finding.finding_id}")
        for issue in validate_span(snapshot, finding.evidence):
            blockers.append(f"finding:{finding.finding_id}:{issue}")
    grouped: dict[str, set[str]] = {}
    for index, deadline in enumerate(deadlines):
        if deadline.kind not in {"submission", "questions", "registration"}:
            blockers.append(f"deadline:{index}:invalid_kind")
        for issue in validate_span(snapshot, deadline.evidence):
            blockers.append(f"deadline:{index}:{issue}")
        if not deadline.raw_wording.strip() or deadline.raw_wording not in deadline.evidence.quote:
            blockers.append(f"deadline:{index}:wording_not_in_evidence")
        if deadline.timezone_wording is None:
            review.append(f"deadline:{index}:timezone_unresolved")
        elif (not deadline.timezone_wording.strip()
              or deadline.timezone_wording not in deadline.raw_wording):
            blockers.append(f"deadline:{index}:timezone_not_in_raw_wording")
        if deadline.precision not in {"date", "minute", "second", "unresolved"}:
            blockers.append(f"deadline:{index}:invalid_precision")
        if deadline.precision == "unresolved":
            review.append(f"deadline:{index}:precision_unresolved")
        grouped.setdefault(deadline.kind, set()).add(deadline.raw_wording)
    for kind, wordings in grouped.items():
        if len(wordings) > 1:
            review.append(f"conflicting_or_multiple_deadline_wordings:{kind}")
    return ValidationResult("blocked_source" if blockers else "review_required",
                            tuple(dict.fromkeys(blockers)), tuple(dict.fromkeys(review)),
                            findings, deadlines)
