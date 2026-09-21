# CaptureBrief deployment target

Updated: 2026-09-21, following the owner's explicit hosting correction.

## Authoritative website target

Use GitHub Pages, not Netlify.

- Repository: `P00NSMASHER/capturebrief`
- Website branch: `gh-pages`
- Canonical website URL: `https://p00nsmasher.github.io/capturebrief/`
- Product engine and its regression tests: `main`

The inspected website branch was at
`d4d9dea6e6adad230be0b49c3d7e06d5ace7f6c1`. Its `index.html` declares the
GitHub Pages canonical URL, uses the redesigned enterprise assets, and offers
an email-based scope request. Its website QA workflow is
`.github/workflows/site-quality.yml` on `gh-pages`.

These are repository observations, not a claim of a new deployment or a fresh
live-browser verification. Re-read branch heads and the actual Pages deployment
when verifying a release.

## Operating rules

1. Website changes must begin from the current `gh-pages` source and preserve
   its design, assets, and other project pages. Do not overwrite that branch with
   `main` or with an older Netlify-oriented static bundle.
2. Product-engine work belongs on `main`. Passing Product Core tests does not
   prove that a website change has been published to GitHub Pages.
3. Use Pages deployment evidence and the GitHub-hosted URL for website release
   verification. An old Netlify deploy, missing Netlify credentials, or Netlify
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
