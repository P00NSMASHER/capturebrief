# Revenue Hunters, 2026-10-31, run 2

## Canonical ownership
- CaptureBrief company website: `P00NSMASHER/capturebrief` branch `gh-pages`, Cloudflare standalone builder. Product engine stays on `main`.
- PermitPlate unsafe checkout issue remains owned by draft PR https://github.com/P00NSMASHER/permitplate-nyc/pull/152. No duplicate checkout edit.
- No emails, payments, customers, secrets, live deployments, or production settings changed.

## Hunter A: source-bound demand test
- SAM.gov opportunities search is free: https://sam.gov/opportunities . CaptureBrief cannot charge for discovery alone.
- HigherGov officially advertises Starter at $500/year and Standard at $2,500/year: https://www.highergov.com/pricing/ (checked Oct 31, 2026).
- Hypothesized first buyer: small federal technology vendor requiring a verified amendment-by-amendment go/no-go evidence review of a *known* public solicitation. Competitive-category pricing does not prove demand for a $149 one-off service. No validated buyer willingness-to-pay, visits, completed requests or revenue data were available.

## Hunter B: reproduced buyer-funnel defect
- Baseline: with all five source-family states marked `found` but no SAM.gov opportunity URL, preflight returned `READY TO REQUEST HUMAN REVIEW`; exported text simultaneously said `Public notice: Not provided`.
- Fix: no link now returns `EVIDENCE GAPS TO CHECK`; conflict remains HOLD; valid explicit canonical notice link plus five marks can still return the buyer-marked/unverified ready label.
- Before/after: 1 / 1,024 no-URL combinations incorrectly ready -> 0 / 1,024. State-space measurement, *not* conversion rate.
- Added targeted whitespace-link and exhaustive negative unit assertions. In-memory JS execution passed 1,024 missing-link cases and conflict precedence. Native CI and browser tests still pending.
- Original code, zero added packages or transitive licenses, no telemetry/egress/storage. Rollback is PR revert.

## Hunter C: self-service infrastructure
- Existing no-send, scope-first, no-card free-check draft remains unchanged. This fix prevents a misleading review-ready signal; no automatic contact, tracking or payments.
- Required real checks: `node .github/v4_preflight_unit.cjs`, `node build-standalone-site.test.js`, and GitHub browser/Cloudflare quality PR checks.
- No verified visits, paid orders, gross receipts or net profit; metrics unavailable rather than zero.

## Ranked follow-up
1. Resolve native GitHub CI/browser failures and review PR without auto-deployment; release requires owner approval.
2. Verify PermitPlate provider-level saved Stripe Payment Link behavior separately; provider-side changes require explicit consent.
3. Validate willingness-to-pay with genuine inbound qualified buyers before forecasting revenue. No unsolicited outreach.
4. Only add privacy-approved funnel measurement once authorized; without live metrics, keep figures unknown.

Estimated engineer-hours saved: not reliably measurable; do not invent.
