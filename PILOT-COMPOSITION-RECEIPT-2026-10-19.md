# CaptureBrief — proposed release composition acceptance (technical only)

**Date:** 2026-10-19 UTC  
**Decision:** TECHNICAL COMPOSITION PASS; PRODUCTION / PAID PILOT STILL ON HOLD.

This receipt documents a temporary, no-write-to-origin integration replay
of six **unmerged** proposed pull requests. It does not authorize merging,
payment acceptance, procurement decisions, customer messages, source
certification or a live 14-day watch.

## Exact release inputs

| Target | Pull request | Immutable candidate head |
|---|---|---|
| Customer website / gh-pages | #50 | 2f5af397fc5d46e6f919f11b0f6e3701df69c665 |
| Pilot core, source-index gates, watch | #51 | b302d137f9a562549384bbe7ea65bece2f4e8cb8 |
| Private website-draft intake parser | #52 | c95fd399c3d3816ac02e628d86347ff96b263bdc |
| Official SAM public CSV/S3 transport security | #53 | cf441e8d580af3a7d147d2884b7b3814fdf28e12 |
| Unrelated PA x402 CI YAML parse fix | #54 | 567c648ac91f23423a808b85ec3c617a919dcc36 |
| Live Stripe three-record reconciliation | #55 | bbbac444705b0a95ea4af12430c287a984b427ee |

Base public Python core: main at 12d90024f053a78ead7936abf092931fce240d3e.
Production website: gh-pages at 415edcaf1bc05f522e22141b3b59cdd9a7c6a0a0.

The workflow builds a local ephemeral branch and merges the five main-based
candidates with Git. It checks each fetched branch against the exact pinned
head SHA, rejects unresolved merge conflicts or movement of upstream heads,
and separately checks out the immutably pinned gh-pages candidate.
**It does not push, merge, deploy, charge, contact, or run a source fetch.**

## Results

Original composition run: #39272506993
https://github.com/P00NSMASHER/capturebrief/actions/runs/39272506993

That first replay found a real Windows test-fixture defect: SQLite connections
were left open by a test fixture, causing WinError 32 when cleaning up temporary
source-index files. This was repaired on PR #51 by explicitly closing every
fixture SQLite connection, without relaxing source verification or the
production database's own fail-closed rules.

Corrected exact-candidate composition run: #39272784471
https://github.com/P00NSMASHER/capturebrief/actions/runs/39272784471

- All five main-based PR candidate commits composed without conflicts.
- **Linux**: 508 Product Core unit tests PASS.
- **Windows**: 101 targeted pilot, history-index, payment and security tests PASS.
- **Chromium + WebKit**: website draft -> actual Python intake parser ->
  fictional Stripe reconciliation PASS. This includes payment-forgery,
  refund, wrong-account, stale source, protected data and no-send boundaries.
- No live Stripe records, API keys, production secrets, private customer data,
  actual customer deliveries or real customer communications were used.
- The PA x402 workflow's branch-push startup failures on main were handled as
  a separate existing defect; the proposed YAML fix is included in the
  combined test tree, but **an actual production x402 job is not accepted
  solely by this composition replay**.

## Independent release decision: REQUIRED / NOT ISSUED

The following must be evidenced separately before shipping, even if the
composition tests are green:

1. Independent reviewer approvals for the exact PR heads and any required
   target branch protection, including separate approval before deploying
   public gh-pages changes. No review can be manufactured by tests.
2. Human-reviewed, authoritative FY2027 SAM source-catalog inventory
   and a private, complete, fresh archive/source index with original
   publisher bytes and independently checked digests for all required slots.
   An automated original FY2027 SHA-256 alone does not cover all years.
3. Real approved in-scope IT/cyber/cloud public-source case, verified buyer
   scope, authenticated controlled inbox intake, processor-paid live order
   if appropriate, human source/rule review and original delivery ZIP receipt.
4. Real 14-day scheduled source-operation proof from **genuine** automatic
   checks and immutable previous-receipt chain, including missing/stale/changed
   cases, not a simulated 14-day clock replay.
5. Authorized private machine/host, access control, retention/privacy policy
   and verified backups before any actual customer case is stored.
6. Specific explicit approval for each outgoing customer email/message.
   The website draft, automation output and Stripe redirect authorize
   no communication.

**Do not label this a production rollout, an independent release acceptance,
a paying customer pilot, or an independently certified service.**

## Reproduction

The read-only workflow lives at
.github/workflows/capturebrief-release-composition.yml on this branch.
It is intentionally restricted to this QA branch and an explicit manual
dispatch after approval. It runs no periodic schedule. To repeat safely,
verify branch heads are unchanged or update the pinned SHAs, rerun the
synthetic composition, require Linux/Windows and browser PASS, then
request a separate independent release review.

## FY2027 privately retainable original candidate

PR #53 adds a SHA-pinned operator utility (scripts/retain_fy2027_candidate.py) for an authorized private machine, using only the official public SAM Data Services FY2027 download entrypoint and its exact guarded S3 object handoff. It checks the full 1,607,260 bytes against SHA-256 7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce **before** retaining immutable original bytes and an unapproved provenance receipt outside the public repository. Its tests are entirely fictional/offline. The earlier code was first exercised on the user's authorized workstation, and the FINAL tested PR #53 command has now run successfully in a separate local acceptance directory and does not change the approved catalog/index. The final QA workflow adds its tests to Windows and the full Linux corpus.

## Real SAM temporary signed transport verification

On October 19, 2026, official SAM Data Services returned an HTTP 303 to `falextracts.s3.amazonaws.com` for FY2027, with six temporary `X-Amz-*` signing parameters. PR #53 now narrowly approves only the exact paired first-party S3 object path and a validated short-lived AWS Signature V4 query; it does **not** approve arbitrary S3 URLs or source content.

