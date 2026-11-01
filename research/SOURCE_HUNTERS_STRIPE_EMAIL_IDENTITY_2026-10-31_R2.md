# Revenue Product Source Hunters, run 2: Stripe buyer-email evidence integrity

Date: 2026-10-31 (America/New_York). Scope: **CaptureBrief** existing product core, isolated draft. No live checkout, emails, API tokens, customer records, payments, deployments or other automation changes.

## Verified source baseline
- Canonical source: [CaptureBrief payment reconciliation](https://github.com/P00NSMASHER/capturebrief/blob/main/capturebrief_core/payment_reconciliation.py), original blob SHA `1b5a6b4cac20c641164f05c3b8e0edc13ceff2d9`.
- Original behavior accepted if the expected email appeared in **either** `checkout.session.customer_details.email` or `checkout.session.customer_email`, even when the other present address contradicted it. It also ignored an invalid secondary non-null email. This is a reproducible **source-level** identity-integrity weakness, **not** an observed Stripe/customer incident.
- Prior test coverage in [test_payment_reconciliation.py](https://github.com/P00NSMASHER/capturebrief/blob/main/tests/test_payment_reconciliation.py) tested a single `customer_details.email` and unrelated payment/charge failures, but not contradictory simultaneous fields.

## Integration decisions and public code/library candidates
1. [stripe/stripe-python](https://github.com/stripe/stripe-python), [exact LICENSE](https://github.com/stripe/stripe-python/blob/master/LICENSE) inspected (MIT, GitHub blob `f9ee781c976b733377d99911319769bf95229bd8`): maintained official SDK, excessive for a pure local equality invariant. Rejected dependency import.
2. [pydantic/pydantic](https://github.com/pydantic/pydantic), [exact LICENSE](https://github.com/pydantic/pydantic/blob/main/LICENSE) inspected (MIT, GitHub blob `488c6260c10f2e88fa1fae58a63fccec8d600cd1`): capable type validation, but adds an unnecessary dependency surface for two existing fields. Rejected dependency import.
- Selected **original minimal adaptation** of the current no-dependency normalizer, with three narrow regression tests. No third-party source copied, no advisory-chain or lockfile change; pinned library-SHA evaluation applies to candidates only, not to runtime dependencies.

## Tests and expected measurements
- Baseline adversarial cases: two *different* simultaneously present emails, one matching the expected buyer. Both were incorrectly eligible under the original `in (session_email, session_fallback_email)` condition.
- New negative controls: invalid secondary email; invalid primary email with a valid fallback; malformed `customer_details` structure with valid fallback. Must block. Failures produce redacted reason codes, not email addresses.
- Positive controls: both email fields equivalent after canonical case normalization; valid fallback when `customer_details.email` is null. Must preserve original consistent review-required state, never authorize work or delivery.
- Run `python -m unittest tests.test_payment_reconciliation -v`; existing [Product Core CI](https://github.com/P00NSMASHER/capturebrief/blob/main/.github/workflows/product-core.yml) also runs full regression discovery on Linux and independent Windows compatibility jobs.
- **Testing status at patch creation:** new tests committed; exact PR-head CI to be observed separately before asserting passes. No browser UI modified; synthetic Stripe fixture path is offline.

## Commercial impact and release controls
- Prevents false processor-to-buyer identity consistency during human-review payment reconciliation. Does not verify actual provider authentication or authorize sending anything.
- Hypothetical integration work saved vs adopting a parsing/validation SDK: **0.5–1.5 engineering hours**, subjective low confidence and **not measured**. Observed customers/revenue/net margin: **unavailable**, not zero by inference.
- Protect product-owner release: hold draft until exact-head CI and protected review; no merge without genuinely satisfied controls and coordination. Rollback: close draft PR, no live state changed.

## Hunter rotation / canonical portfolio coordination
- Hunter A: CaptureBrief focused code and tests. Existing CaptureBrief PRs #167–172 modify separate source/site paths; avoid rebasing/overwriting their owners.
- Hunter B: checked the authenticated owner repository inventory (14 repos). **No separately accessible RETALLY/FreightRecovery/RecoveryOS canonical GitHub repository found**; do not create competing ones or claim their code was touched. The canonical [x402 product factory](https://github.com/P00NSMASHER/x402-product-factory) is accessible and has substantial active draft PR ownership (#61–69 and older release stacks). Avoid duplicate/competing x402 edits during this cycle.
- Next eligible Hunter B investigation: derive a narrow, nonoverlapping adapter test from exact x402 main after coordinating #66's live-PA source edits, or diagnose immutable settlement evidence chain without changing payment code or live settings. Check current PR ownership again.
- Owner action now: **none**. Final merge/release remains separate, protected.
