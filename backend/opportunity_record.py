"""Provider-neutral CaptureBrief opportunity record and comparison gate.

External providers may supply facts, but may not produce pursue/hold/pass. Critical
fields retain source provenance, unknowns remain explicit, and provider conflicts
are surfaced rather than silently reconciled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def safe_public_url(value: str) -> str:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("source URL contains whitespace/control characters")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("source URL must be HTTP(S)")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("source URL must not contain credentials, query, or fragment")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", "", ""))


@dataclass(frozen=True)
class SourceRef:
    source: str
    url: str
    retrieved_at: str
    content_sha256: str | None = None

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.source.strip():
            errors.append("empty_source_name")
        try:
            safe_public_url(self.url)
        except ValueError:
            errors.append("unsafe_source_url")
        try:
            instant = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError
        except (ValueError, TypeError):
            errors.append("retrieved_at_requires_timezone")
        if self.content_sha256 is not None and not _SHA256.fullmatch(self.content_sha256):
            errors.append("invalid_content_sha256")
        return tuple(errors)


@dataclass(frozen=True)
class DeadlineFact:
    raw_wording: str
    normalized_value: str | None
    timezone_wording: str | None
    source: SourceRef


@dataclass(frozen=True)
class OpportunityRecord:
    provider: str
    opportunity_id: str | None = None
    notice_id: str | None = None
    solicitation_number: str | None = None
    title: str | None = None
    agency: str | None = None
    office: str | None = None
    notice_type: str | None = None
    naics: tuple[str, ...] = ()
    psc: tuple[str, ...] = ()
    set_aside: str | None = None
    place_of_performance: str | None = None
    posted_at: str | None = None
    response_deadline: DeadlineFact | None = None
    amendment_ids: tuple[str, ...] = ()
    attachment_ids: tuple[str, ...] = ()
    award_history_ids: tuple[str, ...] = ()
    field_sources: Mapping[str, SourceRef] = field(default_factory=dict)
    source_manifest: tuple[SourceRef, ...] = ()
    explicit_unknowns: frozenset[str] = frozenset()
    provider_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    blockers: tuple[str, ...]
    review_reasons: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class ProviderConflict:
    field: str
    values: tuple[tuple[str, str], ...]


def validate_record(record: OpportunityRecord) -> ValidationResult:
    blockers: list[str] = []
    review: list[str] = []
    if not record.provider.strip():
        blockers.append("missing_provider")
    if not (record.notice_id or record.solicitation_number):
        if "identity" not in record.explicit_unknowns:
            blockers.append("critical_unknown_not_declared:identity")
        else:
            review.append("identity_unknown")
    if not record.source_manifest:
        blockers.append("empty_source_manifest")
    for index, source in enumerate(record.source_manifest):
        blockers.extend(f"source_manifest:{index}:{error}" for error in source.validate())

    deadline = record.response_deadline
    if deadline is None:
        if "response_deadline" not in record.explicit_unknowns:
            blockers.append("critical_unknown_not_declared:response_deadline")
        else:
            review.append("response_deadline_unknown")
    else:
        if not deadline.raw_wording.strip():
            blockers.append("deadline_raw_wording_missing")
        for error in deadline.source.validate():
            blockers.append(f"deadline_source:{error}")
        if deadline.timezone_wording is None:
            review.append("response_deadline_timezone_unresolved")
        if "response_deadline" not in record.field_sources:
            blockers.append("critical_field_missing_provenance:response_deadline")

    for field_name, value in (("set_aside", record.set_aside), ("amendments", record.amendment_ids)):
        missing = value is None if field_name == "set_aside" else len(value) == 0
        if missing and field_name not in record.explicit_unknowns:
            blockers.append(f"critical_unknown_not_declared:{field_name}")
        elif missing:
            review.append(f"{field_name}_unknown")
        elif field_name not in record.field_sources:
            blockers.append(f"critical_field_missing_provenance:{field_name}")

    if (record.notice_id or record.solicitation_number) and "identity" not in record.field_sources:
        blockers.append("critical_field_missing_provenance:identity")

    for field_name, source in record.field_sources.items():
        for error in source.validate():
            blockers.append(f"field_source:{field_name}:{error}")

    return ValidationResult(tuple(dict.fromkeys(blockers)), tuple(dict.fromkeys(review)))


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(str(value).split()).strip().upper()
    return value or None


def compare_records(records: Iterable[OpportunityRecord]) -> tuple[ProviderConflict, ...]:
    records = tuple(records)
    conflicts: list[ProviderConflict] = []

    identity_values: list[tuple[str, str]] = []
    for record in records:
        value = _norm(record.notice_id or record.solicitation_number)
        if value:
            identity_values.append((record.provider, value))
    if len({v for _, v in identity_values}) > 1:
        conflicts.append(ProviderConflict("identity", tuple(identity_values)))

    deadline_values: list[tuple[str, str]] = []
    for record in records:
        if record.response_deadline and record.response_deadline.normalized_value:
            deadline_values.append((record.provider, record.response_deadline.normalized_value))
    if len({v for _, v in deadline_values}) > 1:
        conflicts.append(ProviderConflict("response_deadline", tuple(deadline_values)))

    set_aside_values = [(r.provider, v) for r in records if (v := _norm(r.set_aside))]
    if len({v for _, v in set_aside_values}) > 1:
        conflicts.append(ProviderConflict("set_aside", tuple(set_aside_values)))

    amendment_values = [(r.provider, "|".join(sorted(r.amendment_ids))) for r in records if r.amendment_ids]
    if len({v for _, v in amendment_values}) > 1:
        conflicts.append(ProviderConflict("amendments", tuple(amendment_values)))

    return tuple(conflicts)
