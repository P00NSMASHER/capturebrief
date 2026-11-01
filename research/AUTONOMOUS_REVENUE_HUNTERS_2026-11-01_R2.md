# Autonomous Revenue Hunters | 2026-11-01 | Run 2: duplicate campaign attribution

## Verified ownership and deduplication
- Authoritative CaptureBrief repository: [P00NSMASHER/capturebrief](https://github.com/P00NSMASHER/capturebrief), default protected `main` at `c1339fae470088f48442684d7242819b07324298` when branch created. Open PR listing returned none. Prior payment-identity draft #173 is closed, and its fix is already included in #174's mainline integration. Do not reopen it.
- PermitPlate has active source-integrity [PR #160](https://github.com/P00NSMASHER/permitplate-nyc/pull/160) and [automatic Cloudflare deploy risk #154](https://github.com/P00NSMASHER/permitplate-nyc/issues/154). No PermitPlate branch/deploy changed.
- FreightRecovery/RecoveryOS active research ownership is outside this CaptureBrief branch. Do not duplicate the Unified Engine Evidence Lab or change x402 live settlement code.

## Hunter A: bounded public-buyer evidence
- [SAM.gov Contract Opportunities](https://sam.gov/opportunities) offers free primary notice discovery, saved searches and notice tracking. [GSA's small-business guide](https://www.gsa.gov/small-business/find-opportunities) directs bidders to forecasts and free SAM.gov discovery. These primary sources confirm a competitive *free notice-discovery baseline*, not any purchase of CaptureBrief or demand at $149.
- Hypothesis to falsify: small federal IT/cyber/cloud capture teams might pay for evidence-linked assumption validation and amendment/source-version reconstruction rather than another raw notices feed. The publicly visible procurement workflow supports the *problem framing* only. No buyer interview, provider-backed conversion, paid willingness-to-pay event or customer request has been verified in this run.
- The existing CaptureBrief public page in repository source describes a $149 one-time, up-to-five-assumption review, scope check before invitation-only checkout; the different documented free-check pilot is no-card, one assumption, at most ten independently reviewed businesses and **not an automatic $149 conversion**. Do not conflate offers or silently change prices/terms.

## Hunter B: reproducible integrity defect and focused code fix
- Baseline `assets/main.js`: `params.get('utm_source')` and `params.get('utm_campaign')` select the *first* value when a URL has duplicate query parameters. Example `?utm_source=paid&utm_source=organic` could be recorded as `paid`. This can bias channel attribution used in buyer-demand experiments. It is an **offline source-code defect**, not evidence of real tampering or observed conversion inflation.
- Patch: require exactly one value for each campaign field before applying the existing privacy-sensitive, bounded `cleanTag` validator. Duplicate identical or conflicting values, including percent-encoded key duplicates, become empty/unattributed. The other unique clean campaign field is retained. Source page never includes query strings or URL fragments.
- Adversarial regression: 6 new synthetic cases in `tests/test_public_attribution.py` covering conflicting source values, repeated identical source, conflicting campaign values, encoded-name duplicate, blank-plus-value duplicate and valid unchanged control. Existing valid single-source and malformed-contact cases retained. No customer data or requests used.
- Expected **source contract** before→after: conflicting `utm_source` `paid`→empty; unique `utm_campaign=November` remains `November`. This is NOT a measured traffic or conversion change.
- Modified only `assets/main.js` and `tests/test_public_attribution.py`, plus this research checkpoint. No dependencies, external source code, licenses/NOTICE requirements, lockfile, customer state, product configuration, prices, checkout or tracking vendors added.

## Hunter C: acquisition/delivery boundary
- The inspected `index.html` form uses Netlify's existing optional, consent-required `pursuit-qa-intake` POST; campaign labels are populated only in the form context. The site explicitly says it performs scope review before checkout and does not initiate a payment on submission.
- No live site submission or Netlify/Stripe provider metrics accessed; the public Netlify host could not be verified from the available external retrieval interface. **Live deployment state, visits, real submissions, admission, paid conversion, revenue and net profit remain unknown**; repository copy is not provider evidence.
- Keep current operator review, no-send boundaries and checkout authority intact. Never automate outgoing communications or processing real money as a conversion test.

## Verification, estimate and rollback
- Run `python -m unittest tests.test_public_attribution -v` on the exact PR branch, then observe the actual required Product Core CI and any release checks. Do not infer success until CI reports success. No browser UI changed; no browser-smoke claim from source tests.
- Hypothetical engineering rework avoided: **0.5–1 engineer-hour**, low confidence, assuming one future duplicate-parameter attribution incident would otherwise require manual investigation. **Actual saved time: unmeasured; revenue edge: unverified.**
- Rollback: close the draft PR or revert its isolated three-file patch. No automatic production deployment or provider migration is authorized by this change.
- Follow-up: independently verify the published site commit and actual form provider intake readiness; only then measure opt-in visits → confirmed requests → eligible admissions → first delivered value → actual paid conversions, with deduplicated denominators and explicit unknowns.

## Candidate priority
1. Check exact-head regression CI and repair any failures.
2. Verify provider-backed intake and public build revision read-only (no synthetic form submissions).
3. Evaluate a privacy-minimal, opt-in aggregate funnel only after knowing actual provider log and access permissions; avoid introducing third-party analytics before evidence.
4. Return to PermitPlate after #154 safe-deploy resolution, or capture a non-overlapping x402 genuine-buyer route probe.
