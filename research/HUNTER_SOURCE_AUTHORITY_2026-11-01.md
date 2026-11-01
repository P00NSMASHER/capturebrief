# Revenue-product source hunters: 2026-11-01, current-action proof integrity

## Ownership, baseline and boundaries

- Canonical source: [P00NSMASHER/capturebrief](https://github.com/P00NSMASHER/capturebrief), `main` commit `c1339fae470088f48442684d7242819b07324298` inspected before branching.
- Dedicated [draft PR #177](https://github.com/P00NSMASHER/capturebrief/pull/177) branch: `hunter/revenue-20261101-authority-pagination`; source change `cb063bdcb4372eb293a4d5242d11d751ed0c1d6a`; regression suite `052d9e5484b3f3b58544a0b1f5df795c7cd31864`.
- The open [site attribution PR #176](https://github.com/P00NSMASHER/capturebrief/pull/176) owns `assets/main.js` and public attribution. This branch modifies only `capturebrief_core/authority.py`, a new isolated test file and this evidence note. No live website, payment, checkout, prices, deployment, buyer data or secrets altered.
- Main is governed by active ruleset 26263664 requiring `product-contract` and `windows-compatibility` checks plus a PR. Do not merge without actual exact-head required-check success.

## Confirmed reproducible defect

The newest [SAM Opportunities v2 observation guard](https://github.com/P00NSMASHER/capturebrief/blob/main/capturebrief_core/current_api.py) correctly rejects noninteger provider pagination fields. A separate downstream [current-action authority receipt gate](https://github.com/P00NSMASHER/capturebrief/blob/main/capturebrief_core/authority.py) still used `int(value)` on `total_records`, `returned_records`, `limit` and `offset`. Python accepts `int(True)==1`, `int(False)==0`, and truncates `int(1.9)==1` / `int(0.9)==0`. A structurally valid synthetic retained receipt with a *recomputed matching evidence hash* could therefore incorrectly pass the downstream complete-page check and be labeled `CURRENT_VERIFIED`. A matching hash alone does not attest truthful upstream observations. No evidence of malicious exploitation or a real customer impact is claimed.

**Minimal source fix:** Reuse the product's existing strict `_nonnegative_int` count validator with its `CurrentApiError` conversion into the existing fail-closed receipt finding. This keeps true JSON integers and decimal strings compatible, rejects booleans, fractions, invalid strings, null and negatives, and adds no dependency or external code. No new public API and no source-contract relaxation.

**Executable reproduction / proof:** `python -m unittest tests.test_authority_api_pagination_types -v`. The new test constructs a fully synthetic, source-approved, time-fresh receipt using the existing fake SAM response harness, mutates pagination, deliberately recomputes its canonical evidence hash, then checks actual end-to-end authority verdict and diagnostic. Cases: 11 malformed/negative/missing counts, one unchanged valid receipt and one decimal-string compatibility test. The suite is also included in `python -m unittest discover -s tests -v` and the existing required CI workflows. No fabricated price, purchase or customer activity.

## Public GitHub source comparison, explicit non-adoption

1. [python-jsonschema/jsonschema at c497561ea0a95f5aac09cd63d15eb1420eb7bbec](https://github.com/python-jsonschema/jsonschema/tree/c497561ea0a95f5aac09cd63d15eb1420eb7bbec), non-archived; exact [COPYING](https://github.com/python-jsonschema/jsonschema/blob/c497561ea0a95f5aac09cd63d15eb1420eb7bbec/COPYING) independently read 2026-11-01, MIT-style, latest inspected main commit dated 2026-10-07. Fits declarative validation if full source contracts become multi-field schemas, but a complete schema engine and its transitive dependencies are disproportionate here.
2. [pydantic/pydantic at 132df974eaf99818dd98988d21a175015857e9d9](https://github.com/pydantic/pydantic/tree/132df974eaf99818dd98988d21a175015857e9d9), non-archived; exact [MIT LICENSE](https://github.com/pydantic/pydantic/blob/132df974eaf99818dd98988d21a175015857e9d9/LICENSE) independently read 2026-11-01, current inspected main commit dated 2026-10-31. Mature structured validation alternative; larger runtime/native-core/versioning footprint and compatibility review would exceed this one field-typing fix.

**Decision:** Internal reuse of already-reviewed strict parser. No copied third-party code, newly installed packages, altered lockfile, new transitive license chain, or new NOTICE obligations. Candidate advisories and pinned release/dependency chain must be independently checked before *any future actual adoption*; this source scan alone is not an adoption security clearance.

## Hunter B, dedupe and benefits

- The authenticated owner repository inventory lists no standalone `RETALLY`, `FreightRecovery`, or `RecoveryOS` repo. Do not assume `github-value-hunt-ledger` is the canonical production engine. Its [RecoveryOS money PR #889](https://github.com/P00NSMASHER/github-value-hunt-ledger/pull/889) was independently checked and is **closed without merge**, not shipped; [x402-product-factory PR #60](https://github.com/P00NSMASHER/x402-product-factory/pull/60) remains open draft with separate ownership. No conflicting engine/factory edit or duplicate PR was made.
- Observed improvement: reject 11 fabricated/malformed pagination cases through the genuine current-action gate while maintaining two valid controls. This is a test outcome to be confirmed by exact-head GitHub CI, **not** a claim of live reduced incidents.
- Engineering-hours saved: **not measured**, rather than inventing days/weeks. Mechanism: reuse existing numeric validation avoids a separate dependency, schema migration and duplicated diverging parsing logic. Measurable future metric: incident reproduction/review minutes and release failures before/after adoption.
- No real revenue, buyers, net profit, paid demand or customer conversions verified.

## Next checkpoint

Inspect exact PR SHA and both required GitHub CI checks; repair any failures, and merge only if branch protection and standing release authorization genuinely permit it. Then advance a *non-overlapping* source-to-settlement idempotency contract in the authoritative RecoveryOS repo once ownership is demonstrably accessible. Keep factory watchdog and existing trial/attribution PR ownership separate. Rollback: revert this isolated PR; no production state changes.

## Follow-up: retained API resource-link container integrity (same draft PR)

- **Additional source-derived defect:** `_approved_api_contract_ok` used `evidence.get("resource_links") or []`, silently treating absent, `null`, `false`, `0`, empty string and empty object as an approved empty array. That disagreed with `current_api.validate_api_observation`, which requires a genuine JSON list. The original evidence SHA check does not establish that its payload's schema is valid; these controls recompute the SHA.
- **Smallest repair:** Remove the truthiness coalescing. Keep the preexisting `RECEIPT_APPROVED_API_RESOURCE_LINKS_INVALID` result; valid empty list and existing complete receipts remain compatible. No external dependency or copied code. Existing upstream candidates and exact licensing notes remain unchanged.
- **New regression evidence:** one negative-control loop over seven malformed collection values, a missing-property test, and a positive real-empty-list test. These exercise the actual current-action verdict, digest, and diagnostic. Test module now covers both strict pagination and link-collection data types.
- **Repro command:** `python -m unittest tests.test_authority_api_pagination_types -v`. CI must run on the **new** PR head before any merge. No mock customers, purchase, external contact, new service, payment, data transfer or deploy.
- **Engineering effort:** not measured. Estimated avoided duplication is qualitative only; no claimed saved engineer-days. Current change addresses a structural acceptance weakness, not a reported customer incident.
- **Portfolio coverage:** Verified owner repository `P00NSMASHER/x402-product-factory` exists but its 30+ pre-existing stacked draft PRs, including owned #60, make an independent overlapping implementation unsafe; do not modify that release stack. Authenticated repository inventory still shows no standalone canonical RETALLY/FreightRecovery/RecoveryOS source. Next actionable test is exact-head CI followed by a separate dedicated codebase provenance/ownership review.
