# CaptureBrief — first paid pilot release gates (18 October 2026)

**Verdict: HOLD — not independently validated for a paid customer.**
Authoritative website: https://p00nsmasher.github.io/capturebrief/ on the gh-pages branch. Product core: main branch. Legacy Netlify is not the current website.

## 1. Real first-party pursuit and delivery

- [x] Inspect a genuine first-party SAM.gov opportunity with publicly visible version changes.
- [x] Exercise intake and core refusal on a real public URL paired with fictional buyer claims. No invented source receipts or automatically supported assertions.
- [x] Select an actual current federal enterprise-IT services pursuit for public-source rehearsal; still obtain approved SAM API v2 observation, retained controlling files, version closure, exact quotes, and human-reviewed rule applicability before any customer-delivery claim.
- [ ] Produce a complete non-synthetic Decision Evidence package and actual delivery ZIP, verify it using the original independent receipt and inspect each buyer-facing finding.

**Real public IT-sector metadata rehearsal, not a customer:** The Army's active MAPS multi-domain services solicitation W15P7T-26-R-A006, https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view, is a federal enterprise-IT/engineering-services procurement. Official public notice metadata updated October 16, 2026 advertises a November 12, 2026, 11:59 a.m. Eastern offer deadline, replacing the original May 1 deadline; Amendment 0011 and multiple public attachments are listed. Our fictional buyer assumption uses the old May 1 due date as a negative-control input. Source metadata alone is NOT a verified current API observation, full reference closure, approved historical evidence, expert review or customer delivery; the case must stay UNPROVEN and release-blocked.

**Additional version-control example:** GSA construction notice 47PH5226R0003 at https://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view contains Amendment 007 extending its deadline to November 4, 2026, but is not suitable as the IT-sector pilot sample.

## 2. FY2027 SAM archive catalog

