# CaptureBrief Business Model v6 — Evidence-Linked Pursuit Control

> **Superseded:** Current product/commercial model is `BUSINESS-MODEL-v7.md` (2026-09-21). This file is retained for decision history.

Updated: September 19, 2026

## Wedge

CaptureBrief is an outside, human-supervised **Pursuit QA second pass** for small federal IT / cyber / cloud contractors that already have a live pursuit and an internal gate posture.

It does not compete on opportunity discovery, PWin scoring, proposal generation, submission, or generic RFP summarization. Those categories are already crowded. CaptureBrief attacks the narrower failure mode: **a team starts expensive proposal work while one or more assumptions behind the gate decision are stale, unsupported, source-limited, or tied to the wrong controlling source.**

## Current buyer

Small federal technology contractors with:
- an active capture / proposal workload,
- limited bandwidth for a second independent review,
- enough process maturity to have a GO / HOLD / NO-GO / UNSURE posture,
- public-source pursuits that can be checked without restricted portal material.

## Current offer — unchanged

- $149 one-time founding pilot
- one selected public federal IT / cyber / cloud pursuit
- current posture + up to five non-sensitive assumptions
- outside adversarial QA pass
- inspectable evidence / reasoning appendix
- 14-day public-source change watch
- no automatic renewal

Do not change pricing or expand to subscriptions until paid usage and repeat demand justify it.

## Product unit: the Pursuit QA Case

Each engagement is a small evidence-linked case, not a long report.

### 1. Source manifest
Every relevant source is tagged as:
- controlling/current,
- supporting,
- historical/superseded,
- corrected/reuploaded,
- source-limited/restricted.

### 2. Assumption register
The customer supplies the assumptions they are actually relying on.

Evidence state is one of:
- SUPPORTED
- CONTRADICTED
- UNPROVEN
- SUPERSEDED
- SOURCE-LIMITED

### 3. Decision class
Evidence state is not the same thing as business impact.

Retained items are classified as:
- **GATE-CHANGING** — can change posture, eligibility, submission path, timing, or immediate proposal work.
- **VERIFY-NOW** — a decision-changing unknown with a specific evidence request or owner/action.
- **MONITOR-ONLY** — useful context or confirmation that does not change the current action.

Only GATE-CHANGING and VERIFY-NOW items compete for the default five-item / ~90-second handoff.

### 4. Action ledger
Each retained decision-changing item carries:
- source lineage,
- assertion state,
- decision class,
- owner or evidence request,
- next action,
- deadline/timezone where relevant,
- reopen trigger.

### 5. Change watch
The 14-day watch does not create generic “new amendment” alerts. A material public-source change reopens only the case items it can affect.

## Fail-closed rules

CaptureBrief stops or labels an item SOURCE-LIMITED when:
- the controlling source cannot be established,
- the public copy is incomplete or contradictory,
- the authoritative package is restricted to a contract-holder/private portal,
- a company-specific eligibility fact cannot be established from public evidence,
- a critical source is unreadable or unavailable.

Unknown is not failure. Unknown is a request for evidence.

## Versioned QA rules

Rules should be versioned so a later policy/source-handling improvement does not silently rewrite old work. Initial rule families:
- controlling-action / supersession logic,
- corrected-attachment lineage,
- deadline + source-timezone preservation,
- pool / vehicle / child-call scope,
- source-limited and restricted-source safe-stop,
- critical-item second-pass verification,
- action-changing vs monitor-only classification.

## Customer-facing artifact

Default view:
1. current posture,
2. up to five decision-changing items,
3. evidence state,
4. decision class,
5. owner / next action.

Forensic appendix:
- source manifest,
- exact public references,
- assertion history,
- source limitations,
- change log / reopened items.

The product should feel like a QA control surface, not a generated report.

## Outcome ledger — internal product learning

Track explicit buyer feedback only:
- paid / unpaid,
- useful / not useful,
- changed action / confirmed existing view / already knew / false positive,
- source-limited,
- time to delivery,
- which finding classes were used,
- repeat request.

Do not invent “accuracy,” PWin uplift, proposal savings, or ROI before labeled customer evidence exists.

## Commercial proof threshold before expansion

Remain a one-time founding pilot until real evidence shows:
- at least 3 paid engagements,
- acceptable turnaround without founder overload,
- low critical-error / retraction rate,
- at least one customer asks for another pursuit or recurring coverage,
- customers can identify a concrete action changed or costly uncertainty closed.

Only then test team bundles / subscription packaging.

## Competitive posture

Current GovCon platforms increasingly bundle discovery, scoring, capture management, PWin, and proposal generation. CaptureBrief should not chase that breadth.

The defensible lane is:
**“You already made a gate call. We independently attack the public-source assumptions behind it before proposal kickoff.”**

Differentiation to strengthen:
- outside adversarial second pass,
- source-state / supersession discipline,
- customer-supplied assumptions,
- evidence state separated from decision impact,
- safe-stop on restricted or incomplete controlling sources,
- change-triggered reopening of affected case items,
- concise 90-second handoff with forensic provenance underneath.

## Next product work

1. Preserve the narrow $149 paid pilot.
2. Add the decision-class/action-ledger structure to every fulfillment.
3. Collect explicit outcome labels.
4. Do not add autonomous proposal writing, bid submission, PWin scoring, or private-portal ingestion.
5. Use paid engagements—not feature count—to decide the next business model.
