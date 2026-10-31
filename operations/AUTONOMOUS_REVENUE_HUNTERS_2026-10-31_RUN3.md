# Autonomous Revenue Hunters — 2026-10-31 run 3 (source bound)

## Canonical state and ownership
- This advances existing draft https://github.com/P00NSMASHER/capturebrief/pull/167, against the `gh-pages` standalone public-site branch. It does not edit the product-engine `main` branch or merge to the deployed site.
- PermitPlate payment-gating changes remain exclusively owned by https://github.com/P00NSMASHER/permitplate-nyc/pull/152. No parallel checkout change.
- Prior PR #167 commit `5fb6051c2c492143850697ba71474eb7271646fb` had six passing GitHub checks (Chromium/WebKit, production no-send and Windows/Linux path selection).
- This run commits only local browser code, accessible wording and real buyer-flow checks. No new dependencies, vendor source imports, telemetry, HTTP requests, storage, payments or backend changes. No customer data used.

## Hunter A — market/buyer evidence (accessed 2026-10-31)
- Authoritative free competitor: https://sam.gov/opportunities . Contract opportunity search is available to anyone without an account; accounts add saved searches and following. Mere opportunity discovery cannot justify a paid product.
- Vendor-published competing product: https://www.highergov.com/state-local/ currently lists individual at **$500/year** and team at **$2,500/year**. Different product/billing model than CaptureBrief's **$149 one-time human-reviewed pursuit assessment**; prices do not prove a buyer values CaptureBrief.
- Documented failure mode from independent primary evidence: GAO sustained [Effective Communication Strategies, LLC; Corps of Engineers, B-423993/B-423993.2 (Feb. 18, 2026)](https://www.gao.gov/products/b-423993%2Cb-423993.2) after **ten solicitation amendments** and unreasonably short response windows. This establishes that amendment tracking and timing can matter materially to real bidders. It does **not** establish that those bidders would pay for CaptureBrief or that CaptureBrief could have prevented that protest.
- Specific *hypothesis*, not validated segment: small federal bid teams with an already identified solicitation that need to reconcile amendment, eligibility, submission and controlling-rule evidence before committing proposal effort. Value claim must be tested with genuine inbound demand, repeatability and completion costs. No qualified lead, paid conversion, retention or margin was observed during this run.

## Hunter B — reproducible local buyer friction
- Before: after pasting a valid public SAM.gov notice in the V4 preflight, clicking **Ask for an independent review** opened the request section but left `#opportunity-url` blank. Thus the same URL needed manual second entry. The notice input said **(optional)** despite being necessary for the V4 review-ready label. These are reproducible source-code behaviors, not observed site analytics.
- After: the existing explicit review-link click locally copies only an already validated canonical SAM notice URL into a **blank** request URL field and emits its normal `input` event. It never replaces a buyer-supplied URL, uses network/storage, opens checkout or sends an email. Invalid/missing notice is not transferred. Existing review CTA keeps scope-first state.
- Added Chromium browser regression assertions for valid handoff, non-overwrite, invalid-link rejection, scope-first, clarity and accessibility help; retained the previously added 1,024-state safety tests.
- Deterministic flow proxy: valid source URL manual re-entry count **1 → 0** per opt-in click on a blank intake. No measured user-time, visits, conversions or orders; do **not** quote this proxy as revenue or a conversion lift.
- No imported external library: this is a small, original event handler, avoiding any license and transitive-dependency changes.

## Hunter C — opt-in infrastructure and revenue evidence boundary
- The buyer explicitly initiates a local transition from evidence checklist to unsent email request. No automated selling or outbound communication.
- Website's advertised price remains unchanged; no card handling or paid checkout was added.
- Linked Stripe account readback requires interactive account selection in this environment and cannot complete unattended. This means **actual product receipts, net profit and conversion metrics are unverified/unknown, not zero**.
- No collection of personally identifying form inputs or tracking scripts was introduced.
- PR remains **draft/unmerged** to prevent triggering live GitHub Pages/Cloudflare release during review. Required verification: genuine CI Chromium/WebKit tests plus site-owner QA before any protected merge. Rollback: revert this branch's scoped commits or the PR as a whole.

## Next priority
1. Examine the six native GitHub CI checks against the newest head SHA and repair failures without bypass.
2. Keep PR #167 draft for independent website-owner review; do not deploy without the relevant authorization.
3. Get provider-attested PermitPlate Stripe-link and fulfillment readiness through separate approved access before turning on payment.
4. Test one inbound small-bid-team segment with lawful opt-in traffic and independently attributable qualified requests; until then WTP and unit economics unknown.
5. Only after explicit approval, measure privacy-safe `preflight → request started → buyer-confirmed send` steps; never count a generated email draft as a completed request.

Estimated engineering time saved: **not credibly measured**; one redundant field entry eliminated in a deterministic test, with no observed real-user volume.
