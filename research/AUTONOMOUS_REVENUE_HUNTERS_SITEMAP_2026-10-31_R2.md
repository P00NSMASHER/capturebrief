# Autonomous Revenue Hunters: primary proof-page discovery (2026-10-31 ET, run 2)

## Canonical owner and baseline
- Repository: P00NSMASHER/capturebrief, protected main `0aaa462d42078581bba9e3097e569dadc7c39576`. Its GitHub visibility is **public**, so this branch must not contain user/customer data or secrets.
- Previous experiment: draft [#170](https://github.com/P00NSMASHER/capturebrief/pull/170) controls visitor-supplied acquisition labels and adds real-browser QA. Open [#167](https://github.com/P00NSMASHER/capturebrief/pull/167) edits buyer-path preflight; [#169](https://github.com/P00NSMASHER/capturebrief/pull/169) edits free-check question UX; [#168](https://github.com/P00NSMASHER/capturebrief/pull/168) edits SAM source policy. This change touches none of their paths.
- **Reproduced source defect:** the home page prominently links `decision-evidence-sample.html`, and that page declares itself `index,follow` with a matching canonical URL. Yet `sitemap.xml` listed only the older `sample.html` evidence example. **1/2** high-intent, homepage-linked proof samples appeared in the published sitemap.
- Correction: insert the existing canonical decision-evidence sample URL, with no change to customer copy, pricing, form, server, entitlement, paid checkout, traffic collection or deploy configuration. **2/2** proof samples now listed. The sitemap is already copied into the Netlify public build.
- Regression: new `tests/test_public_sitemap_discovery.py` verifies both actual indexable proof pages are discoverable with matching canonical tags, URLs are absolute, unique and noncredentialed, `thanks.html` remains excluded/noindex, and robots/build include the sitemap.
- Test command: `python -m unittest tests.test_public_sitemap_discovery -v`; inherited Product Core CI runs `python -m unittest discover -s tests -v`. Exact-head CI must be inspected before release.
- There is no external code import or runtime dependency; Python stdlib test only. Revert this single PR to roll back. There is no build artifact or live customer deployment in this draft.

## Demand evidence and falsifiable acquisition hypothesis
- Official [SAM.gov opportunities](https://sam.gov/opportunities) supports public search, saved searches and changes; commodity alerts are free substitutes, so **verified source-version/assumption evidence** is the potential paid value, not access to federal listings.
- [Winning Bids AI](https://winningbids.ai/pricing) advertises $19/month entry tier. [BidStride](https://www.bidstride.com/pricing) advertises $150/month Radar; [Abierto](https://abierto.us/pricing) lists planned $39/month Scout but explicitly is not charging yet. These are public price *offers*, **not** independently verified paid purchases or demand for CaptureBrief.
- [Google Search Central sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) recommends listing preferred canonical pages. It does **not** promise crawling, indexing, traffic, submissions or revenue.
- Hypothesis: a small GovCon IT/cyber/cloud team checking an amendment against existing bid/no-bid assumptions may find the illustrated exact-source/version trail useful, then voluntarily request a public-only assumption review. Cheapest approved channel: existing SEO + source-linked worked examples, no new spend or outreach.
- Proposed future privacy-safe measurement, **not observed:** organic eligible page impressions and clicks, unique `#request` intent from that page, completed *consented* intake, verified eligible review, provider-backed paid order and net profit. Before/after totals, denominator, visitor cohorts, and attributed paid receipts are unavailable, **not zero**.
- No legitimate basis to infer conversion uplift, $149 paid willingness-to-pay, revenue, MRR, profit or search rankings from a sitemap edit.

## Hunter rotation / next tasks
- Buyer track: verify voluntary in-scope request count and reason codes using permissioned *aggregate-only* reporting, then distinguish qualifying demand from page visits. Avoid copying personal customer records to GitHub.
- Conversion track: maintain #167/#169/#170 ownership; on real release authorization reconcile exact live Netlify build SHA, deployed form behavior and accessibility before any marketing experiment.
- Delivery track: require opt-in consent and provider-backed test-mode fulfillment/entitlement before unattended charging. Existing Stripe account selection is interactive; **no metrics were retrieved**, no payment changes are authorized.
- All current PRs remain open and unchanged, no emails/drafts/sends, no deployment, paid spend or automation modification.
