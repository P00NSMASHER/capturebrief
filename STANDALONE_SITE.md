# CaptureBrief standalone company site

This build publishes only the actual CaptureBrief website at https://capturebrief.retallyrecovery.com/. The existing `gh-pages` branch also hosts unrelated projects. It must not be copied wholesale to this company hostname.

## Cloudflare Pages settings

- Repository: `P00NSMASHER/capturebrief` (GitHub repository ID `1375917834`).
- Website base branch: `gh-pages`, not the repository's `main` product-engine branch. Set the Pages production branch to the reviewed release branch until this change is merged.
- Project name: `retally-capturebrief`.
- Root directory: repository root.
- Framework preset: None.
- Node.js: 22 or later; no package installation is required.
- Build command: `node build-standalone-site.test.js && node build-standalone-site.js`.
- Build output directory: `dist`.
- Custom domain: `capturebrief.retallyrecovery.com`, attached to this Pages project.
- Do not set a GitHub Pages CNAME, change the legacy GitHub Pages branch, or publish the entire source root.

## Publication boundary and continuity

`build-standalone-site.js` explicitly allowlists six CaptureBrief HTML pages, their actual styles/scripts/images/fonts, the favicon, and the fictional evidence example files. It generates robots.txt, sitemap.xml, `_headers` and build-info.json. Sibling projects, QA scripts, source code, state and configuration are excluded. A missing allowlisted source, symlinked source, missing local asset/link, or root Pages runtime/config file blocks the build. No Pages Functions or Worker are published.

Only the generated artifact gets root-based navigation, clean-route canonical/social URLs, the visible “Part of RETALLY Group” link to https://group.retallyrecovery.com/, and email-obfuscation opt-out comments. JP Enterprises remains the stated operator. Prices, checkout destinations, recipient addresses, intake behavior and product logic are unchanged. Evidence example bytes remain identical to their published hashes.

The generated decision-evidence sample CTA says that scope and timing are confirmed “before work begins,” consistent with the existing homepage, terms and direct checkout. This one-sentence correction is applied only to the generated page; the shared source file remains unchanged.

The artifact contains 33 files: 29 allowlisted public files, robots.txt, sitemap.xml, `_headers`, and build-info.json. The header configuration is included in the file hashes and count. It sets HSTS to `max-age=86400`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Content-Security-Policy: object-src 'none'; frame-ancestors 'none'; base-uri 'self'`. It adds no script or style restrictions.

`build-info.json` identifies CaptureBrief, its canonical hostname, repository, source branch and `CF_PAGES_COMMIT_SHA` (preferred over other revision variables). It records both source-content and generated-artifact fingerprints.

## Existing work

This migration adds build tooling without changing the existing HTML, CSS or JavaScript source files. CaptureBrief PR #50 (`pilot/site-unverified-payment-copy-20261018`) remains separate and unmerged. Its buyer-journey fixes are not implied by this migration. Once that work is reviewed and merged into the website source branch, rebuild the company site from the resulting revision and rerun its existing buyer-journey checks. The build transformation intentionally does not depend on the current form's field layout.

## Acceptance and rollback

Run the build command. Verify the custom hostname, the five indexable pages, example downloads, fonts/images, a nested missing URL, the Group link and `/build-info.json`. Check checkout and email destinations without purchasing or sending intake. The source revision in build-info must match the Cloudflare deployment commit. Confirm unrelated projects and runtime paths return 404 on this hostname while remaining available at their legacy host.

Rollback only the `retally-capturebrief` Pages deployment if needed. The existing shared GitHub Pages site and the product-engine branch remain independent.

Cloudflare behavior references:
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/