- [x] An October 18 read-only inspection of SAM.gov's live first-party Archived Data page visibly found FY2027_archived_opportunities.csv marked Public. FY2026, FY2029 and FY2030 also appeared; FY2028 was not established by that inspection. Official source: https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public .
- [ ] Preserve a distinct **human-reviewed** October FY2027 catalog observation, exact observed year inventory, source identity, observation timestamp, version/hash and independent approval before updating the canonical approved catalog. A browser agent's observation is not a human signoff.
- [x] Independently compute a streaming SHA-256 of the entire public FY2027
  official-listing S3 file in one bounded, no-secret GitHub Actions run
  [#39205786451](https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451):
  1,607,260 bytes, 1,104 CSV rows, SHA-256
  `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`.
  The file was read in ephemeral CI and **not durably retained**.
- [ ] Fetch and privately retain genuine approved first-party active and ALL
  relevant archive extract bytes, update index receipts and confirm source
  freshness, including FY2027, before any FY2027 FULL_CATALOG claim.
- [x] Retain the existing FY2027 fail-closed production logic until both independent catalog review and required fresh source receipts are complete. Do not silently backdate live checks to FY2026 or invent a FY2028 record.
- [x] Add private read-only coverage auditing to the pilot preflight. The audit examines the existing SQLite source index, validates required source-slot identities and checked timestamps, detects missing/stale/unverified entries or missing files, and can optionally stream-check recorded extract SHA-256 hashes. It does not initialize/migrate the index, download sources or prove publisher origin. No private paths or contents are returned in the report.
- [ ] Perform the audit against the actual operator-held, current-FY SAM extract index. There is no FY2027-recertified index or genuine publisher-byte evidence available in this public repository.

## 3. Checkout and intake

- [x] The current public website/legal pages are reachable. The CaptureBrief live Stripe payment link was independently read as active for a one-time $149 charge.
- [x] The browser request-builder is local only: it copies a draft or asks the buyer's email client to open a message. It does not submit data to a CaptureBrief backend.
- [x] Proposed gh-pages PR #50 corrects a trust issue: buyer-selectable PAID and a forgeable ?checkout=complete redirect are **not** processor payment evidence. It labels the resulting email claim unverified.
- [x] Search the connected Gmail inbox for exact CaptureBrief scope/paid-intake subjects: no actual matching inquiry was found in the checked mailbox. This is a visibility check, not proof the website sent a message.
- [ ] Verify exact published email-draft behaviour and actual inbox receipt under an individually approved test send. A copied or opened draft does not establish delivery.
- [x] Read CaptureBrief's connected live Stripe account: no completed Checkout Sessions or PaymentIntents were present in the queried account. Test-mode Checkout Session `cs_test_a17hxV7xfKNdJ0oXBSuzDxdqOCZT9FMrUX57ISBoKggE1bgNnAWu1a5qBg` was created unpaid for $149; this is not a completed payment or refund test.
- [ ] For an actual order, reconcile the specific Stripe payment ID and order's payment/refund status. Complete a sandbox test payment/refund using authorized Stripe test methods; the prior automated test-card attempt was blocked, so it must not be marked passed.

## 4. Fourteen-day targeted watch

- [x] Existing core watch logic retains hash-bound baseline, 14-day expiry, change/reopen events, human review and no automatic decision changes. Pilot branch adds per-source freshness and fingerprint change controls so a single refreshed source cannot mask others left stale.
- [ ] For a released genuine source case, create the initial baseline at delivery and perform **actual scheduled fresh approved source observations** across the full 14-day interval; retain per-check proof and an operator exception queue.
- [x] Add tests for partial freshness, altered source fingerprints and future-dated source observations. Add `scripts/run_watch_receipt.py` to write content-addressed immutable local operator receipts **outside the public repository**, without messages or scheduling.
- [ ] Independently exercise a complete actual 14-day live watch on a real released case, including source failures and change alerts. Every outbound notification still requires message-specific approval.

## 5. Fulfillment and security

- [x] Core delivery rules require audit approval, complete non-synthetic Decision Evidence and ZIP-byte verification.
- [ ] Validate the actual final ZIP against a separately retained original receipt (command: python -m capturebrief_core.trace_cli verify-bundle delivery.zip --expected-sha256 ORIGINAL_SHA).
- [ ] Record written acceptance of one public pursuit, scope, turnaround, exclusions, refund/correction process and safe record retention. Keep credentials, case content, raw buyer emails and private files outside public GitHub.
- [ ] Review any procurement or eligibility judgment with exact source/version evidence. Explicitly approve each outgoing reply, change notice and delivery.

## 6. Independent acceptance and rollout

- [x] Main Product Core at 12d90024f053a78ead7936abf092931fce240d3e passed (https://github.com/P00NSMASHER/capturebrief/actions/runs/39077316900).
- [x] PR #50 buyer-intake patch passed GitHub Pages Chromium/WebKit Website Quality CI. Product Core regression suites passed on the pilot branch, including new per-source watch safety tests; recheck final head and acceptance logs after any subsequent patch.
- [ ] Obtain independent release review; reconcile open material faults, approve releases through existing controls, deploy the correct gh-pages branch and verify live published bytes.
- [ ] Complete one real supervised IT-sector customer workflow from confirmed paid order and reviewed source package through verified delivery and monitored follow-up, recording feedback/corrections.

## Read-only technical preflight (does not certify commercial launch)

Two separate stages prevent the circular requirement that the first
customer's entire watch must finish before the first customer is admitted.

**Before the first supervised pilot** (catalog and operational admission checks):

    python scripts/pilot_preflight.py --stage admission \
      --history-index /private/capturebrief/history.sqlite \
      --verify-source-bytes --as-of 2026-10-18T12:00:00Z

If original, retained CSV files are intentionally located in a different
private directory, supply:

    --source-snapshot-root /private/capturebrief/approved-extracts

The audit will not follow an index's arbitrary local_path pointer outside
the approved root; it treats such a record as a missing/unverified source.
Paths under the public repository and symlinked index paths are rejected.

Without --history-index, or with --verify-source-bytes omitted, the current
preflight explicitly blocks source-index readiness. The audit reads an
EXISTING private SQLite database in read-only mode and does not create,
repair or migrate missing files. Full hashing can require substantial disk
I/O for 31+ archive slots. Metadata flags marked APPROVED_FETCH and
locally matching SHA-256 files are **not independent proof of publisher
authenticity**; reviewer approval and source collection provenance remain
separate requirements. The audit reports only slot IDs and counts, not
customer data or filesystem paths.

At admission, real customer case, delivery ZIP and completed 14-day watch
are explicitly **POST_ADMISSION**; they are neither fabricated nor
prematurely demanded. The current FY2027 catalog still blocks admission
independently. Payment/inbox, reviewed release and operator approval remain
external, unverified gates. Admission never returns customer authorization.

**After real customer delivery and watch** (full evidence acceptance):

    python scripts/pilot_preflight.py --stage completion --case case.json \
      --bundle delivery.zip --receipt original-receipt.json \
      --baseline delivered-watch-baseline.json --observed-case fresh-case.json

Completion retains the independent original ZIP digest, audit and
non-synthetic Decision Evidence, genuinely refreshed watch observation,
and explicit human approvals. Both stages are local-only diagnostics: no
network request, email, charge, publication, automatic approval or
customer data export. Never interpret a CLI status as permission to send.

PR #49 concerns a separate older public ZIP packaging lane, not the active GitHub Pages publication. The unrelated PA x402 discovery workflow startup error should not be used as evidence that CaptureBrief's Product Core failed.

**No actual new customer, charge, sent message, downloaded archive, 14-day completed watch or buyer delivery is claimed in this record.**
