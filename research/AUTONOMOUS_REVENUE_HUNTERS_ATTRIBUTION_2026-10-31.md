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
- Independent **buyer-language signals (anecdotal, not purchase evidence)**: a small GovCon poster describes spending half a day reviewing each opportunity before a go/no-go call (2026-02-10): https://www.reddit.com/r/govcon/comments/1r0xe6r/how_are_small_govcon_teams_making_real_go_or_nogo/ ; another thread describes manual review of amendments and attachments despite free SAM notifications (2026-09-19 discussion): https://www.reddit.com/r/govcon/comments/1wk4g17/removed/ . The latter thread is currently shown as removed, so treat replies as lower-confidence context, not durable primary demand proof.
- Stronger falsifiable positioning hypothesis: public-source **amendment/assumption verification before bid/no-bid**, not generic opportunity search. Test whether buyers will accept a verified single-assumption free check and explicitly authorize a $149 one-off paid review; do not infer demand from competitor price pages or Reddit votes.
- Demand hypothesis: a documented one-pursuit public source review may be worth a $149 one-time purchase to a small federal IT/cyber/cloud contractor facing a near-term bid/no-bid decision. **UNTESTED**: no verified buyer conversations, paid conversions, active trials, MRR, margin, or conversion rate available from approved evidence in this run.

## Metrics and next bounded experiments
- Before: 1 of 3 newly written regression tests fails. After: 3 of 3 pass locally. CI/merge must be independently verified on exact PR head.
- No measured funnel uplift. No revenue increase claim. No platform analytics or Stripe records read or inferred.
- Stripe aggregate-metrics access check (2026-10-31): two available connected Stripe links each require an interactive account selection in this non-interactive execution. **No Stripe data was retrieved**, and no claim of zero revenue or customer count can be made. Do not substitute synthetic purchases; account selection is the exact remaining read-only metrics blocker.
- Follow-up: obtain approved aggregate Netlify funnel counts (visits, qualified submissions, no-source rejects) and independently corroborated test-mode checkout/fulfillment receipts, without exporting buyer details. Pre-register 1 conversion metric and a 14-day observation window before design changes.
- Validate paid willingness to pay using voluntary inbound buyer responses only; do not spam, collect private data unnecessarily or automatically charge anyone.
- Target next task: verify that `main`'s public build and actual deployed site include the same intake form and report links, after legitimate CI and release authorization. No autonomous production deployment.


## Run 2: browser release gate + independent price-position check (2026-10-31 ET)

### Engineering advancement (PR #170, same branch)
- Confirmed first-run PR #170 exact-head required `product-contract` and `windows-compatibility` checks passed before the follow-up.
- **New executable release gate:** `scripts/qa_public_attribution_browser.py` serves the existing real `index.html` and `assets/main.js` on 127.0.0.1, blocks all non-loopback requests, refuses POST, and checks 4 explicit attribution cases at both 375 px and 1280 px. Verifies form action, method, safety confirmation, no script errors, and Escape/mobile navigation; test cases: 8 real-browser flows. The test must pass in GitHub CI before release status can be claimed.
- `.github/workflows/capturebrief-attribution-browser.yml`: pinned checkout/setup actions, Python 3.11, Node 22.23.4, Playwright 1.57.0, real Chromium; PR-scoped trigger. No production deploy, no billed requests or customer email.
- New-code dependencies: only pinned test-only Playwright version; no runtime dependency, payment code, domain or production change. Rollback: revert the two additive QA files on this isolated draft PR branch. Existing production is unaffected.
- Coverage baseline: previously 3/3 offline JS tests; newly added 8 browser checks pending independent exact-head CI. **Do not equate new tests with conversion uplift.**

### Demand, buyer and acquisition-channel evidence
- https://www.reddit.com/r/govcon/comments/1r0xe6r/how_are_small_govcon_teams_making_real_go_or_nogo/ (2026-02-10): a small contractor describes a half-day manual solicitation review, followed by replies on go/no-go triage. Self-selected discussion, not verified paying demand.
- https://winningbids.ai/pricing : publicly advertises $19/month entry-level AI bid/no-bid, a materially cheaper adjacent substitute; pricing page does not demonstrate paid adoption.
- https://abierto.us/pricing (updated 2026-09-23): announces a planned $39/month Scout, $99 Pro and $249 Team, explicitly **not yet charging**. Treat as non-sale-priced planned positioning.
- https://bidstride.com/pricing : advertises $150/month Radar and $300/month Capture, including bid/no-bid workflows; not proof that CaptureBrief's one-off evidence review sells.
- https://sam.gov/opportunities : government publishes free searchable notices and optional saved searches; competitors charging purely for access or generic alerts face free official substitutes. A credible differentiator must be documented source-version/assumption verification, not mere discovery.
- **Prioritized bounded hypothesis:** small federal IT/cyber/cloud contractors that recently found a consequential amendment will choose to submit a public-only *specific assumption* for a free check and accept the clearly disclosed $149 supervised review if its evidence trail catches a real decision-relevant change.
- **Lowest-cost permitted channel:** a truthful, source-linked worked example and existing landing page exposed to voluntary organic search, not scraped lead lists or unsolicited messages. Track (with approved aggregate privacy-safe counts) organic visits -> legitimate request submits -> in-scope accepted -> *verified* completed paid orders. No conversions can be computed without denominator and Stripe/account evidence.

### Current status
- Prior PR #167/#168/#169 ownership unchanged; no overlapping files changed.
- CI results for the latest commit are not yet captured here; confirm exact-head GitHub job conclusions before advancing PR.
- Current repository is **public** according to authenticated GitHub; user's private-code preference remains unresolved. Do not leak customer records or credentials.
- Browser test cannot prove live Netlify Form fulfillment, actual user demand, or real checkout; independently require authorized production QA and aggregated funnel evidence before stating readiness/revenue.
