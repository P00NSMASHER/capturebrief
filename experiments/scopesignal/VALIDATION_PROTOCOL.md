# ScopeSignal Validation Protocol

Pinned upstream: `cneuralnetwork/ScopeSignal@d470659a009e9944fd6c4a7969a903dfc28c443e` (MIT).

## Purpose
Validate one narrow commercial claim before building a standalone product:

> Given a signed SOW/contract and a new client request, can the system conservatively identify work that may require a change order, cite the exact contract language, and turn the human-reviewed result into billable action?

This workstream is capped at 15% of portfolio capacity.

## Reuse target
The pinned upstream already implements the right safety boundary:
- `src/lib/domain.ts`: structured findings and deterministic grounding policy;
- `src/app/api/analyze/route.ts`: conservative analysis contract;
- out-of-scope findings require contract evidence;
- ungrounded out-of-scope claims are downgraded to review;
- human review remains final.

No upstream code is incorporated into our product until dependency/license review is complete.

## Validation cases

### Case A — clear change order
Contract:
- one landing page included;
- additional pages require written change authorization.

Request:
- "Can you add a second landing page for the event?"

Expected:
- POSSIBLE CHANGE ORDER / likely out of scope;
- exact supporting contract quote required;
- estimated hours are editable by the human;
- no automatic sending.

### Case B — clearly included
Contract:
- two revision rounds included.

Request:
- first normal revision round.

Expected:
- IN SCOPE;
- no recovery value manufactured;
- no change-order draft by default.

### Case C — ambiguous
Contract:
- "reasonable revisions" included;
- no definition of weekend/rush work.

Request:
- "Please redo this over the weekend for Monday morning."

Expected:
- NEEDS REVIEW;
- no out-of-scope verdict without exact supporting language;
- ambiguity is surfaced, not resolved by invention.

### Case D — fabricated-clause attack
Force/model-simulate a finding that cites contract language that does not exist.

Expected:
- deterministic grounding rejects the citation;
- status downgrades to NEEDS REVIEW;
- confidence is capped;
- fabricated evidence cannot appear in the customer-ready change order.

## MVP surface
Only three functional steps:
1. Contract/SOW input.
2. New request/conversation input.
3. Reviewed result -> editable response/change-order draft.

Deferred until validation:
- Gmail/Slack monitoring;
- CRM;
- invoicing;
- team workspaces;
- e-signature;
- autonomous sending;
- background monitoring.

## Success metrics
Technical:
- 100% of out-of-scope findings carry verified source text;
- zero fabricated contract citations survive deterministic validation;
- ambiguous cases fail to review rather than overclaim;
- human override is always available.

Commercial:
- a user recognizes at least one real missed billable request;
- the output is useful enough that the user would actually send/use the change order;
- stronger promotion signal: an identified change order is accepted/paid.

## Kill / hold rule
If users find the output intellectually interesting but it does not recover or protect money, do not expand the product.
