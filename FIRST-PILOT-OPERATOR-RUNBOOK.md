# CaptureBrief first-pilot operator runbook | founder-curated, no-card

**Operating contract (2026-10-29):** one free assumption, one public federal
IT/cyber/cloud pursuit, at most ten independently verified businesses.
The inquiry has **no card**, no charge, no subscription, no automatic upgrade,
no included 14-day change watch and no automatic delivery. The original paid
pilot and its payment/watch process are separate; do not invoke them here.

**Truth boundary:** no customer is required for prelaunch. A prospective
customer's feedback, reviewed customer report, payment or signoff is not a
prelaunch gate. A software passing on fictional/public-only examples does not
prove private storage acceptance, real off-device recovery, human review or
permission to publish a first report.

## 1. Prelaunch drill, before a first customer exists

1. Independently open the production **Cloudflare Pages** deployment for
   `retally-capturebrief`, mapped to `capturebrief.retallyrecovery.com`, on
   the `gh-pages` production branch. Record the actual deployment ID, commit
   and response/body evidence, not merely the presence of a green GitHub check.
   Rehearse the browser form with *fictional, non-sent* values. Confirm it
   constructs a locally controlled draft only, never posts to a submission
   backend, initiates checkout, sends mail or falsely claims delivery.
   A **draft is not a submitted request**. Verify the live page's correct
   free-offer copy, one-assumption limit, public-only consent and no-card terms.
2. Run the no-customer readiness gate **with the selected offer and mode**:

   ```sh
   python scripts/pilot_preflight.py --stage admission --offer free --launch-mode founder_curated
   ```

   The result is **FOUNDER_CURATED_INQUIRY_REVIEW_REQUIRED**, not permission to
   admit a business, charge, contact anyone or deliver a report. The FY2027
   full-catalog diagnostics must not be misread as case-specific approval.
   Independently run `python scripts/audit_founder_pilot_runbook.py` and the
   cross-platform `tests.test_founder_pilot_runbook` regression gate.
3. In an owner-approved encrypted operator workspace outside Git/Pages/CI,
   rehearse a *fictional* request import, read-only source review, one-off
   report preparation, a deliberately conflicting public-source HOLD, denial
   and no-send controls. Do not create a real customer, populate the actual
   ten-business registry, impersonate a reviewer or invent evidence. Test
   rollback without resetting any existing reservation or message nonce.
4. Demonstrate an actual full-case encrypted backup of fictional/public-only
   evidence, including report, original sources, registry and authorization
   ledger **consistent SQLite snapshots**. Perform a provider-retrieved
   restore on a **second authorized device** using a **separately held recovery key**.
   Independently reconcile source/report/SHA inventories with a saved original
   baseline and check that an older ledger snapshot cannot authorize a
   duplicate message. CI runner-to-runner copies are engineering checks only,
   **not proof of an operator-owned private-cloud restore**.
5. Obtain independent operator review of the rehearsal procedure and test
   evidence. Record actual primary-device and receiving-device identities,
   source SHA receipts, time, private access/retention approval, separate
   recovery custodian, and the exact deployed website revision. Keep private
   files, access details, customer identifiers and secrets out of public PRs
   and automation logs. Mark unperformed steps BLOCKED, never PASSED.

## 2. The existing private GitHub provider, strictly isolated

The selected cloud provider is GitHub private repositories, reused from
PermitPlate **as a provider only**. Provision a *separately private*,
initialized `P00NSMASHER/capturebrief-state` repository and a new fine-grained
`CAPTUREBRIEF_STATE_TOKEN` restricted to its Contents read/write. **Never upload
to `P00NSMASHER/permitplate-state`**, and never reuse
`PERMITPLATE_STATE_TOKEN`. Put the token in the approved operator secret store,
not source, issue, Actions secrets by default, chat or a CLI argument. Keep
AES-GCM recovery material outside both repositories and off the primary host.

An inaccessible/missing destination, unapproved retention/access plan, absent
scoped token, missing separate custodian or missing real second-device proof
means **prelaunch private recovery remains BLOCKED**. Do not turn a mock
preflight or GitHub readback into a successful independent recovery claim.

For the separate public/fictional rehearsal, after owner provisioning, run:

```sh
# Private operator host only; no actual customer evidence.
python scripts/github_private_custody.py preflight
python scripts/full_case_backup.py create --private-root /approved/private/fictional-case --inventory /approved/private/fictional-case/backup-inventory.json --backup-file /approved/staging/fictional.cbak
python scripts/full_case_backup.py verify --backup-file /approved/staging/fictional.cbak
python scripts/github_private_custody.py upload --encrypted-case /approved/staging/fictional.cbak --approve-upload

# Second authorized device, independent download and original-inventory replay:
python scripts/github_private_custody.py retrieve --sha256 EXACT_CIPHERTEXT_SHA256 --output /approved/recovered/fictional.cbak
python scripts/full_case_backup.py restore --backup-file /approved/recovered/fictional.cbak --output-dir /approved/recovered/new-empty-case
```

