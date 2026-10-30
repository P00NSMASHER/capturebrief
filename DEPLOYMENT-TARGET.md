# CaptureBrief deployment target

Updated: 2026-10-27 after checking the current standalone-site build contract.

## Authoritative website target

The current company site uses the existing Cloudflare Pages standalone build.
The shared GitHub Pages site is a separate legacy surface.

- Repository: `P00NSMASHER/capturebrief`
- Website branch: `gh-pages`
- Canonical company website: `https://capturebrief.retallyrecovery.com/`
- Existing Cloudflare Pages project: `retally-capturebrief`
- Build command on the website source branch:
  `node build-standalone-site.test.js && node build-standalone-site.js`
- Publish only the allowlisted `dist/` artifact. The full branch also contains
  sibling projects and must not be deployed wholesale to the company hostname.
- Legacy shared website: `https://p00nsmasher.github.io/capturebrief/`
- Product engine and its regression tests: `main`

The standalone build is documented in `STANDALONE_SITE.md` on `gh-pages`.
It sets the company hostname and produces `/build-info.json` with source and
artifact fingerprints. Website QA remains on `gh-pages`; product-core QA is
on `main`. The old Netlify-oriented `main/index.html` is not the company site.

These are source/build contracts, not a claim that a proposed change has been
deployed. Verify live bytes and `/build-info.json` against the reviewed website
revision after each release.

## Operating rules

1. Website changes must begin from the current `gh-pages` source and preserve
   its design, assets, and other project pages. Do not overwrite that branch with
   `main` or with an older Netlify-oriented static bundle.
2. Product-engine work belongs on `main`. Passing Product Core tests does not
   prove that a website change has been published to the company hostname.
3. Use Cloudflare deployment evidence, the company hostname and its
   `/build-info.json` for company-site release verification. Check the shared
   GitHub Pages site separately when it changes. An old Netlify deploy, missing Netlify credentials, or Netlify
   form submission counts are not CaptureBrief launch blockers or current-site
   conversion metrics.
4. Older Netlify-named scripts, reports, and release archives are legacy
   artifacts. Their existence does not select the hosting provider or authorize
   a Netlify deployment. Preserve them unless a separately reviewed cleanup is
   needed; do not delete an account or site as part of this correction.
5. Keep customer records, internal case payloads, credentials, and operator
   evidence out of the website publication branch.
6. Website intake does not authorize an outbound reply. Every external email
   or message still requires the owner's approval of that specific message.

This document supersedes older hosting assumptions. It changes no price,
customer promise, source-evidence gate, or communication approval rule.

## Legacy PA x402 monitoring (2026-10-22)

The retired `capturebrief.netlify.app` discovery/proxy endpoint is not a
CaptureBrief website health target. The `PA x402 legacy contract regression`
workflow retains only offline discovery and single-forward proxy tests; it must
not poll that origin or register it as a replacement for the current seller.
The workflow boundary has a regression test to prevent either action returning.

Live PA x402 deployment, discovery and payment checks belong to
[`P00NSMASHER/x402-product-factory`](https://github.com/P00NSMASHER/x402-product-factory).
A passing compatibility test here proves neither live availability nor a paid
transaction. The company hostname and shared GitHub Pages site are separate
publication targets, both built from the website branch rather than engine `main`.
