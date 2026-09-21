# Verified public release artifact

The existing CaptureBrief Netlify project remains the deployment target. Do not create
a replacement site or publish the repository root.

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

## Existing-site handoff

Download the workflow artifact for the intended main-branch commit. Extract the outer
GitHub artifact first; `CaptureBrief_Public_Release.zip` is the actual website package.
Extract that ZIP to obtain the public output folder for a manual deployment to the
existing project's Deploys page. Do not upload the outer artifact folder or the repository.

After an authorized publish, verify the existing production homepage, sample page,
local assets, and the served `release-manifest.json`. Confirm that its `source_commit`
and file hashes match the retained artifact. Then inspect recognized intake form fields.
Do not label the release live merely because GitHub tests passed or Netlify accepted a job.
Do not submit test forms or send notification emails without specific approval.

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
