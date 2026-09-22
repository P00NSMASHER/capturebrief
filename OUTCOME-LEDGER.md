# CaptureBrief Commercial Outcome Ledger

Updated: 2026-09-21

CaptureBrief's product decisions must follow observed customer evidence, not feature count or hypothetical ROI.

The outcome ledger is an **append-only, hash-chained event stream** implemented by `capturebrief_core/outcomes.py` on top of the existing evidence ledger.

## Why events instead of one mutable row

A real engagement changes over time:

`delivery -> payment -> buyer feedback -> repeat request -> possible later correction/retraction`

Later evidence must not erase earlier evidence. A refunded payment does not delete the original payment event. A later retraction does not delete the earlier buyer feedback. The summary derives the latest applicable commercial state while the full history remains inspectable.

## Allowed event types

### PAYMENT

Records only an explicit payment state:

- `PAID`
- `UNPAID`
- `REFUNDED`
- `UNKNOWN`

`PAID` and `REFUNDED` require an opaque evidence reference such as a processor receipt/payment identifier. Amount/currency are optional; if an amount is recorded, currency must be explicit.

A booked offer, checkout link, proposal, invoice, or stated intent is not a paid engagement.

### DELIVERY

Records:

- work start time;
- delivery time;
- delivery evidence reference.

Both times are timezone-aware. Turnaround is derived from these timestamps rather than manually entered.

### FEEDBACK

Records explicit buyer feedback only:

- usefulness: `USEFUL / NOT_USEFUL / UNKNOWN`;
- action effect:
  - `CHANGED_ACTION`
  - `CLOSED_COSTLY_UNCERTAINTY`
  - `CONFIRMED_EXISTING_VIEW`
  - `ALREADY_KNEW`
  - `FALSE_POSITIVE`
  - `NO_DECISION`
  - `UNKNOWN`
- whether the engagement was source-limited;
- finding classes used;
- evidence reference for the feedback.

There is no free-text notes field in the structured outcome event. Customer names, email addresses, contact details, and company names are prohibited.

### RETRACTION

Records a material correction after delivery without erasing the prior artifact.

Required:

- `CRITICAL / NONCRITICAL`;
- controlled reason code;
- evidence reference.

This makes product-quality problems visible instead of silently correcting the historical record.

### REPEAT_REQUEST

Records:

- `REQUESTED_REPEAT`
- `WOULD_REPEAT`
- `NO_REPEAT`
- `UNKNOWN`

Only an actual `REQUESTED_REPEAT` satisfies the current business-model condition that at least one customer ask for another pursuit or recurring coverage.

### EFFORT

Records actual operator time in whole minutes against one controlled fulfillment stage:

- `INTAKE_SCOPE`
- `HISTORY_CURRENT`
- `PACKET_BYTES`
- `REFERENCE_REVIEW`
- `ASSUMPTION_REVIEW`
- `RULE_REVIEW`
- `DEVIATION_REVIEW`
- `WATCH`
- `DELIVERY`
- `CUSTOMER_COMMS`
- `OTHER`

Each event requires an opaque `effort_evidence_ref` such as a timer/timesheet receipt. Events are additive; a later effort event never overwrites earlier labor.

This is internal operating evidence. It is not a customer ROI claim and does not imply that operator time is billable.

## Operator commands

Validate an event before writing:

    python -m capturebrief_core.cli outcome-validate outcome.json

Append an event:

    python -m capturebrief_core.cli outcome-append outcomes.jsonl outcome.json

Log fulfillment effort without hand-authoring JSON:

    python -m capturebrief_core.cli outcome-effort \
      outcomes.jsonl CB-CASE <CASE_SHA256> ASSUMPTION_REVIEW 35 timer:CB-CASE:review-1 \
      --event-at 2026-09-21T18:30:00Z

Generate the current evidence summary:

    python -m capturebrief_core.cli outcome-summary outcomes.jsonl

The append command refuses to write if the existing ledger fails hash-chain verification.

## Commercial proof summary

The summary reports evidence counts, not inferred business success:

- distinct engagements;
- current paid engagement count;
- recorded collected amount where supplied;
- delivered engagements;
- turnaround count / median / minimum / maximum;
- explicit usefulness labels;
- changed-action / uncertainty-closed / confirmation / already-knew / false-positive counts;
- source-limited engagements;
- requested-repeat / would-repeat / no-repeat counts;
- engagements with retractions;
- critical retractions;
- finding-class counts.

Refunded engagements are not counted as currently paid.

## Current pre-expansion evidence gates

The ledger exposes the factual parts of the business model's commercial proof threshold:

1. at least **3 current paid engagements**;
2. at least **1 explicit repeat request**;
3. at least **1 changed action or explicitly closed costly uncertainty**;
4. turnaround evidence exists;
5. operator-effort evidence exists;
6. every currently paid engagement has recorded effort before expansion economics are treated as complete.

It deliberately does **not** decide whether turnaround, effort, or the observed retraction rate is acceptable. Those thresholds require a human commercial/product decision with the raw counts visible.

Meeting the factual gates does not automatically:

- change the $149 price;
- create a subscription;
- make a sales forecast;
- claim product-market fit;
- authorize customer outreach;
- change the product scope.

## Claims CaptureBrief does not compute

The structured ledger explicitly does not calculate or infer:

- accuracy;
- probability of winning / PWin uplift;
- proposal savings;
- ROI;
- revenue uplift.

Those claims require evidence CaptureBrief does not currently possess.

## Privacy boundary

Outcome events contain pseudonymous case IDs and content hashes/opaque evidence references.

The schema rejects:

- email;
- company/customer/buyer names;
- contact names;
- phone/address fields;
- free-text notes;
- ROI/PWin/proposal-savings/revenue-uplift fields.

Raw payment documents and raw buyer feedback remain outside this ledger. Only a non-secret evidence reference belongs in the event.

## Corrections

Do not edit an old JSONL line.

Append a new event.

The hash chain exists specifically so silent historical mutation is detectable.

## Delivery-bound outcome evidence — 2026-09-21

Red-team testing showed that downstream commercial events could otherwise be counted without proving which delivered artifact they followed.

The ledger now enforces:

- one `case_id` cannot silently combine multiple `case_sha256` fingerprints;
- `DELIVERY`, `FEEDBACK`, `RETRACTION`, and `REPEAT_REQUEST` require a delivery-bundle SHA-256;
- feedback, retractions, and repeat requests count only when their bundle SHA matches an actual delivery for the same case and their event time is not before that delivery;
- post-delivery events that cannot be bound are excluded from commercial counts and surfaced as `unbound_outcome_events`;
- the factual pre-expansion evidence surface includes `outcome_binding_complete`.

This does not authenticate Stripe, an email, or a buyer merely from an opaque evidence reference. Those external records remain separate evidence. It prevents the structured summary from treating an unbound event as if it were proven customer outcome evidence.

