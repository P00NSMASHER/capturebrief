# Verified public release artifact

CaptureBrief's company website is https://capturebrief.retallyrecovery.com/,
served by the existing Cloudflare Pages standalone build from `gh-pages`.
The shared https://p00nsmasher.github.io/capturebrief/ site is a separate legacy
surface. See `DEPLOYMENT-TARGET.md` and `STANDALONE_SITE.md` on `gh-pages`.

The Netlify-named build and ZIP below are legacy packaging tools. They do not
select the current hosting provider or authorize a website deployment. Product
engine changes and their tests belong on `main`; do not publish the repository root.

## Build and publication are separate

`Public Release Artifact` runs the full regression suite, executes `netlify-build.sh`,
and creates `CaptureBrief_Public_Release.zip` from the exact checked-out Git revision.
The ZIP has `index.html` at its root, all 22 explicitly approved public files (including the four x402 discovery paths), and a
`release-manifest.json` listing their byte lengths and SHA-256 values.

Packaging rejects extra/missing files, new unreviewed assets, symlinks, modified build
output, an incorrect revision, and dirty tracked source. The companion receipt hashes
the archive itself. Stable ZIP metadata makes repeat builds byte-identical.

Only the public ZIP, archive hash, and release receipt are retained as the workflow
artifact. No raw product code, tests, fixtures, customer data, source catalogs, or
operating documents enter that deployment ZIP. No deployment credentials are required
or embedded. All artifact receipts explicitly say the build is not deployment proof.

## Current company-site release handoff

The legacy release ZIP is packaging evidence, not a company-site deployment
instruction. Begin website changes from the actual current `gh-pages` branch,
preserve its existing project pages and use its site-quality workflow. The
existing `retally-capturebrief` Cloudflare project publishes only the standalone
build's allowlisted `dist/` artifact. Do not replace the website branch with
product-engine `main` or with the legacy ZIP.

After an authorized release, independently verify `/build-info.json`, the served
homepage, sample and assets at https://capturebrief.retallyrecovery.com/ against
the intended website revision. Verify the shared GitHub Pages surface separately
when it changes. A successful product build or deployment job does
not prove the intended content is live. Do not submit forms or send customer
messages without the owner's specific approval.

## Fulfillment readiness corrections

The operator plan now distinguishes old-case readability from customer-bundle eligibility.
A legacy case without the required Decision Evidence trace reports `TRACE_UPGRADE_REQUIRED`,
not `READY_TO_BUILD_DELIVERY`. Complete traced cases must pass the same audit/trace
conditions used by the bundle builder; outstanding work remains visible separately.

A `HYBRID` task stays in the human-review lane even when an upstream flag permits an
automated substep. Only an explicit boolean flag plus `AUTOMATED_LOCAL` or
`AUTOMATED_APPROVED_SOURCE` qualifies the whole task for the automation lane.

These are planning outputs, not an execution engine. A complete bundle and a change-watch
result never authorize external communication. See `OUTBOUND-COMMUNICATIONS.md`.

Reference documentation:
- https://docs.github.com/en/actions/tutorials/store-and-share-data
- https://docs.netlify.com/deploy/create-deploys/
