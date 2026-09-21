# CaptureBrief Product Core v0.1

CaptureBrief is a human-supervised, public-source Pursuit QA second pass. This package turns the product methodology into executable release gates so a buyer-facing brief cannot silently outrun its evidence.

## What is now enforced

- Current-action authority is status-aware. Active, cancelled, archived, inactive, deleted, and unknown families do not share the same semantics.
- Action IDs are treated as opaque. Row order and lexical sorting cannot decide currentness.
- A green authority receipt must be fresh, first-party, history-member-bound, and payload-hash verified.
- Public history completeness and attachment/resource manifest completeness are separate release gates.
- Public packet artifacts require immutable SHA-256 evidence when treated as accounted-for.
- Restricted, export-controlled, unavailable, or unknown evidence safe-stops rather than becoming a resolved public-source conclusion.
- UNPROVEN and SOURCE_LIMITED facts cannot masquerade as resolved gate-changing facts.
- Decision-changing items require a concrete next action plus an owner or evidence request.
- The default buyer handoff is capped at five GATE_CHANGING or VERIFY_NOW items.
- Deadlines require timezone-aware timestamps.
- Change watch reopens only assumptions whose declared triggers match the source change.

## Commands

    python -m capturebrief_core.cli validate fixtures/ready_case.json
    python -m capturebrief_core.cli render fixtures/ready_case.json -o brief.md
    python -m capturebrief_core.cli diff fixtures/ready_case.json fixtures/changed_case.json

A blocked validation exits with status 2, so fulfillment or CI can prevent release.

## Deliberate boundary

This core does not automate proposal writing, PWin scoring, bid submission, or protected-portal access. The next production layer should issue these receipts from first-party SAM observations, retain exact source snapshots and hashes, and preserve explicit restricted/external dependencies. Until that issuer exists, this core still adds value by preventing incomplete or contradictory evidence from being released as a confident customer conclusion.
