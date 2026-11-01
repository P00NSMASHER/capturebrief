# Autonomous Revenue Hunters: 2026-10-31 run 7

## Ownership and change boundary
- **Authoritative buyer website:** `P00NSMASHER/capturebrief` `gh-pages`, publicly deployed through Cloudflare Pages only after protected release. Product core stays on `main`. See `DEPLOYMENT-TARGET.md` on main and `STANDALONE_SITE.md` on gh-pages.
- **Existing owner branch:** `hunter/revenue-v4-notice-readiness-20261031-r2`, draft [PR #167](https://github.com/P00NSMASHER/capturebrief/pull/167). **This run extends the existing PR rather than creating a competing one.** The separate [PR #169](https://github.com/P00NSMASHER/capturebrief/pull/169) modifies the V3 suggestions and browser QA. No files from #169 were touched here.
- **Pre-run exact PR head:** `4977c19d6a0b804cc34dc31fa5f6c2efe86a710e`. Its [six-job website-quality CI](https://github.com/P00NSMASHER/capturebrief/actions/runs/41224159917) passed. No claim of deployment is made.
- **Code commits:** [`1ef1bd2`](https://github.com/P00NSMASHER/capturebrief/commit/1ef1bd2a1e13a9aca142ea4ef6e35e2505ffcbd6), [`518d550`](https://github.com/P00NSMASHER/capturebrief/commit/518d55052674dc856b03ea92026b85ee36ad57ea).
- **No new dependencies or third-party source import** (the change consists of original trivial mailbox syntax checks); no new license/NOTICE or vendor cost. Rollback is a revert of these two commits; leave prior PR #167 fixes intact.

## Hunter A: demand evidence and cheapest acquisition hypothesis
- Narrow potential buyer: capture/proposal operations lead with an actual, public SAM.gov solicitation whose deadline, amendment, eligibility, or submission instruction is in doubt. The public free single-assumption path and source-linked historical example are existing assets; **no inquiry or payment is inferred from their presence**.
- [FedReady vendor pricing](https://www.fedready.us/pricing) advertises a free tier, Pro $49/month, Pro+AI $149/month; its [homepage](https://www.fedready.us/) simultaneously describes discounted founder prices ($24.50 and $74.50 per month). This is a public **pricing inconsistency**, not a verified current purchase price, paid conversion or like-for-like valuation for CaptureBrief's human-reviewed $149 one-time service.
- Published [GAO docket B-424433.16](https://www.gao.gov/docket/b-424433.16), decision dated 2026-09-21, establishes a real federal bid-protest context but not demand for CaptureBrief. Do not infer willingness to pay from a docket or competitor offer.
- Lowest-spend validation channel to try *after approved release*: opt-in search discovery for buyer queries about solicitation amendments and deadlines, with the existing optional self-reported acquisition channel in the email draft. It is a **hypothesis**, not an active campaign or proven acquisition channel. No SEO page was published or analytics tracker added.

## Hunter B: measurable code-level buyer-reply defect
- Canonical `assets/capturebrief.js` previously used `/^[^@\\s]{1,64}@[^@\\s]{1,189}\\.[^@\\s]{2,63}$/` before allowing a no-send email draft. Four invalid unquoted work-mailbox shapes were accepted at the local composer layer: `.buyer@example.com`, `buyer.@example.com`, `buyer..test@example.com`, `a..b+tag@example.com`. Browsers' `type=email` checks are not a substitute for mailbox dot-atom semantics. **No affected real buyer or undeliverable email was observed**.
- Added local-part leading/trailing/doubled-dot rejection without changing the existing email shape/254-character bounds, SAM public-source checks, no-send policy, price, manual-copy fallback or consent rules.
- Added actual-script execution assertions in the pre-existing `.github/request_draft_unit.cjs`: 4 bad addresses × 3 request modes = **12 synthetic rejection** cases; 3 permitted addresses × 3 modes = **9 valid-preservation** cases; all 12 bad scenarios retest correction in place. Includes a 64-character local part and a plus-tagged dotted work address.
- Bounded before/after logic check on the same four bad strings: **4/4 accepted → 0/4 accepted**; three valid examples retained (**3/3**). These are code-model fixture observations, not real browser CI or measured user conversion uplift. Exact-head official CI must independently validate the committed browser/Node runner.

## Hunter C: conservative fulfillment and accounting boundary
- Draft only. No charge, price/terms change, checkout activation, contact, email send/draft, record access, tracking beacons, customer data or live publish.
- Existing no-card manual-send intake remains explicitly separate from receipt confirmation. The free pilot remains max ten *operator-verified* businesses, **not** self-serve accepted signups.
- No new automated payment fulfillment until customer-ready provenance, provider receipt binding, protected delivery and controlled rollback are confirmed. Keep PermitPlate paid checkout hold [#152](https://github.com/P00NSMASHER/permitplate-nyc/pull/152) and x402 money-boundary repairs in their separate owner PRs.

## Funnel measurements and interpretation
| Measure | Before | Proposed branch | Evidence |
| --- | --- | --- | --- |
| Invalid unquoted mailbox forms accepted by composer | 4/4 fixtures | 0/4 fixtures expected; final CI pending | Exact source validator and deterministic local expression check |
| Valid fixture emails accepted | 3/3 | 3/3 expected | Local validator check |
| Verified delivered inquiries, leads, actual visits | Unknown | Unknown | No approved aggregate live funnel source |
| Stripe-confirmed paid purchases or refunded receipts | Unknown | Unknown | No provider readback |
| Net collected revenue, variable costs, profit or CAC | Unknown | Unknown | No independently reconciled transaction/cost evidence |

## Next checkpoint
1. Read PR #167 exact-head native Website quality six-job CI; repair a reproducible failure, if any, without relaxing no-send / payment boundaries. Keep draft and unmerged until website owner authorizes production release and existing PR #169 is coordinated.
2. Verify no mismatch between Cloudflare company website deployed bytes and expected approved revision *only after an authorized release*. Do not treat other hosts or fixture traffic as real conversion.
3. Rotate to PermitPlate supervised trial and x402 evidence reliability without colliding with their open owner PRs. Gather **real, consented** inbound outcomes when available; no fabricated MRR.
