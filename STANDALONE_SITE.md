# CaptureBrief standalone company site

This build publishes only the actual CaptureBrief website at https://capturebrief.retallyrecovery.com/. The existing `gh-pages` branch also hosts unrelated projects. It must not be copied wholesale to this company hostname.

## Cloudflare Pages settings

- Repository: `P00NSMASHER/capturebrief` (GitHub repository ID `1375917834`).
- Website production branch: `gh-pages`; product-engine changes remain on `main`. Verify the actual deployment revision after each release.
- Project name: `retally-capturebrief`.
- Root directory: repository root.
- Framework preset: None.
- Node.js: 22 or later; no package installation is required.
- Build command: `node build-standalone-site.test.js && node build-standalone-site.js`.
- Build output directory: `dist`.
- Custom domain: `capturebrief.retallyrecovery.com`, attached to this Pages project.
- Do not set a GitHub Pages CNAME, change the legacy GitHub Pages branch, or publish the entire source root.

## Publication boundary and continuity

`build-standalone-site.js` explicitly allowlists six CaptureBrief HTML pages, their actual styles/scripts/images/fonts, the favicon, and the fictional evidence example files. It generates robots.txt, sitemap.xml, `_headers`, `_redirects`, and build-info.json. The `_redirects` artifact maps previously shared `/sample`, `/sample.html`, `/decision-evidence-sample` and `/decision-evidence-sample.html` URLs to the actual published `/decision-evidence` page with HTTP 301, without copying the different Netlify-oriented `main` example into the company build. These redirects are part of the exact file manifest and are verified against the served Cloudflare response after deployment. Sibling projects, QA scripts, source code, state and configuration are excluded. A missing allowlisted source, symlinked source, missing local asset/link, or root Pages runtime/config file blocks the build. No Pages Functions or Worker are published.

Only the generated artifact gets root-based navigation, clean-route canonical/social URLs, the visible “Part of RETALLY Group” link to https://group.retallyrecovery.com/, and email-obfuscation opt-out comments. JP Enterprises remains the stated operator. The $149 price, recipient addresses, and already-paid intake remain unchanged. Evidence example bytes remain identical to their published hashes.

The current purchase policy is `SCOPE_FIRST_PENDING_SOURCE_READINESS`. An earlier main-only SAM observation lacked `SAM_API_KEY`. A later October 27, 2026, main-only observation verified that the secret was available and the bounded current public SAM Opportunities API request succeeded. This verifies access for one observed solicitation only: approved FY2027 catalog coverage, a complete reviewed case-specific action history, independently recoverable private evidence and customer-delivery approval remain unproven. All four homepage purchase placements now lead to the local scope request, including the mobile and no-JavaScript path. The source and standalone builder reject direct Stripe checkout links on every allowlisted HTML page. The evidence sample retains its original promise that scope and timing are confirmed before payment. `build-info.json` records this purchase policy.

This is a website intake correction, not deactivation of the existing Stripe payment link or a Stripe-account change. Existing paid requests, unverified checkout-return handling, and all refund rights remain supported. Restoring direct checkout requires a separately reviewed change backed by actual production source readiness; changing a flag or passing site tests does not supply that evidence.

The exact public file list, count, byte sizes, and SHA-256 values are generated in `build-info.json`. The fingerprint includes `_headers`. The current policy uses same-origin scripts, styles, fonts and connections; blocks frames, objects, workers and form submissions; and adds HSTS, a strict-origin referrer policy, no-sniff and restricted browser permissions. Inspect `STANDALONE_HEADERS` for the complete policy.

`build-info.json` identifies CaptureBrief, its canonical hostname, repository, source branch and `CF_PAGES_COMMIT_SHA` (preferred over other revision variables). It records both source-content and generated-artifact fingerprints.

## Request and trial contract

The current request composer includes company/contact identity, explicit unverified payment language, lossless legal identifiers, a complete manual-copy fallback, and the one-assumption free-pilot request. Free inquiries require one canonical public SAM.gov notice link and reject control-character injection, while all request types invalidate stale clipboard drafts on edits. The ten-business supervised limit is an operator admission gate, **not** a count enforced by this static no-send website. Those repairs carry forward the relevant intent of historical PR #50 on the current branded website. The trial is supervised: preparing a request neither admits a business, starts work, verifies sources nor sends email. The Python core on `main` remains the authority for intake and delivery readiness. Rebuild both public targets and verify the served bytes before claiming the request change is live.

## Acceptance and rollback

Run the build command. Verify the custom hostname, the five indexable pages, example downloads, fonts/images, a nested missing URL, the Group link and `/build-info.json`. Check that every new-review CTA reaches scope-first intake and that no allowlisted page emits a direct payment link, without sending intake. The source revision and purchase policy in build-info must match the Cloudflare deployment commit. Confirm unrelated projects and runtime paths return 404 on this hostname while remaining available at their legacy host.

Rollback only the `retally-capturebrief` Pages deployment if needed. The existing shared GitHub Pages site and the product-engine branch remain independent.

Cloudflare behavior references:
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/

