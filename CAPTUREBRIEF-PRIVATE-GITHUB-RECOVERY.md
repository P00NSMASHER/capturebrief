# CaptureBrief encrypted backup on PermitPlate's existing private GitHub cloud

**Decision (October 29, 2026):** Reuse PermitPlate's established **private GitHub repository** storage model, with **no new paid storage service** and no customer-contact automation. PermitPlate's actual operational repository is `P00NSMASHER/permitplate-state` and is private. CaptureBrief must **not** store its own customer files, keys, ciphertext or trial registry inside PermitPlate's repository.

Use a **separate dedicated private GitHub repository** under the same existing account: `P00NSMASHER/capturebrief-state`. This repository was **not provisioned at the inspection**. The code refuses to upload until the destination is both present and verified private, with canonical `main`, no fork or archived/disabled state, and a dedicated write token.

## Owner-only setup, no new service or paid membership

1. Create `P00NSMASHER/capturebrief-state` as a **private** GitHub repository with an initialized `main` branch. It must be separate from both `P00NSMASHER/capturebrief` (public code) and `P00NSMASHER/permitplate-state` (PermitPlate private operating records).
2. Issue a **new fine-grained token with Contents: Read and write ONLY for `capturebrief-state`**. Do not copy, broaden or reuse `PERMITPLATE_STATE_TOKEN`. Place the new token in the operator's protected secret manager as `CAPTUREBRIEF_STATE_TOKEN`. Never paste either token or the recovery phrase into ChatGPT, documentation, commits, logs, or CLI arguments.
3. Approve an encrypted source workstation/worker, restricted local workspace, retention and access plan, and **separately controlled recovery key**. The GitHub private repository stores only encrypted blobs, not the plaintext report, sources, buyer identity, trial registry or recovery key.
4. Perform a **fictional/public-only first rehearsal on the owner-controlled machine**, and only then validate a new-device download and independent decrypt on a second authorized device. CaptureBrief stays marked not independently recovered until this has been evidenced.

Private storage on GitHub is a provider choice, not blanket permission to handle customer information without the access, retention and recovery acceptance above.

## Current implemented transport (small supervised first-customer pilot)

`scripts/github_private_custody.py` uploads **only the AES-256-GCM encrypted .cbak** created by `scripts/full_case_backup.py`. It uses GitHub's HTTPS Contents API and your existing GitHub account. It **never** writes PermitPlate's state repository, never accepts a caller-supplied alternate repo, and does not open a new service or create a charge.

The pilot is intentionally size-limited to **900,000 encrypted bytes per complete-case bundle**, and the configured private repository must remain within a **40,000 KB inspected size**. Larger backups must **fail closed** for an explicitly reviewed storage plan, not silently create extra cloud charges or drop original evidence. GitHub private repositories can consume account storage, so confirm free-plan limits before expanding this bounded pilot. No automatic pruning or deletion is implemented.

Each encrypted backup is stored immutably at a content-addressed path that includes its SHA-256. GitHub's private API must re-read and match every byte after upload, including on retries. A digest/path collision or wrong remote original blocks; no overwrites or forced pushes. Only hashes, sizes and non-sensitive status appear on output.

## Operator commands

Create and locally verify the **complete** encrypted case archive using the existing recovery tool (interactive recovery phrase, NOT an environment variable):

~~~sh
python scripts/full_case_backup.py create \
  --private-root /approved/private/CaptureBrief/fictional-case \
  --inventory /approved/private/CaptureBrief/fictional-case/backup-inventory.json \
  --backup-file /approved/private/backup-staging/fictional-case-1.cbak

python scripts/full_case_backup.py verify \
  --backup-file /approved/private/backup-staging/fictional-case-1.cbak
~~~

After the private repo and dedicated token are provisioned, read-only preflight and explicit encrypted upload:

~~~sh
python scripts/github_private_custody.py preflight

python scripts/github_private_custody.py upload \
  --encrypted-case /approved/private/backup-staging/fictional-case-1.cbak \
  --approve-upload
~~~

The upload prints the **ciphertext SHA-256**. On a **different approved device** with separately controlled access and recovery key, retrieve the exact encrypted object to a new, owner-only path:

~~~sh
python scripts/github_private_custody.py retrieve \
  --sha256 EXACT_UPLOADED_CIPHERTEXT_SHA256 \
  --output /approved/private/fresh-remote-ciphertext.cbak

python scripts/full_case_backup.py restore \
  --backup-file /approved/private/fresh-remote-ciphertext.cbak \
  --output-dir /approved/private/new-empty-restore/fictional-case-1
~~~

Compare every restored source/report/registry/authorization ledger digest to the previously retained original inventory, reconcile any later ledger writes, and independently retain provider download receipt, different device identity and a recovery-custodian attestation. Never reset a used nonce or a reserved business because an older backup was restored.

## Readiness boundaries

- **Code-level integration:** ready for QA. The transport uses no live token or real customer data during CI. Provider requests are simulated for adversarial tests.
- **Verified already:** PermitPlate's private repo exists, is private, and uses GitHub for durable operational records. That establishes the **provider model**, not authorization to mix the products' data.
- **Still required before 100% first-customer operating readiness:** `capturebrief-state` must be created and verified; its distinct token configured; encrypted data retention/access approved; fictional archive uploaded, re-read, independently downloaded and decrypted on a second authorized device with separately held key; signed operator evidence retained.
- **Not prelaunch prerequisites:** existing customer, customer feedback, customer report approval or customer payment. When an actual customer arrives, complete official solicitation/amendment history, original sources, internal report review and explicit per-message approval remain per-case delivery gates.

Never claim that GitHub HTTPS readback alone proves a separately held production recovery key or successful independent customer recovery. This design **does not use Cloudflare R2**, which is not required, or any new paid service.
