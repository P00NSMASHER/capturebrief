# CaptureBrief — Assumption source / rule / version history

Updated: September 21, 2026. Trace contract: `1.0`.

## What the buyer receives

For each of up to five bid assumptions, CaptureBrief retains the exact supporting or contradicting passage, source version and content hash; any relevant dated rule and alternate/deviation; the pursuit-specific evidence for applicability; the documented amendment/correction chain; the reviewed conclusion, owner and next action. Later dependency changes reopen the affected assumption for human review. They do not silently rewrite the customer's decision.

The $149 one-pursuit offer, public/non-sensitive boundary, concise handoff, 14-day public-source change watch and no automatic renewal are unchanged. This implementation adds no scheduled task, customer message, billing event or autonomous bid decision.

## Integrated workflow

The existing `case-from-intake` command now initializes `evidence_profile=ASSUMPTION_SOURCE_RULE_HISTORY_V1` and pending trace entries. Nothing is marked supported or reviewed by the initializer. The existing work queue adds human-review tasks for missing passages, versions, rule applicability, history and review receipts.

The existing `validate` command composes both independent gates: the prior packet/current-action/history/manifest/reference checks AND assumption-level trace checks. The existing `render` command includes the detailed history in the forensic appendix. The existing `diff` command combines packet events with source/rule dependency changes and deduplicates reopened assumptions.

Existing packet implementations are preserved byte-for-byte in `packet_audit.py`, `packet_render.py`, `packet_watch.py`, `packet_workqueue.py` and `base_intake.py`. Public entry points compose the new trace layer over those implementations. Legacy cases remain readable but explicitly say that exact assumption history was not collected; they are not silently upgraded or retroactively approved.

## Evidence model

Sources use unique immutable version IDs, `version_label`, HTTPS source URL, observation timestamp and `content_sha256`. Do not overwrite an older source object with new bytes. A citation binds `source_id`, `content_sha256`, exact `locator`, exact `quote`, and a role (CONTROLLING, CONTRADICTING, SUPPORTING, HISTORICAL).

Rule versions retain namespace (FAR, DFARS, AGENCY_SUPPLEMENT, CLASS_DEVIATION, SOLICITATION_RULE), rule citation, dated/version label, explicit alternate, deviation ID when applicable, nullable effective date, and a source citation. A Git commit or collection date does not substitute for the rule's version/effective date.

Each assumption explicitly records LINKED, NOT_RULE_DEPENDENT or UNRESOLVED plus the reason. Rule bindings state APPLIES, DOES_NOT_APPLY or UNRESOLVED and cite the controlling pursuit passage for that applicability judgement. A newer published rule is NOT automatically adopted. Missing exact effective days remain null rather than being fabricated from a month/year label.

Source changes use AMENDS, REPLACES, CORRECTS or WITHDRAWS, retain both source versions, identify the exact affected scope, and cite the evidence establishing the change. Source graphs with cycles, missing predecessors or missing source hashes cannot support a complete resolved history. A later source can amend only part of a document; this schema does not impose a universal 'newest document wins' hierarchy.

History review is REVIEWED, SOURCE_LIMITED or PENDING. SOURCE_LIMITED can be documented as an unknown/VERIFY_NOW item, but cannot prove a resolved conclusion. Every trace requires a named and dated HUMAN_REVIEW record bound to the exact dependency-input fingerprint. Hashes provide integrity, not independent human review, publisher authentication or legal advice. The code checks quoted-text membership when an explicit hashed `text_snapshot` is supplied; otherwise exact-passage accuracy remains a documented human-review responsibility. A text snapshot is an extraction artifact, not proof that a PDF extraction was correct.

## Operator commands

Keep cases and source snapshots in the approved private fulfillment environment, not the public website repository. The fixture corpus contains synthetic data only.

```
python -m capturebrief_core.decision_trace initialize case.json --decision-at 2026-09-21T15:00:00Z -o traced-case.json
python -m capturebrief_core.decision_trace review-input traced-case.json --assumption-id A1
python -m capturebrief_core.decision_trace validate traced-case.json
python -m capturebrief_core.cli validate traced-case.json
python -m capturebrief_core.cli render traced-case.json -o buyer-brief.md
python -m capturebrief_core.cli diff prior-case.json traced-case.json
python -m capturebrief_core.cli ledger-append case-ledger.jsonl REVIEWED_DECISION_SNAPSHOT traced-case.json
python -m capturebrief_core.cli ledger-verify case-ledger.jsonl
```

`review-input` only calculates the fingerprint and returns `review_performed=false`. A reviewer must inspect the actual sources/applicability/history before recording their identity, time and fingerprint. Retain the earlier case in the append-only ledger before saving subsequent decisions. The local ledger is tamper-evident, not an externally notarized immutable store.

Advance `decision_at` to the actual review snapshot after acquiring evidence. Source observations after that time are rejected, preventing future evidence from being portrayed as known at an earlier decision. Recalculate and independently review the new fingerprint after material changes. A new rule with no binding to an assumption does not reopen that assumption merely because it is newer. Removing old bindings cannot conceal a changed dependency.

`decision_trace validate` validates only the trace and explicitly returns `case_release_authorized=false`; it never replaces the full product release gate. Missing trace data in a legacy case returns NOT_COLLECTED rather than a green history claim.

## Source rationale

The design is informed by official FAR 52.101(f), which requires operative clause/provision/alternate dates; FAR 1.108(d), which distinguishes rule effective dates and application to solicitations/contracts; and FAR 15.206, which describes solicitation amendments and their change-identification information. These are design references, not a legal applicability determination for any customer pursuit.

- https://www.acquisition.gov/far/52.101
- https://www.acquisition.gov/far/1.108
- https://www.acquisition.gov/far/15.206

No full FAR/DFARS corpus, automatic legal rule selector, private-portal reader, or live customer evidence is introduced by this change. The approved-source acquisition boundaries in PRODUCT-CORE.md and SOURCE-POLICY.md remain in force.

## Validation

The new synthetic regression corpus tests source/hash/quote binding, old-version retention, rule date identity, explicit applicability, unknown handling, review invalidation, future-evidence rejection, cycle detection, missing predecessors, and targeted reopen behavior. Integration tests exercise the real audit, render, intake, work queue and watch entry points. A passing synthetic test does not establish accuracy on customer solicitations or completed customer fulfillment.
