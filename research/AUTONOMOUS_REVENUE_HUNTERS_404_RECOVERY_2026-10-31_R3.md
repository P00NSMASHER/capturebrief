# Autonomous Revenue Hunters: 404 recovery and buyer proof (2026-10-31, run 3)

## Verified source state, not commercial outcome
- Repository: P00NSMASHER/capturebrief; source branch main when evaluated; existing open draft PRs #167, #168, #169, #170, #171 inspected and none lists `404.html` as a changed file.
- Reproduced against exact `404.html` blob `a702ab6e2a04219c5ffb16e1162ba0979b166a5b`: `robots=index,follow`, **5** legacy `sample.html` links, and a form CTA falsely labeled as an email request despite targeting a web form.
- Current homepage promotes `decision-evidence-sample.html` as the primary proof page. The historical `sample.html` remains available from that page.
- Fix: explicitly `noindex,follow` the missing-page document, point all 5 recovery links to the current primary sample, and correct the accessible request CTA label. **Also fixed 28 root-relative navigation/assets references**: when Netlify renders 404 at `/missing/nested/`, former `href="index.html"`, sample and asset URLs resolve beneath the missing pathname, producing another 404 or an unstyled page. Root-absolute paths now resolve to actual site resources. Regression verifies three nested missing-route shapes.
- Acceptance: `python -m unittest discover -s tests -p test_public_404_buyer_recovery.py -v`; required Product Core CI. No price, checkout, backend, customer data, protected branch, or deployment changes.
- Before/after source-level measurements: **0/5 → 5/5** recovery links to primary proof; indexable directive → noindex directive; **0/${countFixed} → ${countFixed}/${countFixed}** nested-safe internal navigation/asset paths. This is not verified traffic, ranking or revenue uplift.
- Live website browser returned inaccessible for `https://capturebrief.netlify.app/404.html` on this check; no claim about actual HTTP 404 status or published deploy.

## Competitor asking-price evidence, not purchase validation
- PursuitBrief publicly advertises a $297 entry bid sprint (https://pursuitbrief.com/).
- 180 Industries advertises a $450 Go/No-Go Decode (https://180ind.com/).
- FedBid Pro advertises a $99 Analyzer (https://fedbidpro.com/).
- All checked 2026-10-31. These are substantially different deliverables, not proven CaptureBrief willingness to pay. Hypothesis: buyers with costly pursuit uncertainty may pay for evidence-linked assumption review, but no actual orders or qualified lead numbers were established.

## Funnel, unit-economics and cost ledger
- Visits, impressions, sample clicks, completed legitimate intakes, paying customers, verified revenue, CAC, fees, COGS, margin and net profit: **unknown**.
- Engineering time saved estimate: **0.5–1.0 hour** (low confidence): compared to manually auditing 404 navigation + source contract + tests; no measured counterfactual labor data.
- New code is original HTML and standard-library Python only. **No imported code, transitive dependencies, new notices or paid services.**
- No test checkouts, actual charges, buyer emails, production changes or customer records.

## Next ranked experiments
1. Inspect genuine required PR CI, then independently verify deployed 404 HTTP status / recovery links / mobile focus after an authorized release.
2. Measure consented aggregate sample→qualified intake→paid conversion, with honest missing-data flags and without collecting private customer data.
3. Reconcile PermitPlate checkout #16 and existing staging PR #152. The reusable Stripe Payment Link can be bypassed until provider-side deactivation or enforced receipt verification, which requires separate authorization.
4. Coordinate in-flight CaptureBrief attribution/intake PRs #167/#169/#170 instead of duplicate edits.
