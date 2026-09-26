"""Compare a candidate provider record against CaptureBrief's reference record."""
from __future__ import annotations

from dataclasses import dataclass

from opportunity_record import OpportunityRecord, compare_records, controlling_source_readiness

@dataclass(frozen=True)
class ProviderComparison:
    status: str
    conflicts: tuple[str, ...]
    candidate_blockers: tuple[str, ...]

def compare_candidate(reference: OpportunityRecord, candidate: OpportunityRecord) -> ProviderComparison:
    conflicts=tuple(conflict.field for conflict in compare_records((reference,candidate)))
    readiness=controlling_source_readiness(candidate)
    if conflicts:
        status="conflict"
    elif readiness.eligible:
        status="controlling_eligible"
    else:
        status="compatible_discovery_only"
    return ProviderComparison(status,conflicts,readiness.blockers)