The actual guarded repository retention command passed against the live official download route in [CI #39304861281](https://github.com/P00NSMASHER/capturebrief/actions/runs/39304861281), retrieving the original 1,607,260 bytes, SHA-256 `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`. [CI #39305721653](https://github.com/P00NSMASHER/capturebrief/actions/runs/39305721653) independently re-ran the current signed-transport command successfully after idempotent receipt improvements; original bytes were retained only ephemerally by those CI jobs.

New tests reject wrong-year objects, forged/expired signers, duplicate signature fields, malicious redirects, printed signed-link transport errors, mutated retention receipt fields and misleading fresh timestamps on rechecks. Windows and Linux Product Core regressions passed at PR #53 head `6ad99fbceacf537a5e4eb400e42d9a6f4a3516b3`. The production catalog remains pinned to FY2026; a single FY2027 source file and any automated hash check still cannot certify complete original history or independently approve customer work.

## Retention receipt idempotence and combined Windows check

The pinned PR #53 source utility now accepts legitimate current, short-lived SAM.gov Signature V4 redirects to the exact original FY archive object, and suppresses transport-error traceback links to presigned secrets. Its immutable original-file receipt can be replayed with the SAME source bytes without rewriting the original observation timestamp; it refuses altered existing receipt fields, byte-format changes and duplicate keys.

A prior expanded Windows composition detected a test-fixture restoration that had converted canonical LF receipt bytes to CRLF, making the integrity guard correctly reject the modified fixture. The fixture was corrected to restore original bytes byte-for-byte. Product Core Linux/Windows completed successfully at the new PR #53 head `6ad99fbceacf537a5e4eb400e42d9a6f4a3516b3`. Require the final all-PR composition run for that exact SHA before claiming full combined release QA PASS. This still does not authorize FY2027 source-catalog approval or a real customer release.


## October 19 final direct Windows acceptance and hard-link correction

On the user-authorized Windows device, a clean local checkout of the verified PR #53 head `cf441e8d580af3a7d147d2884b7b3814fdf28e12` ran `scripts/retain_fy2027_candidate.py` with a new private per-user retention directory. The initial older implementation uncovered a Windows-only source-publication defect: a read-only hard-linked temporary file could not be deleted, leaving an unreceipted duplicate even though its digest matched. The fix in `capturebrief_core/atomic_io.py` now defers the Windows read-only attribute until AFTER removing its hard link, while preserving SHA-256 checks and the read-only final original. New `tests.test_atomic_io` coverage checks Windows source preservation, no lingering tmp files, read-only status and repeat idempotence.

**Observed acceptance on the exact final candidate:** local command exit 0; exact 1,607,260 original bytes; SHA-256 `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`; original read-only; independent receipt SHA matches; no stray temporary files; signed SAM source transport correctly bound to `falextracts.s3.amazonaws.com`. A subsequent direct execution also exited 0 with the ORIGINAL receipt bytes and observation timestamp unchanged. The earlier rejected temporary pair was deleted only after independently matching its hashes to the accepted original. No sensitive user file paths or temporary signed query strings are recorded publicly.

**Remaining nontechnical holds:** The privately retained file is still only **ONE** FY archive original and is not a complete 34-year source index, and no independent human catalog approval has been granted. BitLocker/whole-disk encryption is **unverified** because read-only operating system queries returned access denied; encrypted off-device backup remains unverified. No actual customer charge, message, release, real delivered ZIP or live 14-day watch has been represented as complete. Protected independent GitHub code review is required before any main or gh-pages merge.

## October 19: FY2027 unapproved source-index coverage audit (still NO RELEASE)

PR #51 now includes an additional **read-only, candidate-only** diagnostic at
`scripts/audit_fy2027_candidate.py`. It validates the exact previously
recorded, unapproved 36-file SAM listing before checking an existing PRIVATE
index against the **34 required observed FY1969/FY1970/FY1980/FY1981 and
FY1998–FY2027 archives, plus one ACTIVE slot (35 total)**. Future-listed
FY2029/30 are excluded; an invented FY2028 is rejected. Missing, stale,
mismatched-size, unverified and SHA-mismatched slots are distinguished.

Example for an authorized operator with an already existing private index:

    python scripts/audit_fy2027_candidate.py --private-index PRIVATE_INDEX_PATH --verify-bytes

The command does not create an index, import the separately retained FY2027
candidate, fetch source bytes, certify original publisher authenticity,
approve a catalog or release a customer. An old 2026-complete synthetic index
is missing candidate-only FY1969, FY1981 and FY2027; this is a synthetic
comparison, **not** a claim about the real private workstation's inventory.

A newly updated PR #51 exact head `b302d137f9a562549384bbe7ea65bece2f4e8cb8`
passed its direct Product Core Linux and Windows CI. The revised ephemeral
all-PR composition passed [run #39316089037](https://github.com/P00NSMASHER/capturebrief/actions/runs/39316089037)
at QA SHA `588d9c48d7b60175ec934ca01f0418dd226e5ab7`:
**523 Linux tests, 126 Windows tests**, plus successful Chromium and WebKit
browser → private fictional case → Stripe no-send/rejection checks. The QA
workflow pins the new #51 commit. This section is a later documentation
addition, so that cited run validates the code composition BEFORE this
documentation-only receipt update; any subsequent exact-head CI is a
separate evidence event.

Despite this technical pass, FY2027 production catalog remains pinned to
FY2026; the genuine PAAM source index is not yet audited; the 34-year original
history is not complete or independently reviewed; machine encryption,
encrypted off-device backup and independent reviewer approvals remain
unproven. No real customer case, message, charge, release or deployment.
