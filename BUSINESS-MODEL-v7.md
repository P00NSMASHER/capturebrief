# CaptureBrief Business Model v7 — Decision Evidence for Federal Pursuits

Updated: September 21, 2026

## Product definition

CaptureBrief is a human-supervised **Decision Evidence review** for small federal IT, cyber, and cloud contractors.

The buyer already has a live pursuit and a current internal posture.

CaptureBrief answers a narrower question:

> **What exact public source, source version, and reviewed rule edition does each important assumption behind that pursuit decision actually rest on?**

It is not an opportunity-discovery platform, proposal writer, bid-submission service, legal adviser, or PWin engine.

## Current founding offer

**$149 one time**

For one selected public federal IT / cyber / cloud pursuit:

- current posture;
- up to five non-sensitive buyer assumptions;
- exact public-source passages;
- controlling / supporting / superseded source versions;
- before/after source-version evidence where a material change is retained;
- reviewed FAR / DFARS / supplement / deviation edition and pursuit-specific applicability basis when relevant;
- explicit missing-evidence requests where the record cannot support a conclusion;
- concise decision handoff;
- inspectable Decision Evidence package;
- 14-day targeted source/rule/change watch;
- no automatic renewal.

The buyer's team retains all pursue / hold / pass and legal/procurement decisions.

Do not change pricing or introduce a recurring offer until outcome evidence satisfies the current review gates.

## Buyer

Initial buyer:

Small federal technology contractors that:

1. already have active capture/proposal work;
2. have made or are approaching an internal GO / HOLD / NO-GO / UNSURE decision;
3. lack bandwidth for a rigorous independent second pass;
4. can use public-source evidence without exposing restricted portal material;
5. care more about avoiding a bad assumption than receiving another long summary.

## Unit of value

The product unit is **one assumption with an inspectable evidence trail**.

For each assumption CaptureBrief preserves:

- buyer assumption text;
- evidence state;
- decision class;
- exact cited public passage;
- retained source identity;
- source version label;
- document SHA-256;
- prior/new source versions when relevant;
- exact before/after passages for a retained source delta;
- reviewed rule version when rules matter;
- separate pursuit-specific applicability basis;
- human reviewer and review time;
- concrete next action or evidence request;
- targeted watch dependencies.

## Evidence states

- `SUPPORTED`
- `CONTRADICTED`
- `UNPROVEN`
- `SUPERSEDED`
- `SOURCE_LIMITED`

Unknown is not converted into “no.”

Unknown becomes a specific evidence request.

## Decision classes

- **GATE-CHANGING** — can change eligibility, submission path, timing, posture, or immediate proposal work.
- **VERIFY-NOW** — unresolved evidence that could change the current action.
- **MONITOR-ONLY** — useful evidence that does not currently change the next action.

The default buyer handoff contains at most five GATE-CHANGING / VERIFY-NOW items.

## Product architecture

The current product separates these claims:

`opportunity-family history`
≠
`current action`
≠
`attachment/resource presence`
≠
`captured bytes`
≠
`named-reference closure`
≠
`exact cited passage`
≠
`rule version`
≠
`rule applicability`
≠
`buyer decision`

A stronger claim may never be inferred merely because a weaker layer is green.

### Public-source history

SAM Data Services supplies action/version membership.

The documented Opportunities API supplies latest-active currentness.

These are separate evidence planes.

### Packet/reference closure

Named dependencies are proposed by automation but human-confirmed.

A missing parser hit can never become “safe to ignore” automatically.

### Exact Decision Evidence

Every decision-relevant assumption can be tied to:

- exact retained public text;
- source/version metadata;
- content hashes;
- reviewed source-version deltas;
- reviewed rule edition and applicability basis.

A newer rule publication does not automatically replace an edition incorporated by the pursuit.

### Delivery bundle

A customer delivery is produced only after the release gate passes.

The deterministic ZIP contains:

- concise brief;
- Decision Evidence HTML/Markdown;
- machine-readable decision summary;
- source-version manifest;
- targeted-watch baseline;
- per-file SHA-256 manifest.

The raw internal case and raw customer intake are excluded.

### Targeted 14-day watch

The delivered baseline fingerprints only the minimum public/evidence state needed for change detection.

Fresh observations can reopen only assumptions whose recorded dependencies changed.

The watch never silently rewrites the prior decision or auto-changes rule applicability.

## Source boundaries

Current product accepts public/non-sensitive inputs only.

Do not accept:

- CUI;
- classified/export-controlled information;
- credentials;
- proposal drafts containing sensitive strategy/pricing;
- private-portal material;
- restricted content the customer is not authorized to share.

When controlling evidence is unavailable publicly, the affected item remains SOURCE_LIMITED / UNPROVEN.

## Product promise

CaptureBrief should be sold as:

> **Know what your bid decision rests on.**

Not:

> “We summarize solicitations.”

The differentiator is source/rule/version accountability around assumptions the buyer is already using.

## What CaptureBrief does not promise

CaptureBrief does not claim:

- win probability;
- legal correctness;
- proposal compliance certification;
- automatic eligibility determination;
- savings;
- ROI;
- guaranteed action change;
- complete private-portal coverage.

## Commercial learning

Commercial outcomes are recorded through the append-only outcome ledger in `OUTCOME-LEDGER.md`.

Track explicit evidence only:

- current paid/unpaid/refunded state;
- delivery turnaround;
- operator effort by fulfillment stage;
- buyer usefulness;
- changed action;
- costly uncertainty closed;
- confirmed existing view;
- already knew;
- false positive;
- source-limited;
- retraction;
- explicit repeat request;
- finding classes used.

Do not infer PWin uplift, proposal savings, accuracy, ROI, or revenue uplift.

## Current pre-expansion gates

Before testing team/subscription packaging, require factual evidence of:

1. at least **3 current paid engagements**;
2. at least **1 explicit repeat request**;
3. at least **1 buyer-reported changed action or costly uncertainty closed**;
4. measured turnaround evidence;
5. recorded operator effort for every currently paid engagement;
6. a human decision that turnaround, labor burden, and retraction levels are acceptable.

Passing these conditions makes expansion eligible for human review. It does not automatically change the price or product.

## Current execution priority

1. Sell and deliver the $149 founding review.
2. Preserve exact source/rule/version evidence for every material finding.
3. Run the included targeted watch.
4. Record payment/delivery/effort/feedback/retraction/repeat evidence.
5. Review which fulfillment stage consumes the most human minutes and remove avoidable operator work without weakening evidence gates.
6. Use those outcomes—not additional feature count—to decide whether CaptureBrief expands.

## Stop rule

If qualified buyers will not pay for the narrow review, do not respond by adding proposal generation, broad opportunity discovery, or autonomous bid scoring.

Revisit buyer, problem, positioning, intake burden, and price first.


## Fulfillment economics rule — v0.28

The founding $149 offer is not treated as operationally scalable merely because buyers pay.

Every paid engagement should record additive `EFFORT` events by stage. Before testing a recurring/team offer, the operator should be able to answer from evidence:

- how many human hours the median paid case consumed;
- which stage consumed those minutes;
- whether every currently paid engagement has labor coverage;
- collected dollars per recorded effort hour by currency where payment amount was recorded;
- whether that labor burden is acceptable for the current price and operating model.

CaptureBrief does not set an automatic labor threshold or auto-reprice itself. The evidence exists so a human commercial decision can distinguish product demand from a service that is quietly consuming too much founder time.
