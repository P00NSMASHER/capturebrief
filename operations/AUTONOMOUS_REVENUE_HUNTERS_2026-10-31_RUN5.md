# Autonomous Revenue Hunters — October 31, 2026, run 5

## Canonical code, no conflicting ownership
- Continued existing draft [CaptureBrief site PR #167](https://github.com/P00NSMASHER/capturebrief/pull/167) on `hunter/revenue-v4-notice-readiness-20261031-r2`, targeting `gh-pages`. Did not modify production `gh-pages` or product-engine `main`.
- Source before this run: `5ad3a5efb4346984dd4d835f0ff7042c7268177a`; previous [GitHub workflow #41214906090](https://github.com/P00NSMASHER/capturebrief/actions/runs/41214906090) succeeded. New feature file sequence ends at `c678fe11199c53a69d639edb0c566b349db71306`, before this checkpoint commit.
- PermitPlate paid-path hold is separately owned by draft [PR #152](https://github.com/P00NSMASHER/permitplate-nyc/pull/152); x402 payment-verification repair by draft [PR #61](https://github.com/P00NSMASHER/x402-product-factory/pull/61). No duplicate branches, payment changes or merges. RETALLY/RecoveryOS canonical code not identified as a currently accessible exact repository; no guessed repo edits.

## Hunter A — source-backed buyer hypothesis, adversarial pricing comparisons
- [SAM.gov opportunities](https://sam.gov/opportunities), accessed October 31, 2026: public contract searches can be performed for free without an account. Simple search is not a defensible paid offer.
- [GAO Effective Communication Strategies, B-423993/B-423993.2](https://www.gao.gov/products/b-423993%2Cb-423993.2), February 18, 2026, sustained a protest about insufficient time to respond to substantive amendments and feedback. Contrast: [GAO Cinteot, B-424433.18](https://www.gao.gov/products/b-424433.18), September 28, 2026, denied a challenge about amendment response time because time allowed was sufficient. This is evidence of variable source-specific risk, not automatic injury or proven purchases.
- [GovPillar posted prices](https://www.govpillar.com/pricing), accessed October 31, 2026, advertise a free tier and $79/month Pursuit subscription. [Abierto posted plan](https://abierto.us/pricing), updated September 23, 2026, describes an intended $39/month Scout tier but specifically says subscriptions are not open and nothing is charged. Neither listing is a verified actual sale nor a directly equivalent one-time offer.
- Buyer hypothesis: small active federal bid teams with a known solicitation and a specific unresolved amendment/rule/eligibility/submission question, not buyers seeking another search engine. No inbound customers, price experiments, referrals, observed WTP, acquisition counts or margins substantiated by these public sources.

## Hunter B — smallest friction/attribution change, measured as code behavior only
- Baseline: the public request form has **zero voluntary first-party acquisition-source fields**, and generates local unsent email drafts without source. As a result, even a buyer who *chooses* to reveal their discovery channel cannot include it in structured intake.
- Added one clearly optional, consent-by-selection dropdown with five fixed answers (web search, referral, direct, social media, other/unsure) and a prefer-not-to-say default. A buyer-selected channel is included as `Discovery source (buyer-reported, unverified)` in a **local** unsent request only. Blank selection adds no line; forged/unlisted values fail closed; an edit invalidates previously generated previews.
- Scoped files: `index.html`, `assets/capturebrief.js`, `.github/request_draft_unit.cjs`, `.github/buyer_journey_qa.py`. Added source-selection, opt-out, tamper rejection, stale-draft invalidation, and real Chromium no-request test assertions.
- Source-only baseline/post-change proxy: **0 → 1 optional channel line** in a correctly opted-in draft; **0 lines** for an opted-out draft. This is NOT observed conversion lift, channel effectiveness, user participation, verified referral or revenue. It adds one optional form control, a potential friction cost to assess if real customer samples ever exist.
- Locally checked JS syntax before GitHub commit; full native GitHub checks and real browser QA must pass at final exact head before release. No external dependency, license import or new secrets. Rollback: revert four tightly scoped feature-file commits from this PR.

## Hunter C — privacy-safe opt-in infrastructure boundary
- No cookies, attribution URL parameters, hidden traffic capture, analytics scripts, network calls, storage or automated transmissions were added. The selected channel appears only if a buyer explicitly requests a local email preview/copy; delivery still requires the buyer to press Send in their email app.
- This makes *self-reported channel* inspectable if genuine inbound email is delivered but does not provide visit denominators, third-party authentication, provider-attested payment, automated sales, self-serve fulfillment or evidence that anyone actually sent an inquiry.
- Existing $149 human-reviewed offer, free founder check, no-card trial and payment hold remain unchanged. No Stripe readback, customer records, real transaction, refund, spending, email message or production deployment performed.

## Funnel and unit economics: factual evidence boundary
| Metric | Baseline | After this branch | Validated? |
| --- | --- | --- | --- |
| Optional discovery source in composed buyer email | No field | One *buyer-reported* source when selected | Requires native CI final-head checks |
| Automated outbound network/email/checkout actions | 0 newly added | 0 newly added | Browser test included; final-head CI pending |
| Page visits, qualified delivered leads, completed sales | Unknown | Unknown | No live analytics/provider readback |
| Actual gross revenue, refunds, fulfillment costs, net profit | Unknown | Unknown | No provider-attested records |
| Actual buyer willingness-to-pay | Unknown | Unknown | Public competitors/protests are not customer purchases |

## Next critical verified experiments
1. Review exact-head CI jobs including Chromium/WebKit and repair regression failures; keep draft/unmerged pending site owner review.
2. For real opt-in inbound inquiries, classify self-reported discovery source as *unverified* and separately confirm delivered receipt before counting a lead; avoid private customer content and false conversion attribution.
3. Pre-register a qualified-buyer sample around one specific public solicitation and a single source-reconciliation problem; capture opt-in demand, actual payment willingness and fulfillment cost only through authorized sources. No cold outreach or charges.
4. Separate customer-acquisition hypotheses from actual margin: source listing prices and synthetic test cases do not establish gross or net product income.

Engineering hours saved: not credibly measured. Scope reduced to original first-party code; no new dependency acquisition or vendor license obligations.
