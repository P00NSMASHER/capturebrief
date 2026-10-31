# Autonomous Revenue Hunters: preserve free-check buyer question (October 31, 2026)

## Scope and ownership
- Authoritative CaptureBrief company website source: `P00NSMASHER/capturebrief`, `gh-pages` -> the independently deployed Cloudflare Pages project at `capturebrief.retallyrecovery.com`; product-engine `main` is **not** the website. See `STANDALONE_SITE.md`.
- Concurrent website [PR #167](https://github.com/P00NSMASHER/capturebrief/pull/167) owns `index.html`, `assets/capturebrief.js`, `assets/v4-preflight.js`, buyer journey/browser QA, and release readiness. This isolated branch only changes `assets/v3-intake.js` and its dedicated offline question-desk test. Do not merge/release in parallel with #167 without checking current base and production owner approval.
- Other current owners: [PermitPlate #157](https://github.com/P00NSMASHER/permitplate-nyc/pull/157), [x402 #64](https://github.com/P00NSMASHER/x402-product-factory/pull/64). No competing edits or launches.
- Repo metadata at inspection shows **public**, not private. No secrets/customer data used or written.

## Buyer discovery (Hunter A)
- Independent published seller prices reviewed 2026-10-31:
  - [FedBid Pro](https://fedbidpro.com/pricing) advertises a **$99 one-time** public SAM.gov compliance/bid memo and **$299/month** unlimited analyzer.
  - [PursuitBrief](https://pursuitbrief.com/) advertises a **$297** first-sprint bid/no-bid brief, with higher scopes at **$750** and **$1,500**.
  - [BidSmith](https://www.bidsmith.pro/) advertises **$999/month** plus a free trial for a larger automated audit offering.
- These offer descriptions/prices are **vendor assertions**, not proof of purchases, comparable quality, or willingness to pay for CaptureBrief's advertised $149 one-time supervised product. The opportunity is an unresolved assumption before a proposal deadline/amendment, not generic AI summaries.
- A [2026 discussion of a GAO amendment protest](https://www.governmentcontractslegalforum.com/2026/04/articles/bid-protest/february-2026-bid-protest-sustain-of-the-month-gao-finds-failure-to-acknowledge-ifb-amendment-was-fatal/) illustrates materiality of amendment review, but is not a customer acquisition datapoint.

## Reproduced buyer-path defect and narrow repair (Hunter B)
- Actual `assets/v3-intake.js` shipped an unconditional `assumptions.value = suggested` whenever a visitor in free-check mode clicked a suggested question. If the buyer had already typed a custom one-assumption question, one click **silently deleted it**. There was no undo/confirmation. This is source-level reproduction, not a reported customer event.
- Fix distinguishes the last untouched canned question from buyer-authored text. Empty free check accepts a template; switching between untouched templates stays one click; editing a suggested question protects the edit; even over-limit content remains visible with an instruction to clear. No unapproved automated communications, form submits, third-party requests or storage.
- Four adversarial assertions cover preservation of custom questions, replacing a canned suggestion, preservation after manual edits, and never masking over-limit copy. Existing 1,000 synthetic-users/limit/deduplication tests remain the acceptance baseline.
- Code files: `assets/v3-intake.js` and `.github/v3_question_desk_unit.cjs`. No external dependency or imported code, so no new license chain. Revert the two file commits to roll back.

## Acquisition/delivery infrastructure (Hunter C)
- Existing no-card free inquiry still intentionally uses local unsent email draft and supervised admission. This branch does not add tracking/marketing messages or bypass paid fulfillment gates. Releasing it would require the existing website owner's review and actual CI + browser validation.

## Transparent metrics and limitations
| Metric | Prior website source | Candidate branch | Meaning |
|---|---|---|---|
| Custom text lost on one template click | 1/1 deterministic scenario | 0/1 expected; test pending CI | Source behavior, **not measured buyer conversions** |
| Unedited canned template replacement | 1 click | 1 click expected | Existing behavior retained |
| Leads, purchases, refunds, gross and net revenue | Unknown | Unknown | No permissioned analytics/receipts reviewed |
| Customer demand and $149 willingness to pay | Unproven | Unproven | Competitor public pricing alone is insufficient |

## Next
1. Confirm exact-head Node unit and mandatory GitHub CI, plus non-submitting browser QA; repair regressions if any.
2. Avoid merging before PR #167 ownership/release overlap is reconciled and site operator authorizes protected release. No Cloudflare publication in this run.
3. Once available, use consented aggregate acquisition -> submitted inquiry -> accepted in-scope -> paid -> delivered measures with actual cost, not synthetic buyer counts.
