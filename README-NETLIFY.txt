CaptureBrief Netlify deployment

Production site: https://capturebrief.netlify.app/

Deployment boundary
-------------------
Do NOT publish the repository root.

The repository now contains private/internal product code, tests, fixtures, rule-source machinery,
commercial operating documents, and research artifacts that are not website content.

Netlify is configured to:

  command = "bash netlify-build.sh"
  publish = "dist"

netlify-build.sh creates dist/ from an explicit public whitelist:
- public HTML pages
- _headers / _redirects
- favicon / robots / sitemap / webmanifest
- assets/

It deliberately excludes:
- capturebrief_core/
- tests/
- fixtures/
- .github/
- PRODUCT-CORE.md
- RULE-SOURCES.md / RULE-SOURCE-CATALOG.json
- Decision Evidence implementation docs
- outcome/business/source-policy operating files

CI runs tests/test_netlify_public_boundary.py and must fail if an internal path enters dist/.

Forms
-----
The public intake form remains in dist/index.html and Netlify Forms remains enabled.

Safe deployment sequence
------------------------
1. Merge only after Product Core CI passes.
2. Netlify runs netlify-build.sh.
3. Confirm the deploy publish directory is dist/.
4. Confirm the production deploy commit matches current main.
5. Verify /, /decision-evidence-sample.html, /data-handling.html and form detection.

Never work around a failed build by changing publish back to ".".
