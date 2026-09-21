# CaptureBrief Product Core v0.2 — Evidence Acquisition + Packet Integrity

Updated: September 21, 2026

CaptureBrief remains a human-supervised, public-source Pursuit QA second pass. v0.2 upgrades the product from a release validator into an evidence-preserving case engine.

## Release contract

A case reaches `READY_FOR_HUMAN_RELEASE` only when all applicable gates pass:

1. current/terminal authority is supported by a fresh first-party receipt;
2. the observed action/version history is supported by a first-party history receipt;
3. every observed action has a successful, deletion-inclusive SAM resource-manifest receipt;
4. named or incorporated dependencies are semantically closed;
5. required public artifacts have verified SHA-256 byte receipts;
6. assumption evidence/action rules and timezone/source-integrity rules pass.

A caller-provided `manifest_complete: true` cannot override missing receipts.

## Evidence acquisition

The operator CLI can observe the public SAM web-interface resource manifest, preserve the raw payload and digest, normalize resource state, and append evidence to a hash-chained JSONL ledger.

The manifest client:
- sends no API key;
- requests deletion-inclusive state;
- retains raw response + SHA-256;
- distinguishes checked-empty from source failure;
- fails closed on response-shape drift;
- classifies public, deleted, restricted, export-controlled, unavailable, and external-link resources.

This SAM resource surface is treated as an undocumented web-UI interface and is monitored separately by a live canary rather than assumed to be a stable published API contract.

## Identity and history

CaptureBrief does not use filename as source identity. Resource ID, action identity, observation time, source state, and byte hash are retained independently.

Manifest diffs surface additions, disappearances after complete observations, explicit deletions, access restrictions, metadata changes, and same-filename replacement by a new resource ID.

## Public byte capture

Permitted public SAM file resources can be captured and hashed before historical bytes disappear. The downloader refuses external-link, restricted, or export-controlled resources and applies a maximum-byte limit.

Historical source-object identity and byte availability are separate claims. A required historical artifact whose source identity survives but whose bytes are unavailable remains fail-closed unless explicit source-backed supersession closes the dependency.

## Semantic reference closure

A complete attachment list is not automatically a complete decision packet. Named amendments, attachments, exhibits, drawings, schedules, and external systems referenced by controlling material must resolve to:

- a verified resource with verified hashed bytes;
- an explicit source-backed superseding resource; or
- an explicit external/restricted dependency with a reason.

Otherwise the reference remains unresolved and blocks packet completeness.

## Evidence ledger

Manifest and byte observations can be appended to a hash-chained JSONL ledger. Each record carries a payload SHA-256, previous-record SHA-256, and record SHA-256 so silent mutation of the 14-day evidence history is detectable.

## Change watch

The watch layer reopens only assumptions whose declared triggers match the actual change: current action, per-action manifest, resource ID, artifact bytes, or reference closure.

## CI

The deterministic Product Core workflow compiles the package, runs the regression corpus, validates the v0.2 releasable fixture, renders a sample brief, and exercises change detection. A separate SAM Manifest Canary monitors the live undocumented source surface without making deterministic CI depend on SAM availability.

## Remaining P0

The largest remaining gap is automated first-party history issuance. v0.2 can validate and preserve history evidence, but the production service still needs a hardened SAM History/Data Services ingestion path that automatically issues history receipts. After that, the next highest-value layer is conservative notice/document reference extraction with human confirmation.