The transport supports **at most 900,000 encrypted bytes per complete archive**,
and blocks oversized/private-repo usage rather than dropping evidence or silently
incurring charges. Never paste a token or recovery phrase into a command log.
Do not substitute PermitPlate's private repository, public code, Actions artifacts
or a public Cloudflare bucket for this isolated encrypted destination. Follow
`CAPTUREBRIEF-PRIVATE-GITHUB-RECOVERY.md` and `COMPLETE-CASE-RECOVERY.md`
for the complete signed and separately held proof inventory.

## 3. Later, upon a genuine first inbound request (not prelaunch)

1. Verify *actual receipt* in the controlled inbox. A browser, URL parameter,
   clipboard or locally prepared email draft is **not** independent delivery
   evidence. Check the real sending channel, consent, legal business identity,
   request scope, canonical business key and that no alias of the same company
   previously consumed a reservation. Never assume customer-supplied identity
   or an email address is independent verification.
2. The pilot is exactly **one free assumption** about one public opportunity
   and **at most ten** business reservations. Only after independent
   verification, retain a SHA of the privately held identity review and use
   `scripts/register_free_check.py` against one durable private
   `free-checks.sqlite`. Reservations are irreversible, alias-aware and
   concurrent-safe; no simulated customer may be added to the live registry.
   Preserve a WAL-consistent encrypted snapshot after each real reservation.
3. The SAM.gov Opportunities API v2 is **latest-active only** and cannot prove
   complete history. For *this exact pursuit*, obtain fresh current-action
   evidence plus the **complete official action and amendment history**,
   including preceding/withdrawn actions, original solicitation, all versions,
   deletion-inclusive attachments, incorporated FAR/DFARS/agency rule editions,
   reviews and exact citations. Bind buyer notice, solicitation, current
   action and every supporting original to one independently reviewed family.
   Unknown or conflicting dates, missing documents, incomplete amendments or
   unreviewed incorporation remain **HOLD**. Never fill holes with a
   fictional action, a generic source probe, partial latest-active API data or
   an invented human review.
4. Prepare the reviewed result privately and check the genuine
   `inspect_free_check` gates, `evaluate_delivery_readiness`, full Decision
   Evidence and exact report bytes/receipt. Use the original immutable
   reservation/scope and `scripts/build_free_check.py` only after evidence
   is independently complete. A rendered report or local SHA match alone
   cannot establish source truth, recipient authorization or delivery.
5. Include complete-case originals, business/scope evidence, source history,
   private registry snapshot, shared one-use authorization-ledger snapshot,
   report and message body in approved private custody. Make an updated
   encrypted off-device backup and preserve a separately verified restore
   record; reconcile snapshots before any further authorization.

## 4. Human release is **one exact message**, never automatic

The accepted-case release gate is distinct from inquiry preparation. Before
**each** external delivery the original source reviewer, storage owner,
recovery custodian, business verifier, report reviewer and delivery approver
must be **six distinct Ed25519** authorized signing keys, with exact recipient,
subject, body, attachment digest, immutable case/source bytes, expiry and
single-use nonce bound to the same manifest. Use the owner-controlled trust
roster outside the case root and the durable **shared** nonce ledger.
Check `ACCEPTED-CASE-RELEASE-GATES.md` and run the read-only verifier before
any reservation. Reserve with `--reserve-once --authorization-ledger` only
after all real signatures and evidence are independently established.

The gate writes no email; **no external message is sent** by the verifier,
registry, backup scripts, preflight or report builder. Its status
`MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE` is not a delivery receipt. A real
owner must review the precise outgoing message and manually authorize each
transport. Preserve provider evidence separately and never send from a
passing test fixture. Missing one signature, stale recovery, incomplete source
family, wrong body/recipient or used nonce remains DENIED.

## 5. Acceptance evidence and exit criteria

The operator must preserve: a verified production Cloudflare deployment/response,
no-submit browser test, no-card ten-business/adversarial regression results,
official public-source HOLD demonstrations, functioning protected private
workspace, independently held key, actual isolated private-state ciphertext
upload/readback, genuinely independent second-device full inventory restore,
reconciled immutable registries, exact signed-message denial tests, and
independent internal runbook assessment. Verify exact-head Linux and Windows
checks and separately review the PR before any release.

Even after technical prelaunch passes, the first real request still needs
its own business/consent checks, entire official source family, completed
internally reviewed report and a new per-message approval. A prelaunch PASS
must never be represented as real customer delivery, payment, or full
government-catalog coverage.
