# Portfolio Program — 2026-09-18

## Mission
Run five workstreams as one portfolio, with unequal investment and explicit promotion/kill gates.

## Capacity allocation
- CaptureBrief — 40%
- PermitPlate — 30%
- ScopeSignal validation sprint — 15%
- Invoice Maid + ChronosGuard technical reserve — 10%
- Freight audit experiment — 5%

## Portfolio rules
1. CaptureBrief and PermitPlate outrank all new-product work until their current P0 reliability/deployment gates are closed.
2. No workstream earns more capacity because it is technically interesting; it earns capacity through reliability, customer evidence, or reusable leverage.
3. New SaaS surface area is deferred until the underlying engine is version-controlled, deterministic where practical, replay-tested, and source-provenanced.
4. Open-source reuse requires a provenance record, pinned source revision, license review, dependency review, and separation from proprietary business logic.
5. No paid spend or outbound outreach is authorized by this program document.
6. No second outbound email to a contact unless that contact has replied.
7. Experiments are time-boxed; weak evidence stops work.

## Current execution state

### Workstream A — CaptureBrief (40%)
Current product role: supervised, source-linked federal opportunity qualification / pursuit QA.

Immediate P0:
- Put the authoritative backend source into GitHub; the current public repo is primarily the static site.
- Preserve existing evidence, blocker/unknown, deadline/amendment, and source-provenance behavior with regression tests.
- Introduce a normalized OpportunityRecord boundary before importing external data providers.
- Add adapters for SAM.gov / USASpending only after the regression gate passes.

Target reusable architecture:
- Provider adapters -> OpportunityRecord -> proprietary CaptureBrief qualification/evidence engine -> human review -> customer output.
- Candidate open-source inputs: capture-mcp-server, rfp-map, simple-crm, federal-proposal-copilot.
- Do not turn CaptureBrief into generic proposal-writing software during this phase.

Promotion gate:
- materially lower human fulfillment time without increasing critical evidence/deadline/eligibility errors;
- retain source traceability;
- obtain credible paid/repeat demand before broad CRM expansion.

### Workstream B — PermitPlate (30%)
Current product role: source-linked NYC restaurant-opening intelligence; zero paid subscribers at the current checkpoint.

Immediate P0:
- Fix generalized cross-entity/cross-CAMIS corroboration suppression and replay the known false-match class.
- Bring the actual ETL/scoring/state engine into deterministic, versioned code in GitHub.
- Define subscriber-start/backlog semantics.
- Prove an end-to-end subscriber canary before geographic expansion.

Next architecture:
- Source adapters -> normalized ProjectSignal -> evidence/corroboration engine -> category-specific commercial opportunity mapping -> customer views/digests.
- NYC restaurant openings become one vertical view of a general permit/property-event engine.
- Expand NYC -> one second jurisdiction -> three only after the adapter/replay model is proven.

Promotion gate:
- false-match regression closed;
- second jurisdiction added without bespoke rewrite;
- leads are actionable to a buyer;
- paid evidence precedes broad national expansion.

### Workstream C — ScopeSignal validation sprint (15%)
Purpose: validate whether contract + new client request can reliably surface billable scope change.

MVP only:
- upload/paste contract or SOW;
- paste new client request;
- return IN SCOPE / POSSIBLE CHANGE ORDER;
- show supporting clause, reasoning, confidence;
- generate editable client response and change-order draft.

Explicitly deferred:
- CRM;
- autonomous email monitoring/sending;
- accounting suite;
- enterprise collaboration;
- deep integrations.

Promotion gate:
- users identify real missed billable work;
- at least one identified change order is considered useful enough to charge for or is actually approved.

### Workstream D — Invoice Maid + ChronosGuard reserve (10%)
Purpose: harvest reusable technical primitives, not launch two more businesses.

Invoice Maid extraction targets:
- mailbox/document ingestion;
- parsing/OCR;
- structured extraction;
- confidence/correction/audit trail;
- duplicate detection;
- tenant isolation;
- exports/webhooks.

ChronosGuard extraction targets:
- temporal source/version model;
- date-in-force retrieval;
- verified source quotations;
- tenant isolation/RLS;
- ingestion quarantine;
- prompt-injection defenses;
- evaluation and job-processing patterns.

Deliverables:
- Document Intake Service design;
- Temporal Evidence Engine design;
- provenance/dependency audit for each reused component.

Promotion gate:
- component is demonstrably reusable by at least one priority product or experiment.

### Workstream E — Freight audit experiment (5%)
Question: can the system produce defensible dollar discrepancies worth human review?

Initial rule set:
- duplicate invoice;
- wrong contracted rate;
- unsupported accessorial fee;
- demurrage/detention inconsistency.

Prototype output:
invoice amount, expected amount, difference, cause, evidence, confidence.

Promotion gate:
- credible detection on synthetic or legally usable samples;
- tolerable false-positive rate;
- discrepancy explanations are reviewable and source-linked.

## Shared program backlog
P0-1 CaptureBrief authoritative backend consolidation.
P0-2 PermitPlate authoritative pipeline consolidation + false-match replay.
P0-3 Open-source provenance/dependency ledger.
P1-1 CaptureBrief OpportunityRecord contract and provider adapter tests.
P1-2 PermitPlate ProjectSignal contract and commercial-category mapper.
P1-3 ScopeSignal three-screen validation prototype.
P2-1 Invoice Maid component extraction.
P2-2 ChronosGuard temporal evidence extraction.
P2-3 Freight audit rule-engine proof.

## Weekly portfolio review
Each workstream reports only:
- shipped;
- verified;
- blocked;
- customer/revenue evidence;
- reliability evidence;
- next highest-value action.

Capacity may move only when evidence changes.