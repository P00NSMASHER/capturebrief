# CaptureBrief accepted-case source, custody and human-release gate

**Scope:** one REAL received, identity-checked and accepted case, not a local email-draft inquiry. The read-only release verifier is python scripts/check_accepted_case_release.py; it performs no source fetch, email, payment, browser action, data upload or customer contact.

## 1. Complete the official family, not only the latest-active API response

The [GSA Get Opportunities Public API v2](https://open.gsa.gov/api/get-opportunities-public-api/) explicitly provides **only the latest active version**. Its resourceLinks are not deletion-aware historical attachment evidence, nor a statement that amendments do not exist.

For **each accepted pursuit**, independently collect in approved private storage:

1. Exact buyer notice ID, solicitation number and first-party current API receipt (current action only).
2. A separate official SAM.gov complete-family action/version list, including amendments, modifications, cancellations, reinstatements and prior versions. Use the documented SAM.gov Data Services active/archived source inventory and human-supervised first-party SAM views when needed. The management history endpoint may be restricted; do not scrape, hallucinate or infer inaccessible data. Preserve an original history observation, timestamp, URL, SHA-256, source method, affected-action IDs, and all prior versions. When unknown, **HOLD**.
3. A source-linked action/original inventory with every action ID and original. Match the exact set to the case packet history_action_ids. Explicitly identify each amendment number and publication time, including negative checks for absent/withdrawn changes. A current API reply alone is forbidden as the HISTORY original.
4. A **deletion-inclusive** attachment/manifest observation for the entire family. Preserve each current, superseded or deleted source object, including original contents. A deleted/unavailable original needed for a material conclusion stays **HOLD** rather than being silently omitted.
5. Incorporation/rule review: each FAR, DFARS, agency supplement, deviation and cited/attached reference affecting the assumption. Preserve official original bytes, exact **edition incorporated for this pursuit**, cited clause/section locator, incorporation language, applicability, and unresolved conflicts. A newer web rule is not automatically the incorporated edition.
6. A real identifiable source reviewer examines retained originals, unresolved limitations, completeness and conclusions. They attest to the final case evidence with an independently approved source-review key. A file digest and a self-reported reviewer name are not enough.

The accepted-case manifest requires source_closure.scope = HUMAN_REVIEWED_COMPLETE_ACTION_SET, first-party history_file and resource_inventory_file, every actions[].original_file, resources[].original_file and exact incorporated_sources[] rule editions. Recognizable official SAM.gov notice pages must name **the same exact action ID**, and official SAM resource download paths must name **the same exact resource ID**. Distinct historical actions and attachment IDs cannot reuse the same retained original file ID. For a first-party **Data Services collection URL**, supply a separately reviewed `record_locator` exactly matching the action or resource ID; the human review must verify that row inside the real retained extract. This does not automatically certify Data Services completeness. Missing history, inaccessible originals, source/version mismatch, unreviewed references or incomplete core audit **fail closed**. A local SHA-256 does not itself independently authenticate a downloaded document to GSA.

## 2. Approve a REAL private customer environment

Customer records are **not** authorized for public GitHub, GitHub Pages, Actions artifacts/logs, consumer browser storage, or an unapproved shared folder. Existing scripts/scoped_private_backup.py backs up a single scoped intake and recognized source files: it does **not** back up the final report, ten-business registry, approval roster or all customer records. Its public/fictional clean-runner demo is not production recovery.

Owner/custodian tasks, with no new paid service unless separately approved:

- Provision restricted encrypted primary storage and a separate encrypted off-device backup destination. Explicitly approve provider, jurisdiction, retention/deletion policy, roles, audit trail and restore process. Cloudflare R2 is optional and is **not** assumed active or approved.
- Hold the **production recovery key independently** with a custodian, not solely on the primary device or in the backup, repository, CI or chat. Keep release signer public keys in an owner-controlled trust roster **outside the customer case root**; private signing keys must never go into GitHub, reports, email or chat.
- Back up the **entire** encrypted evidence inventory, not just a scoped source: intake, official history and original documents, resource ledger, business identity proof, signed scope, complete report and receipt, trial/engagement registry snapshot, audit/review records and proposed delivery body. Retain an actual off-device provider retrieval receipt.
- On a **different approved device**, independently download the remote encrypted original, restore using the independently held key to a new empty private location, verify every file SHA-256 against the original inventory, and sign the actual receiving-device and restoration evidence. No synthetic key or CI artifact can be accepted as production proof.

The separate receipt uses schema capturebrief-independent-restoration-v1 and contains offdevice_backup_sha256, distinct primary_device_id and restore_device_id, key_custodian_id, restoration_method = NEW_DEVICE_RETRIEVAL_AND_DECRYPTION, restored_and_verified = true, timezone-aware restored_at, and restored_files mapping **every private file ID to SHA-256** except the encrypted backup and recovery receipt. The verifier checks that inventory and independent signatures. It cannot reach into the separate device to prove the event happened; the custodian remains responsible for the signed statement.

## 3. Actual business identity, completed report and ONE delivery

Every accepted case needs an independently received inbound request, identity checked against an independent organizational source, control over the contact channel, and an exact accepted scope. A reserved no-card cohort slot is **not** business verification.

Complete the Decision Evidence report privately, retain exact report bytes and a separately preserved report receipt, and have a real human examine **the entire completed report**, exact citations, caveats and material conflicts. Unresolved material source conclusions block release.

Before **each proposed external message**, obtain explicit review of the exact verified recipient, subject, message body bytes and report attachment digest, plus a fresh unique 128-bit or greater authorization nonce, max_sends=1, and expiry no later than 24 hours away. Six independently trusted roles must sign the exact same immutable manifest:

- SOURCE_REVIEWER
- STORAGE_OWNER
- RECOVERY_CUSTODIAN
- BUSINESS_VERIFIER
- REPORT_REVIEWER
- DELIVERY_APPROVER

All roles require **distinct approved Ed25519 signer keys**. Sign exactly the bytes produced by capturebrief_core.accepted_case_release.signature_payload(unsigned_manifest, role, key_id, signed_at). Each signature record contains role, key_id, timezone-aware signed_at and signature_base64. The externally provisioned trust roster has schema capturebrief-private-release-signers-v1 with signers containing role, key_id and public_key_base64. The roster must be created through a separate owner-controlled administrative process, not from customer intake. No private keys are generated by this code. Every change to a signed report, original, recipient, body, or nonce invalidates the approvals.

The approved root must be owner-only and outside Git; the signer roster must be in a separate approved owner-only location. The private case root, individual case/manifest files, and trusted signer roster **must not traverse any symbolic-link or Windows-junction ancestor**, even if the last file itself is a normal 0600 file. The verifier rejects such path aliases before reading private JSON, preventing a shortcut into a public or unrelated workspace. On Python 3.11 Windows workers, NTFS junctions and other reparse points are detected with `os.lstat()` reparse attributes because `Path.is_junction()` is available only in Python 3.12 or newer. Native Windows junction tests are part of scoped-source acceptance. Test the read-only gate with:

~~~sh
python -m pip install --only-binary=:all: cryptography==46.0.4
python scripts/check_accepted_case_release.py \
  --private-root /approved/private/CaptureBrief/case-123 \
  --case /approved/private/CaptureBrief/case-123/case.json \
  --release-manifest /approved/private/CaptureBrief/case-123/release.json \
  --trusted-signers /approved/trust/CaptureBrief/signers.json
~~~

After all independently reviewed evidence and signatures exist, the operator must reserve **one** approved message nonce immediately before the manual handoff, using a **single durable append-only ledger shared across every accepted case**. Never create a new ledger per recipient or reset it after a restore. **First initialize this one canonical ledger once, before customers, in the approved private location** (see COMPLETE-CASE-RECOVERY.md):

~~~sh
python scripts/snapshot_authorization_ledger.py init \\
  --ledger /approved/private/CaptureBrief/approved-message-nonces.sqlite
~~~

The reservation tool now **requires that exact operator-preprovisioned existing SQLite schema**. It refuses a missing/deleted ledger or an empty SQLite file rather than creating a new nonce history. If the original disappears, stop and independently restore/reconcile every later authorization; do **not** initialize a replacement and call it the same ledger. This protection does not authenticate the operator's choice of ledger path: the custodian still must consistently supply the unique approved path, retain its durable identity, and verify backups across all cases. Only then reserve a message nonce:

~~~sh
python scripts/check_accepted_case_release.py \
  --private-root /approved/private/CaptureBrief/case-123 \
  --case /approved/private/CaptureBrief/case-123/case.json \
  --release-manifest /approved/private/CaptureBrief/case-123/release.json \
  --trusted-signers /approved/trust/CaptureBrief/signers.json \
  --reserve-once \
  --authorization-ledger /approved/private/CaptureBrief/approved-message-nonces.sqlite
~~~

The command **rechecks the entire retained case, source originals, trusted signer roster, signatures, core readiness and expiry inside the nonce-reservation transaction path**. It no longer accepts a caller-supplied `verification` status as authorization. It rejects ledgers with unexpected schema, added triggers or tables, damaged reservations and future-dated entries. The command atomically records only the recipient digest, exact signed-manifest digest and nonce digest, never sends a message or claims recipient delivery. Concurrent or later reuse of the **same** nonce/manifest within this shared ledger fails closed. The receipt state is MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE. Preserve and independently back up this ledger, and reconcile its state after any restoration; a restored stale snapshot must not resurrect an already used authorization.

Exit **2** = CUSTOMER_DELIVERY_BLOCKED; nothing sent. Exit **0** = exact case, originals, roster signatures, core source/Decision Evidence and one-message approval verified, **manual send only**. It does **not** claim customer receipt, prevent a human outside the software from reusing an approval, independently authenticate signer identity, or prove a remote event happened except through signed custodian evidence. Owner must verify the real transport receipt and record it separately. Every later delivery needs a new explicit approval and nonce. Never enable checkout or automatic messaging from this read-only result.

## What cannot be completed simply by merging code

**Having no customer is not a pre-first-customer launch blocker**, and neither customer feedback nor review of a completed customer report can be demanded before a first engagement. Still missing for operational delivery preparation: custodian-held production key, owner-approved primary/remote private storage, genuine independent restore of non-sensitive rehearsal data, and verifiable full-action source-history workflow. After a specific request arrives, that case will require authenticated business identity/scope, independently reviewed first-party originals, internally reviewed report and explicit owner-approved message. These individual customer obligations must not be misclassified as prelaunch defects. **Do not fabricate reviewer approvals, reuse demo keys, fake a controlled mailbox, or turn paid release on to make a test green.**

The FY2027 full-catalog archive remains unapproved. A separately reviewed, complete **case-specific** SAM_HISTORY path can potentially close one case without approving the entire multi-decade catalog, but **never** from only the latest active API.
