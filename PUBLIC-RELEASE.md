# Verified public release artifact

> **Historical Netlify release artifact instructions — not the current website deployment path.**
> CaptureBrief's authoritative website uses GitHub Pages, the gh-pages branch,
> and https://p00nsmasher.github.io/capturebrief/. Do not publish the repository root.
> The older Netlify ZIP, manual deployment and form steps below are retained
> as historical build instructions, not as an active production-release procedure.

## Build and publication are separate

`Public Release Artifact` runs the full regression suite, executes `netlify-build.sh`,
and creates `CaptureBrief_Public_Release.zip` from the exact checked-out Git revision.
The ZIP has `index.html` at its root, all 18 explicitly approved site files, and a
`release-manifest.json` listing their byte lengths and SHA-256 values.

Packaging rejects extra/missing files, new unreviewed assets, symlinks, modified build
output, an incorrect revision, and dirty tracked source. The companion receipt hashes
the archive itself. Stable ZIP metadata makes repeat builds byte-identical.

Only the public ZIP, archive hash, and release receipt are retained as the workflow
artifact. No raw product code, tests, fixtures, customer data, source catalogs, or
operating documents enter that deployment ZIP. No deployment credentials are required
or embedded. All artifact receipts explicitly say the build is not deployment proof.

## Current GitHub Pages release handoff

The older Netlify release ZIP remains historical packaging evidence only,
not a GitHub Pages deployment instruction. The authoritative website
must be changed from its actual gh-pages branch, never from product-engine
main or by uploading the older Netlify artifact bundle.
Use the existing gh-pages site-quality workflow for independent website QA.

After an authorized Pages release, independently verify the served homepage,
sample page and assets at https://p00nsmasher.github.io/capturebrief/.
CI success or deployment acknowledgement is not proof of publication.
Do not submit test forms, contact customers or send messages without approval.

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
