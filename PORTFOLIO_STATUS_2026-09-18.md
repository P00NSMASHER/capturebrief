# Portfolio Status — 2026-09-18

## Capacity contract
- CaptureBrief 40%
- PermitPlate 30%
- ScopeSignal validation 15%
- Invoice Maid + ChronosGuard reserve 10%
- Freight audit proof 5%

## CaptureBrief — ACTIVE / highest priority

Shipped on `portfolio/2026-09-18-program`:
- portfolio operating program;
- OSS provenance ledger with exact upstream pins;
- provider-neutral OpportunityRecord specification AND executable validation/comparison gate;
- verified backend snapshot record plus the complete verified release ZIP preserved in-branch;
- evidence/provenance module;
- source-request budget ledger;
- webhook signature boundary;
- source-budget + webhook regression tests;
- OpportunityRecord provenance/conflict tests.

Verified authoritative backend release:
- artifact SHA-256 `a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d`;
- 43 tests + 19 subtests pass locally on the original verified release.

New provider-boundary gate:
- 7/7 local tests pass;
- identity/deadline/set-aside/amendment unknowns must be explicit;
- critical facts require source provenance;
- unsafe source URLs fail closed;
- timezone gaps remain review items;
- conflicting provider facts surface instead of silently merging.

Offer-state check:
- current repository main advertises the $149 one-time founding pilot;
- verified entitlement release uses `pilot_149` at $149;
- no pricing mismatch patch is required.

Open P0:
- import the remaining verified entitlement/job-queue modules and their tests as normal source;
- run the complete suite from a clean repository checkout when a network-capable runner is available;
- only then evaluate external federal-data adapters behind OpportunityRecord.

## PermitPlate — ACTIVE / second priority

Shipped on `portfolio/project-signal-foundation`:
- ProjectSignal contract;
- deterministic fallback snapshot + migration warning;
- executable fail-closed identity/corroboration gate;
- cross-entity regression suite.

Recovered deterministic fallback:
- extracted Apps Script: 118,151 bytes;
- SHA-256 `8935F355A51AC3F438ABEED4F35D0EFACCC801D4771BEAD35DE848B336004843`;
- JavaScript syntax check passes;
- handoff reports 29/29 merged self-tests + 28/28 original regressions.

New corroboration gate:
- 7/7 local Node tests pass;
- same address alone never corroborates;
- KOKE / EASTHARLEM125 + M01329447-I1-style shared-site failure fails closed;
- contradictory same-namespace stable identifiers reject;
- shared building without entity linkage remains review;
- stronger corroboration requires an additional independent identity signal.

Blocker:
- fallback is NOT the later DOHMH + SLA + DOB production Venue Graph path;
- the isolated rule is fixed in deterministic code, but current production automation is not yet proven to route every join through it;
- current multi-source matching/scoring/state behavior still needs extraction from automation into versioned code;
- no second-jurisdiction work until full production-graph replay and subscriber P0 gates pass.

Permit OSS candidates are now pinned:
- nycaabs `149c27b6a42d3dc33f77be8e7c2b84dcc227239c`;
- Municipal-Permit-Scraper `427d27e4506cea91a969e3f2e2e0ddc49a379c21`;
- addressintel-mcp `e714e1451e80bdd64543ec3e374a5aa42f5681c7`;
- construction-lead-agent `6015b1c54d8a559eb5c54a93140bdeda3681537d`.

Municipal-Permit-Scraper note:
- actual LICENSE file is MIT;
- README badge says ISC;
- documentation inconsistency is recorded and no code is incorporated yet.

## ScopeSignal — VALIDATION ONLY

Pinned upstream:
`d470659a009e9944fd6c4a7969a903dfc28c443e`.

Shipped:
- validation protocol;
- standalone grounding harness.

Result:
- 4/4 local validation cases pass;
- fabricated contract evidence is rejected;
- ungrounded out-of-scope claims downgrade to review with confidence capped at 0.55;
- ambiguous cases remain review;
- no CRM/integrations/autonomous sending/full SaaS build.

Commercial validation remains the promotion gate.

## Invoice Maid + ChronosGuard — TECHNICAL RESERVE

Pinned:
- Invoice Maid `adc14c4c23c26b1b140066cdb0cb7119d5b227a4`;
- ChronosGuard `acce7bc3726aec19096bbb2f3ab78ae17eed5edb`.

Documented reserve abstractions:
- Document Intake Service;
- Temporal Evidence Engine.

Invoice Maid concrete module seams are recorded in `TECHNICAL_RESERVE.md`.
No standalone launch is scheduled.

## Freight audit — CHEAP PROOF

Implemented:
- deterministic Python audit engine;
- 4 regression tests, all passing;
- controlled synthetic example yields $451 of explainable discrepancies:
  - base-rate variance;
  - fuel-surcharge variance;
  - invalid demurrage;
  - unsupported accessorial.

Conservative behavior:
- duplicate billing is only a review candidate when BOL + carrier + total align;
- missing shipment/contract evidence fails to review instead of inventing expected charges.

Next gate:
- more controlled examples and false-positive testing before any UI or SaaS investment.

## Production safety
No production branch has been merged or deployed by this portfolio setup.
No paid spend was authorized.
No outbound sales email was sent.
