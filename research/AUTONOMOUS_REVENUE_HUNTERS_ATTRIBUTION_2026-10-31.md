# Autonomous Revenue Hunters: attribution integrity and demand scan (2026-10-31)

## Source of truth and ownership
- Repository: P00NSMASHER/capturebrief, default branch `main`; this PR is isolated and **does not deploy**.
- Open concurrent owners: PR #167 (website review preflight, `gh-pages`), PR #169 (free-check question composer, `gh-pages`), PR #168 (source redirect guard, `main`). No touched paths overlap those open PRs.
- The authenticated GitHub connector reports this repository **public**, not private. No customer records, credentials or secret measurements may enter this repository.
- Product truth: CaptureBrief is currently a supervised public-source review, not fully automated customer fulfillment. The form records user-supplied acquisition labels, not reliable purchases or qualified demand.

## Reproducible failure and correction
- Failure before: visitor-controlled `utm_source`, `utm_campaign`, and pathname flowed verbatim into hidden Netlify form fields. A 4,096-character tag and an email-containing path would be submitted with a normal voluntary intake.
- Correction: allow only short (max 64-character), non-URL, non-email marketing labels; use only the canonical intake page identifier. Leave all form destination, consent, price, network, account and production configurations unchanged.
- Regression: `python -m unittest tests.test_public_attribution -v` runs actual `assets/main.js` in an offline Node synthetic DOM. Three tests cover three legitimate combinations, seven rejected adversarial inputs and the missing-form/empty-value path. Before patch, the adversarial test fails; after patch, all three tests pass locally.
- No external dependency or license obligations were introduced; source is original local adaptation.

## Buyer demand scan: published offers, not verified purchases
- Competitor RestoSignals advertises opening-data coverage and a **$29/month** plan: https://restosignals.com/
- Ribbon Leads advertises a **$99/month one-state** tier: https://ribbonleads.com/
- Townline advertises permit-record API plans **starting $199/month**: https://townline.app/
- CaptureIQ advertises a **$249/month** federal capture software tier: https://www.rfpcapture.com/
- These are competing published price positions, not proof that the user's products can sell at those prices. They also differ substantially in coverage and service level. The likely niche to validate: buyers who prefer source-linked, decision-ready evidence rather than lists, automated scores or broad proposal suites.
- Demand hypothesis: a documented one-pursuit public source review may be worth a $149 one-time purchase to a small federal IT/cyber/cloud contractor facing a near-term bid/no-bid decision. **UNTESTED**: no verified buyer conversations, paid conversions, active trials, MRR, margin, or conversion rate available from approved evidence in this run.

## Metrics and next bounded experiments
- Before: 1 of 3 newly written regression tests fails. After: 3 of 3 pass locally. CI/merge must be independently verified on exact PR head.
- No measured funnel uplift. No revenue increase claim. No platform analytics or Stripe records read or inferred.
- Follow-up: obtain approved aggregate Netlify funnel counts (visits, qualified submissions, no-source rejects) and independently corroborated test-mode checkout/fulfillment receipts, without exporting buyer details. Pre-register 1 conversion metric and a 14-day observation window before design changes.
- Validate paid willingness to pay using voluntary inbound buyer responses only; do not spam, collect private data unnecessarily or automatically charge anyone.
- Target next task: verify that `main`'s public build and actual deployed site include the same intake form and report links, after legitimate CI and release authorization. No autonomous production deployment.
