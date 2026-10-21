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


## October 19 — seven-PR combined storage and pilot composition

A new exact-head, ephemeral **NO DEPLOY** synthetic composition tested
**seven** main-target candidate heads together, rather than just the
five pilot-repair heads. Pinned inputs were:

| Candidate | PR | Exact head used |
|---|---:|---|
| Pilot source coverage/watch | #51 | `b302d137f9a562549384bbe7ea65bece2f4e8cb8` |
| Buyer draft-to-private intake | #52 | `c95fd399c3d3816ac02e628d86347ff96b263bdc` |
| SAM signed-redirect security/original retention | #53 | `cf441e8d580af3a7d147d2884b7b3814fdf28e12` |
| Live Stripe account receipt safeguards | #55 | `bbbac444705b0a95ea4af12430c287a984b427ee` |
| CI typed x402 addresses | #54 | `567c648ac91f23423a808b85ec3c617a919dcc36` |
| Operator-only encrypted private backup | #57 | `b77f48a623a622c1f297fd819290bbfda5415bdf` |
| Guarded FY archive capacity/compressed original (stacked #53/#58/#59/#60) | #61 | `ef478f497472a10eeba1388ba6cfd8327e44a2b6` |
| Separate website checkout | #50 | `2f5af397fc5d46e6f919f11b0f6e3701df69c665` |

**Actual [GitHub Actions run #39356771333](https://github.com/P00NSMASHER/capturebrief/actions/runs/39356771333)**,
at QA workflow head
`02e483273922b35acab6a58410ead40dcf2872c3`:

- **Linux:** 561 actual combined unit tests PASSED.
- **Windows:** 164 real combined tests PASSED, **one skipped**.
- **Chromium and WebKit** integration PASSED, including browser-to-Python
  case, fictional processor negative controls and no external POST.
- Installed optional `cryptography==46.0.4` into CI runners for the
  synthetic AES-256-GCM/backup tests only; production core does not
  depend on this package by merely merging source.

All Git merges occurred exclusively inside discarded CI workspaces.
No protected main or gh-pages branch was modified. Neither the test
result nor any candidate PR is a valid independent human release
review; **all seven source PR heads remain unmerged** at this observation.

**Mandatory NO-GO remains:** approved FY2027 34-year original-source
catalog and complete hash-bound private history, genuine first
customer scope/payment/delivery, actual fourteen-day monitored case,
administrator-verified host disk encryption, actual encrypted
off-device backup with independently recoverable key and proven
off-device restore, independent code/security review and protected
production-release authorization. Local DPAPI-backed FY2027 AES copy
and one local restore were completed separately on PAAM-L044, but
their recovery key remains machine/profile bound and no off-device
disaster recovery is proven. Compression's measured 4.60 GiB proxy
is not guaranteed full archive storage or index/backup capacity.


## October 19 — real FY2027 history blank-identifier regression and final integration

This is a further exact-head **NO-DEPLOY** integration replay of the same
seven proposed main-target candidate PR heads as the earlier successful
composition, with **PR #51 source-coverage head updated** from
`b302d137f9a562549384bbe7ea65bece2f4e8cb8` to
`ac93aa91873629f45918c491175170adbe031689`.
This new PR #51 head blocks normalized **blank `Sol#`** from being
used to associate unrelated source notices into a history family.
The official genuine FY2027 original has **seven** such missing source
identifiers, motivating a specific regression. Its exact
1,607,260-byte source SHA-256 remains
`7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`.

[Actual Actions #39359448066](https://github.com/P00NSMASHER/capturebrief/actions/runs/39359448066),
running at QA workflow SHA
`1cfdd0693694d6a33110418d94593674322e4b21`:
**563 Linux tests PASSED, 166 Windows tests PASSED (1 skipped)**,
and Chromium/WebKit browser-to-case and fictional payment
no-external-POST integration **PASSED**. PR #51's own
[Product Core #39359171817](https://github.com/P00NSMASHER/capturebrief/actions/runs/39359171817)
also passed Windows and Linux.

On actual PAAM-L044 **Python 3.13**, the new PR #51 head and
still-reviewed compressed security PR #61
`ef478f497472a10eeba1388ba6cfd8327e44a2b6`
were merged **only in a disposable local checkout**, resulting in
unpublished local composite commit
`1f8fb888c309869c25c0d33db8273ea75146a66e`.
The **26 targeted Windows source/history tests PASSED**; the
uncomposed PR #51 inherited an older Windows read-only hardlink cleanup
bug, separately corrected in PR #53, explaining why a standalone
PR #51 Python 3.13 run cannot substitute for actual composed testing.

The exact retained FY2027 original was then parsed into a **temporary
private disposable SQLite index**, twice. Its 1,104 notice rows,
one source snapshot, 1,104 distinct notice IDs and 7 empty Sol#
values were verified; the second ingest was idempotent. A specific
actual source notice with an empty Sol# was then presented to the
composed history-issue function; it correctly rejected that proposed
family join. The original public catalog guard independently raised
`ArchiveCatalogStale` because production catalog approval still ends
at **FY2026**. The temporary index and local synthetic merge checkout
were deleted after the tests. No real customer data was present.

A separate read-only early-year semantic probe read **five tiny
first-party SAM.gov CSV originals only in RAM**, checking the exact
signed transport, full public content SHA-256, required schema and
aggregate rows (FY1969: 0; FY1970: 3; FY1980: 1; FY1981: 0;
FY1998: 85). Both FY1969 and FY1981 are identical valid header-only
685-byte originals. The SHA-256 / sample counts are stored as
**unapproved evidence** in PR #58's
`research/fy2027_early_archive_full_byte_observations_20261020.json`
and tested by PR #58's passing
[Linux+Windows Product Core #39360108215](https://github.com/P00NSMASHER/capturebrief/actions/runs/39360108215).
None of these five originals was durably retained or independently
approved for the production catalog.

**Decision: still NO-GO.** The real FY2027 file remains a single
retained original, not a 34-year approved history. Encrypted local
DPAPI-backed FY2027 backup and a genuine same-PC restore are proven,
but independently recoverable off-device key escrow, an actual
restoration from remotely stored ciphertext, BitLocker disk encryption,
approved production-source index, independent PR review, verified
customer payment and fourteen-day live case watch remain unverified.
No main/gh-pages merge, paid customer release, actual customer
contact, live charge, independent signoff or production deployment
was performed.


## October 19 — NoticeId and strict original-byte decoding final composition

The verified live original FY2027 source contains **1,104 notices**,
seven blank `Sol#` fields, **zero blank `NoticeId` fields**, and
no observed undecodable values. A separate invented-byte regression
proved that the earlier importer would nevertheless accept an absent
`NoticeId` as an indexed record and silently replace undefined cp1252
bytes inside `NoticeId` with U+FFFD. Both paths could corrupt
source-to-notice identity in a history mistakenly reported complete.

The final PR #51 candidate source at
`21f0e188e4490a65bafd711c478b60562f794384` now:
- Rejects blank normalized `Sol#` input **before a family join**;
- Rejects source rows missing their primary `NoticeId` before any
  row can be registered as a current source snapshot, with atomic
  SQLite rollback;
- Rejects invalid CSV characters via `errors="strict"` instead of
  silently altering evidence identifiers;
- Preserves legitimate zero-row header-only archives and valid
  Windows-1252 accented text without alteration.

[Product Core #39360792881](https://github.com/P00NSMASHER/capturebrief/actions/runs/39360792881)
passed Linux and Windows at this exact PR #51 head. Genuine local
PAAM-L044 read-only testing confirmed that the authentic FY2027 source
still strictly decodes, ingests exactly 1,104 rows into an ephemeral
unapproved SQLite source index and replays idempotently. The temporary
database was removed, and full-coverage checks still blocked due to
an approved catalog ending at FY2026. On-demand guarded source checks
of five small official FY original CSVs (1969, 1970, 1980, 1981,
1998) also passed strict text decoding, verified required headers
and remained **in-memory only**, with no durable source retention.

The combined [NO-DEPLOY acceptance run
#39360914919](https://github.com/P00NSMASHER/capturebrief/actions/runs/39360914919)
at QA workflow head
`c36406f76d6d3389c517e73cb205a652bc554e73`
passed **567 actual Linux tests; 170 actual Windows tests with
one skip; Chromium and WebKit no-send integrated case tests**.
All seven exact candidate heads were merged only inside disposable
CI workspaces. Existing latest candidate guards for source transport,
private encrypted backup, compressed archival sizing, strict source
originals, invoice/buyer flow and payment reconciliation remained
compatible. **No main or gh-pages branch was modified.**

Actual independently verified whole-device encryption, encrypted
off-device original AND independent recovery key with proved remote
restore, human publisher FY2027 catalog/source-index signoff,
independent code/production approval and real customer + 14-day watch
are **STILL UNVERIFIED**. No charges, customers, published claims,
external emails or deployments were initiated by this QA.


## October 19 — source-original byte attestation and fiscal-year isolation QA

The **real PAAM-L044** source-integrity investigation reproduced
two serious false-completeness defects with entirely **FICTIONAL**
FY2026/FY2027 inputs:

1. **Missing retained original:** After building an apparently
   complete synthetic FY2026 source archive, changing a source's
   SQLite `local_path` to a missing file still left
   `index_status(..., fiscal_year=2026)["complete"] == True`.
2. **Future-year contamination:** After adding an UNAPPROVED
   FY2027 `OPERATOR_FILE` notice that shared a solicitation number
   and AAC with an approved FY2026 family, the historical FY2026
   receipt erroneously included that unapproved notice and returned
   `COMPLETE`.

PR #51 exact candidate head
`d1fadd4779a96df3ab78e6e8af4e2a843078a35b` now:

- Mandatory release-bearing source verification streams full retained
  original-file bytes against the SHA-256 and byte count stored in the
  source snapshot, accepts only an explicit private authorized
  `snapshot_root` (or index containing directory), and rejects source
  URLs, fiscal years, kinds, timestamps and filenames outside the
  approved slot contract. Missing or mismatched original bytes become
  `UNVERIFIED` and block `COMPLETE`, regardless of SQLite
  `APPROVED_FETCH` flags.
- Checks each required current SQLite snapshot's indexed action rows
  against its recorded ingest row count, contiguous positions and
  nonempty NoticeId values. Zero-row historical CSVs are valid, but
  a deleted indexed action invalidates `COMPLETE`.
- Restricts both action-family joins and emitted source evidence to the
  **exact approved required fiscal-year slots**. Future/unapproved
  FY2027 rows can exist in the operator's SQLite without appearing
  in a FY2026 receipt. A future/unapproved seed cannot manufacture
  a complete older-year family.

At exact head, [Product Core
#39362749702](https://github.com/P00NSMASHER/capturebrief/actions/runs/39362749702)
and [#39362754058](https://github.com/P00NSMASHER/capturebrief/actions/runs/39362754058)
passed **Linux and Windows** after a synthetic test initially held
an SQLite write lock while reading status; the *fixture* was corrected
without weakening production checks.

The [seven-head disposable QA composition
#39362798263](https://github.com/P00NSMASHER/capturebrief/actions/runs/39362798263)
at QA workflow commit
`fbcf2546b4b046a6eafba52abe2f011c2b8a26ec`
**PASSED 574 Linux tests, 177 Windows tests (one skipped),
Chromium + WebKit no-external-POST buyer-to-case-to-payment controls**.
All merges remained ephemeral and the real site/approved catalog
were unchanged.

A returned `local_original_hashes_verified` covers locally retained
bytes in **required slots only**, against locally stored fingerprints.
It is NOT human/source-publisher attestation, does not guarantee
immutable or independently checked SQLite row semantics against
publisher originals in adversarial storage, and does not replace the
required signed source evidence, encrypted off-device backup,
independently recoverable key, device encryption, independent reviewers,
approved full catalog or customer pilot. The full-byte check is
I/O-intensive (proportional to genuine retained catalog size);
do not quietly bypass it for performance without an independently
validated alternative.


## October 19 — eight-candidate exact original-to-index row fidelity validation

A newly reproducible source-coverage false-positive was demonstrated
with fictional inputs on PAAM-L044: an otherwise complete FY2026
catalog could report `complete=true` even after a retained source
original's SQLite `local_path` pointed to a nonexistent file.
A second issue allowed a current UNAPPROVED FY2027 source notice to
contaminate a `COMPLETE` FY2026 history-family receipt when
solicitation number and AAC matched. PR #51 now checks every required
retained original's SHA-256/size/private root/official source URL,
required SQLite row counts and identifier validity, and strictly
limits family evidence to the requested approved FY source slots.

An additional independent acceptance gap existed for a *mutated
SQLite projection with the same row count and correct complete original
file SHA*. New DRAFT operator-only **PR #62** provides a read-only,
on-demand row-by-row source-to-index audit. It recomputes every
original row digest and checks exact NoticeId, normalized Sol#,
AAC/agency/office/date/link values against one private source
snapshot, using only an approved explicit local source root.

On PAAM-L044 with the exact PR #62 head
`47b1341ab1419b392a661ce803f60f7f7c6193e3`:

- Eight synthetic adversarial source-to-row projection tests **PASSED**
  using local Python 3.13; GitHub Actions [#39363457248](https://github.com/P00NSMASHER/capturebrief/actions/runs/39363457248)
  independently **PASSED Linux and Windows**.
- The real previously verified FY2027 original
  (`1,607,260` bytes, SHA-256
  `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`)
  was indexed once as **UNAPPROVED OPERATOR_FILE** inside a disposable
  SQLite test folder. The on-demand auditor verified **all 1,104
  real notice-row projections** matched the actual original. A
  deliberate date-field mutation to ONLY that temporary SQLite
  record was then correctly rejected while the original full-file
  SHA remained identical. No notice details, bytes or customer
  records were uploaded or published. Disposable SQLite evidence was
  deleted, original+receipt SHA remained intact.
- PAAM's preexisting AES-256-GCM FY2027 local backup, independently
  reverified by SHA-256, remains a *local-only* DPAPI protected
  candidate. It is **not a remotely stored ciphertext with a
  separately recovered key**. PAAM had about **14.70 GiB** free at
  the last read-only original+backup check.

The new eight-head, **synthetic-only, NO DEPLOY** composition included
PR #51, #52, #53, #55, #54, #57, #61, and #62 as exact pinned
heads; the website candidate #50 remained separate. Actual
[GitHub Actions run #39363676788](https://github.com/P00NSMASHER/capturebrief/actions/runs/39363676788)
at QA source head
`5c520c0b2b56cde6dd5627cd70c064781044c287`
**PASSED**: **582 Linux tests, 185 Windows tests (1 skipped)**,
Chromium/WebKit integrated no-external-POST buyer and fictional
payment checks, and clean disposable eight-branch Git merges.
No production or protected branches were mutated.

All FY2027 release gates remain explicitly **NOT APPROVED**:
human-reviewed 34-year FY2027 source catalog and exact source
retention/index, independent source-publisher authenticity,
whole-device encryption, independently recoverable recovery-key
escrow with encrypted off-device backup and actual downloaded remote
restore, independent code approvers, real customer authorization,
verified delivery/paid transaction, and a genuine 14-day live watch.
The passing tests do not override these holds.


## October 19 — agency and office anchored-family false-completeness repair

On PAAM-L044, directly simulated **four** complete-but-ambiguous
history sources (FICTIONAL bytes only) from the genuine current
`history_index` release-candidate function:

- Identical normalized solicitation and AAC with distinct Offices
  were incorrectly grouped as one `COMPLETE` contract history.
- Identical solicitation+A​AC with one blank/unknown Office could
  improperly include both known/unknown office records.
- A seed with blank AAC and a known Office could join a differently
  coded agency merely because Office/Sol# were identical.
- A seed with neither AAC nor Office could include unrelated
  identifiable notices when one nonblank agency code was present.

PR #51 head
`cf15448c54cfd9245955819a22171680accb69f6`
now rejects completion whenever these anchors do not establish a
unique seed family: review-required errors are emitted, ambiguous
sibling notices are excluded, and the receipt is `OBSERVED_ONLY`
rather than `COMPLETE`. Five new invented-source negative-control
tests passed on Linux/Windows
([exact code #39365703690](https://github.com/P00NSMASHER/capturebrief/actions/runs/39365703690)).
The workstation independently replayed **four** variants at the exact
same PR source SHA using real Windows Python 3.13: **4/4 PASS**.

The real retained, still-unapproved FY2027 official original contains
1,104 rows, 119 repeated nonblank `Sol#` groups, nine blank AAC
rows and zero blank Offices. Its repeated groups do not exhibit
multiple nonblank Offices under the same AAC or mixed known/missing
AAC or Office conflicts as defined above. This is a **single-year
compatibility observation**, not independent publisher authentication
or 34-year complete-history acceptance.

Actual [eight-candidate no-deploy composition
#39365810058](https://github.com/P00NSMASHER/capturebrief/actions/runs/39365810058),
using exact QA workflow source commit
`f08ed6ac3b8c1a7fcdb7b93ae9ebd214fbfe89f4`,
passed **587 Linux tests, 190 Windows tests (one skipped)**,
Chromium+WebKit no-send negative-controls, and eight pinned
source-branch merges inside disposable CI workspaces.

**No protected main/gh-pages merge, FY2027 catalog review/approval,
customer communication, source bulk downloads, independent code
approval, verified host encryption, off-device recovery or
production deployment was performed.** A real customer case and
14-day monitored pilot are still missing. The engineering test
results must never be relabeled as independent approval.


## October 20 — additional source-slot and stable-original release-gate QA

**Scope: source-security engineering only; NOT customer-release approval.**

1. DRAFT PR #63, exact source head
   `3280cf9f3fc6abb9b1956004c98f010a6543cf95`, now applies the same
   official active/archive fiscal-year/URL binding to **both** the
   in-memory Data Services scanner and the disk-based SQLite importer.
   Six new fictional bad-label cases reject an ACTIVE source mislabeled
   as an archived year, archived URLs mislabeled as ACTIVE or another FY,
   and accidental coercion of boolean/string year parameters **before
   private retention or index mutation**. [Exact-head Product Core
   #39524307326](https://github.com/P00NSMASHER/capturebrief/actions/runs/39524307326)
   passed Linux and Windows.
2. DRAFT PR #62, exact source head
   `2e3ae7f5300d50842d30186f488752519b5a8f34`, adds a synthetic
   regression where an on-disk source original changes **between**
   its initial matching SHA-256 and the read-only SQLite projection
   comparison. Its operator-only audit now rehashes full source bytes
   after row comparison and refuses a PASS for the changed source.
   [Exact-head audit #39524744813](https://github.com/P00NSMASHER/capturebrief/actions/runs/39524744813)
   passed Linux and Windows. This costs one additional sequential source
   read and does NOT prove safety against a fully malicious host.
3. The ten-source-candidate, **NO DEPLOY** composition at QA workflow
   source `12d4ccc7bb0497108110a3137bcf52ebd3b8c607`
   [#39524768027](https://github.com/P00NSMASHER/capturebrief/actions/runs/39524768027)
   **PASSED**: **639 Linux tests, 242 Windows tests (one skipped)**,
   Chromium and WebKit fictional site-to-private-case/Stripe safety
   checks, and all ten exact branch merges in isolated CI workspaces.
   The public website PR #50 was checked out separately at its existing
   immutable candidate SHA, not published.
4. This document addendum does not advance the fixed FY2026 production
   archive catalog or claim authenticated 34-year FY2027 history.
   PAAM-L044 was **offline** during this source review. New code has
   not been replayed against the private FY2027 original on the host.
   Local original retention, local backup and preexisting receipt
   observations are historical, not remotely escrowed/restore-tested
   proof. The unrelated `pa-entity-discovery.yml` branch-push
   workflow remains invalid on unmerged branches until the separately
   green PR #54 is independently approved and integrated.

**Release decision: NO-GO.** Independent human source/catalog/code
review, immutable complete archive coverage + current ACTIVE file,
independently recoverable encrypted off-device backup and actual
remote restore, verified device encryption, payment/case/delivery
acceptance and real 14-day monitoring are still unproven. No main or
gh-pages merge, actual billing, private original upload, customer
communication, or production deployment is authorized by this receipt.


## October 21 — buyer-intake retry and blocked-clipboard fallback acceptance

**Product improvements, NO DEPLOY.** The staged pilot now fixes two tangible
buyer/operator pain points without changing payments, source authority,
release permission or customer notifications.

1. **Repeatable intake:** PR #52 candidate
   `4ac840dbbc50fea40e629ee48d12aaa2ff6f56d7` restores the original
   private case import timestamp on a byte-identical CLI retry, including
   interruption between case and receipt publication. A changed request
   and tampered prior artifacts are refused without overwriting. The
   initially reproduced red failure is [Product Core
   #39545698859](https://github.com/P00NSMASHER/capturebrief/actions/runs/39545698859).
   Fixed-head [Product Core #39546730510](https://github.com/P00NSMASHER/capturebrief/actions/runs/39546730510)
   passed Linux/Windows.
2. **Clipboard-independent buyer handoff:** PR #50 website candidate
   `2e35b30cceefa213d1b27b6159b6b8ae6834f1e7` displays a complete,
   selectable local email draft when both browser clipboard methods are
   blocked. A later input change clears that previously shown draft.
   All five fictional 500-character assumptions remain intact and are
   not sent or stored by the website. [Exact-head website quality
   #39546404758](https://github.com/P00NSMASHER/capturebrief/actions/runs/39546404758)
   passed Chromium/WebKit.
3. **Interoperability against actual separate candidate branches:** PR #52
   [cross-branch acceptance
   #39546727991](https://github.com/P00NSMASHER/capturebrief/actions/runs/39546727991)
   passed Chromium and WebKit, loading the exact immutable site head
   and the pinned fictional Stripe/payment review candidate. A
   clipboard-denied plain-text draft generated a backend case containing
   all five UNPROVEN assumptions, without external HTTP POST, sent email,
   charge, source attestation or fictitious payment authorization.

**Full ten-candidate composition, exact QA head
`7fa8eb6243f2a6b1ff88982ead15b233b428b304`:**
[GitHub Actions run
#39546802599](https://github.com/P00NSMASHER/capturebrief/actions/runs/39546802599)
**SUCCEEDED on Linux and Windows**, with **642 Linux tests** and
**245 Windows tests (one skipped)**. The actual pinned candidate heads
merged cleanly only inside disposable CI workspaces, and the
separately checked-out site candidate ran Chromium/WebKit fictional
buyer-to-private-case/Stripe acceptance.

**Not a production release.** No actual buyer emails, real payments,
private source uploads, customer data, independent approval, main/gh-pages
merges, FY2027 catalog approval, 34-year original collection, or
off-device recovery took place. The real website/customer system has
not been claimed updated from these unmerged candidates. Protected-main
and independent user/source-release gates remain separate from this
functional improvement.


## October 21 — concurrent buyer-import replay and Windows QA clarification

The Python importer previously assigned a fresh local `submitted_at`
timestamp on each attempt before publishing private case/receipt files.
Two simultaneous copies of the same buyer request could race into
different case identifiers even when targeting identical private paths.
The source and test suite reproduced the conflict in [negative-control
Product Core #39549345568](https://github.com/P00NSMASHER/capturebrief/actions/runs/39549345568)
using only fictional buyer data.

Current PR #52 candidate
`d445ee6fe21513b48ead4d956b15ff333ddb9013` wraps
both case and receipt paths in bounded, deterministically ordered,
private `.intake.lock` critical sections. A second simultaneous job
replays the *original* recorded UTC timestamp, validates the exact
case and receipt bytes, and never silently replaces the original.
Partial publication remains recoverable; a held lock safely blocks.

The initial Windows **test harness** compared its short temporary
file path to the separately normalized output path, missing its
artificial pause checkpoint (while Linux passed). The harness was
corrected to compare resolved paths; that does not weaken production
locking. The final targeted [Linux+Windows concurrency and interrupted
publication #39550263273](https://github.com/P00NSMASHER/capturebrief/actions/runs/39550263273)
**PASSED**. [Exact-head Product Core #39550265437](https://github.com/P00NSMASHER/capturebrief/actions/runs/39550265437)
also passed. PAAM-L044 ran **17/17** source-locked Windows Python
3.13 intake unit tests, confirming the final retry logic; its isolated
test checkout was removed and the retained real original/receipt SHA
remained identical.

At the revised QA source commit
`a8520a67eb3c050d34a47da102d2387c6abc7ca1`,
[full ten-candidate no-deploy composition #39550329639](https://github.com/P00NSMASHER/capturebrief/actions/runs/39550329639)
**PASSED 644 Linux tests and 247 Windows tests (one skipped)** plus
Chromium/WebKit no-send buyer-to-Python/fictional-Stripe integration.
All ten candidate Git merges took place only inside disposable CI
workspaces. The public website PR #50 was checked out separately
at its immutable `2e35b30c` head, not deployed. No actual customer
records, charges, email sends, source catalog promotion or main/gh-pages
merge were performed. This evidence does not independently approve
publisher authenticity, full FY2027 coverage, disaster recovery or
production release.


## October 21 — private saved-request batch intake acceptance

**Functional candidate only; no live buyer data or deployment.** Newly stacked
DRAFT PR #64 introduces an operator-invoked private batch loader for saved
CaptureBrief request-draft `.txt` files, based on the reviewed single-request
intake PR #52. It accepts at most 100 immediate draft files per invocation;
never polls an inbox, sends messages, bills Stripe, calls SAM.gov, or creates
a case containing approved evidence. Distinct **exact request-byte SHA-256**
values map to separate private case+receipt paths; same-byte copies are
safely deduplicated even if the source filenames differ. Previously created
matching case/receipt pairs are reused, and interrupted partners can be
restored with the original import timestamp.

A new optional expected-request SHA-256 boundary in the underlying importer
rejects a request that changes *between* batch fingerprinting and the
locked authoritative import read; no incorrect digest-named case is
published. Symlink input/output files and linked private directories are
rejected; oversized, malformed, tampered, or unsafe drafts fail independently
without aborting valid neighbors. The batch JSON reports only aggregate
counts, opaque hashed filename tags, and generic error classes, never buyer
contact details, paths or request text. Payment/source/client-release
approval remains **FALSE**. Semantically similar but byte-different drafts
are **not** deduplicated automatically and remain an operator concern.

**Checks at exact current PR #64 candidate head
`149bd034e56bcba75aeb8daff2d71f3dc302ebd0`:**
- Dedicated [Linux/Windows batch QA
  #39558736476](https://github.com/P00NSMASHER/capturebrief/actions/runs/39558736476),
  [Product Core #39558736632](https://github.com/P00NSMASHER/capturebrief/actions/runs/39558736632),
  and [private intake concurrency #39558736483](https://github.com/P00NSMASHER/capturebrief/actions/runs/39558736483)
  all **PASSED** using invented buyers and disposable directories.
- PAAM-L044 Windows Python 3.13 ran **25/25 previous-head combined
  batch/single-draft tests with one symlink test skipped** at exact
  `6c8d4327054b0987e60a754e731dfda642a563ee`; that isolated
  checkout was removed. The final `149bd034` head was installed
  locally into an explicitly pinned operator-only checkout, and a
  read-only empty-inbox smoke test returned exactly
  `BATCH_NO_REQUESTS`, creating **no** case artifacts.
- The local operator setup includes EMPTY private `private-inbox`
  and `private-cases` folders under CaptureBrief's local app data,
  plus a manual, pinned launch command. The new launcher has not been
  used to ingest real buyer records. No broad Users/Everyone/Guest
  allow ACLs were observed on the new private folders; this is not
  certification of whole-device encryption.
- Previous pinned eleven-candidate
  [no-deploy QA #39558146207](https://github.com/P00NSMASHER/capturebrief/actions/runs/39558146207)
  **PASSED 652 Linux tests and 255 Windows tests (one skipped)**,
  Chromium/WebKit buyer-to-Python/fictional-Stripe checks and all 11
  ephemeral pinned Git merges. That run used the previous PR #64
  documentation head `6c8d4327`. The updated current final head is
  pinned in this QA branch's revised workflow for a separate
  eleven-head acceptance; do not infer final acceptance from the prior
  run before its own exact-head CI completes.

**Release state: still NO-GO.** PR #64 remains stacked onto unmerged
PR #52. No main/gh-pages changes, private buyer requests, mail
delivery, live payment, complete FY2027 source catalog, off-device
recovery, independent release approval or actual customer fulfillment
are established by these synthetic developer tests.


## October 21 — private batch dry-run preview and operator handoff

**Product-only advancement, still NO DEPLOY.** Draft stacked PR #64 adds a
read-only operator preview mode to the previously accepted private saved
request batch importer. At exact PR #64 head
`137f0963cf83c2257f1245143e9938911626c572`,
`--preview` applies the same strict local buyer-draft syntax validation as
importing but **does not publish, repair, overwrite or delete** private
cases or receipts. It counts exact duplicate input bytes and labels
pre-existing saved output pairs `EXISTING_UNVERIFIED` and incomplete
pairs `PARTIAL_UNVERIFIED`. These labels DO NOT attest that the
previous case/receipt bytes are valid; the actual locked import is
still responsible for integrity checks. Invalid drafts report a
nonzero partial-preview status, and an empty inbox says
`BATCH_PREVIEW_NO_REQUESTS` rather than falsely saying a customer
was accepted.

**Verified exact source head:** [Linux/Windows private-batch QA
#39560683272](https://github.com/P00NSMASHER/capturebrief/actions/runs/39560683272),
[Product Core
#39560683558](https://github.com/P00NSMASHER/capturebrief/actions/runs/39560683558),
and [intake concurrency
#39560683494](https://github.com/P00NSMASHER/capturebrief/actions/runs/39560683494)
all **PASSED**, using fictional buyer data only.

**Integrated exact-code composition:** [NO-DEPLOY GitHub Actions
#39561057406](https://github.com/P00NSMASHER/capturebrief/actions/runs/39561057406)
at QA workflow source
`01334b146e07e9aa40a81c2d9ce2024a036eb7c8`
**PASSED 657 Linux tests, 260 Windows tests (one skipped)**, Chromium/WebKit
fictional buyer-to-private-case/Stripe safety checks, and all eleven
pinned candidate Git merges inside disposable CI workspaces. No public
branch, customer record, payment processor state, private source
storage or live site was mutated.

**Real authorized Windows device replay:** The online PAAM-L044
checkout was updated to the same pinned PR #64 code SHA, and
**30 Python 3.13 batch/intake tests ran successfully (one Windows
symlink-permission skip)**. An empty real private inbox preview
returned `BATCH_PREVIEW_NO_REQUESTS` and produced zero files. A
separate isolated, entirely fictional three-draft CLI exercise
(duplicate + malformed + one valid draft) verified the preview
created **no case files**, that explicitly running the importer
created exactly one fictional case/receipt, and that another preview
classified the existing pair `EXISTING_UNVERIFIED`.
The separate disposable test directory was destroyed. Pinned
`Preview-CaptureBrief-Private-Batch.cmd` and
`Start-CaptureBrief-Private-Batch.cmd` remain in local app data,
with both real private inbox/output folders still empty.

**Not accepted by these tests:** actual buyer identity/email delivery,
live $149 Stripe payment, official FY2027 full source catalog and
genuine source authority, independent code/production review,
off-device encrypted disaster recovery with an independently retrieved
key, and a real 14-day customer watch. No main/gh-pages merge,
external send, payment, or customer release occurred.


## October 21 — read-only operator review of imported private cases

**Feature candidate is functional, still NO DEPLOY.** Stacked PR #64 at
immutable exact head `dbf4bc9a12f67bbce56b1da3bc14468038fea8d2`
adds `scripts/review_private_cases.py` after the already-validated
private Preview and Import stages. Its read-only review loads paired
private case/receipt JSON files, requires consistent canonical case
and receipt hashes, source request SHA and UTC timestamp, checks
unverified buyer identity/payment/communication/source states, then
uses CaptureBrief's **real** `build_fulfillment_plan` to summarize
task counts and the next generic effort stage. Raw customer contact,
assumptions, opportunity URLs, case IDs and private filesystem paths
are **not** emitted in the output.

The reviewer refuses missing partner files, altered receipts, unapproved
state claims and active importer locks. Two independently valid requests
with matching supplied work email and exact opportunity URL are
reported as **possibly related** even if the assumption copy differs.
These are *unverified local duplicate clues*, not authenticated buyer
identities or automatic merges/deletions.

**CI:** [Final isolated eleven-head no-deploy composition
#39577299827](https://github.com/P00NSMASHER/capturebrief/actions/runs/39577299827)
at exact QA workflow SHA `c276b4dc02eef4a58bdb3275ecc3caae3afe0ba6`
**PASSED 663 Linux tests and 266 Windows tests (one Windows symlink
privilege skip)**, Chromium/WebKit fictional buyer-to-strict-core/
fictional-Stripe checks, plus all eleven pinned ephemeral Git merges.
Standalone [private batch
#39577254208](https://github.com/P00NSMASHER/capturebrief/actions/runs/39577254208),
[Product Core
#39577254258](https://github.com/P00NSMASHER/capturebrief/actions/runs/39577254258),
and [intake concurrency
#39577254315](https://github.com/P00NSMASHER/capturebrief/actions/runs/39577254315)
also passed at the same exact PR #64 code head.

**Real Windows host:** PAAM-L044 checkout was updated to the same PR #64
SHA. **36 direct Python 3.13 private review, batch, and intake tests
passed with one symlink creation privilege skip**. Its authorized
private case folder remains empty; a read-only live-dir check
returned `PRIVATE_CASE_REVIEW_EMPTY` with no case writes.
Three private manually initiated pinned launchers are installed:
`Preview-CaptureBrief-Private-Batch.cmd`,
`Start-CaptureBrief-Private-Batch.cmd`, and
`Review-CaptureBrief-Private-Cases.cmd`. A *separate disposable
fictional* Windows CLI exercise verified preview-new/duplicate/blocked
counts, two explicitly created fictional cases, one related-case
warning, and rejection of a manually altered fictional receipt. Its
temporary folder was destroyed. Both actual private inbox and cases
directories are still empty. The real retained FY2027 original/source
hash was never used by this case-queue feature.

**Release/certification still blocked:** These results do not establish
independent customer identity, authenticated Stripe live payment,
independent source or FY2027 34-year catalog coverage, publisher
review, real 14-day customer watch, disk encryption or independent
off-device disaster recovery. No customer record was sent or stored
on GitHub, no live website, pricing, payment, buyer communication
or production main/gh-pages branch was changed.
