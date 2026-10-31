# Autonomous Revenue Hunters — 2026-10-31 run 6

## Verified ownership and checkpoint
- Canonical CaptureBrief public website: `P00NSMASHER/capturebrief`, feature branch `hunter/revenue-v4-notice-readiness-20261031-r2`, PR [#167](https://github.com/P00NSMASHER/capturebrief/pull/167) against `gh-pages` (product engine is separately maintained on `main`).
- Start head `3c6eecfd5bf6c72c802bc25d2bdddf4a0cfc0300`; previous [six-job CI](https://github.com/P00NSMASHER/capturebrief/actions/runs/41219853271) passed. Existing PermitPlate checkout hold [#152](https://github.com/P00NSMASHER/permitplate-nyc/pull/152) and x402 facilitator repair [#61](https://github.com/P00NSMASHER/x402-product-factory/pull/61) retain separate ownership.
- This iteration only updates the existing draft PR; no live `gh-pages`, `main`, Stripe, customer mailbox or production configuration changed.

## Hunter A: customer demand, verified public alternative prices (October 31, 2026)
- [FedReady](https://www.fedready.us/pricing): free federal opportunity search; vendor **advertises** Pro `$49/month` and Pro+AI `$149/month` with a no-card Pro trial.
- [GovPillar](https://www.govpillar.com/pricing): vendor **advertises** a free Explorer tier and a `$79/month` Pursuit tier with a 14-day trial.
- [Abierto](https://abierto.us/pricing): vendor displays a future `$39/month` Scout price but expressly states accounts are not open and it charges nobody yet.
- These are public vendor claims, not independently observed transactions, and are not 1:1 substitutes for CaptureBrief's one-time **human-reviewed** `$149` scope-confirmed service. No measured buyer willingness to pay, qualified lead count, or net profit.
- Narrow buyer hypothesis: an active federal pursuit team with a specific public notice and one unresolved response/eligibility/amendment question. Test only through voluntary inbound demand; do not use cold outreach.

## Hunter B: reproducible source-level intake friction fixed
- **Before:** a buyer chooses `FREE_CHECK`, enters a valid public non-SAM URL, clicks Copy, and receives the correct free-only error. The error is installed via `opportunity.setCustomValidity(...)`. Switching to `SCOPE_FIRST` or `PAID` without changing that URL leaves the custom validity error in place: `form.reportValidity()` refuses the now-eligible public URL. The previously implemented mode switch only cleared `assumptions` and `purchaseStatus` errors.
- **After:** mode switch additionally clears only the stale `opportunity` custom validity. Normal `compose()` still rejects actual invalid/private links; free checks continue to require one exact canonical SAM.gov notice; paid status remains buyer-claimed and independently verified. All existing prices and offers preserved.
- Modified `assets/capturebrief.js`, added two mode-switch regression scenarios in `.github/request_draft_unit.cjs` and real Chromium browser-path/no-network assertions in `.github/buyer_journey_qa.py`.
- Baseline/post-change *code behavior* target: **0/2 -> 2/2** previously stranded paths (free-to-scope, free-to-paid) become draftable with unchanged otherwise-public URL. This is not a customer conversion measurement. Exact-head GitHub CI, including browser QA, is mandatory to validate target.
- Commits: [fix](https://github.com/P00NSMASHER/capturebrief/commit/0fe07f250c2d3788043a6c572bc9b58704c8793b), [unit regressions](https://github.com/P00NSMASHER/capturebrief/commit/52eca848d9af8048d2a77f09f32f1641a5fe9c3f), [browser regression](https://github.com/P00NSMASHER/capturebrief/commit/18be7fc34acdb287b465d97782f5183aec948afa).
- No dependency or code import, so no additional library license-chain or deployment risk. Rollback: revert these three scoped commits in PR #167.

## Hunter C: independent acquisition and fulfillment boundary
- Browser QA guards local Copy and no-network behavior; no new email, auto-submit, tracking, data retention, subscription upgrade, charges, delivery automation, user tracking, or Stripe calls.
- The existing intake still requires the buyer to manually send an email and operator to confirm fit before purchase. It **does not** establish a self-service revenue engine. No changes were made to payments or fulfillment while release ownership is unconfirmed.

## Funnel evidence (no invented metrics)
| Metric | Baseline | Proposed branch | Source |
| --- | --- | --- | --- |
| Previously trapped type-switch paths | 2/2 trapped | 0/2 expected trapped | Source logic and new tests; final CI pending |
| Actual website visitors/qualified inquiries | Unknown | Unknown | No permissioned aggregate analytics |
| Stripe-verified purchases/refunds | Unknown | Unknown | No authorized provider readback |
| Real net profit, CAC, demand elasticity | Unknown | Unknown | No verified transaction and operating cost dataset |

## Next priorities
1. Verify final exact-head GitHub Actions unit and Chromium/WebKit browser jobs and repair any regressions; keep PR draft until website release owner explicitly authorizes merging a live sales-surface change.
2. Preserve PermitPlate #152 checkout hold; no public checkout restoration until full Stripe payment-link control, product readiness and source-backed fulfillment are independently verified.
3. If genuine opt-in inbound buyers arrive, record only consented aggregate delivered-inquiry/acceptance/payment results and direct fully burdened cost; pre-register a small price/value test. Do not claim success based on synthetic tests, public advertised vendor prices, or unsent local drafts.
