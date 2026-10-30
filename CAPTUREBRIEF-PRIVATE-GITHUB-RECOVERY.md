# CaptureBrief encrypted backup on PermitPlate's existing private GitHub cloud

**Decision (October 29, 2026):** Reuse PermitPlate's established **private GitHub repository** storage model, with **no new paid storage service** and no customer-contact automation. PermitPlate's actual operational repository is `P00NSMASHER/permitplate-state` and is private. CaptureBrief must **not** store its own customer files, keys, ciphertext or trial registry inside PermitPlate's repository.

Use a **separate dedicated private GitHub repository** under the same existing account: `P00NSMASHER/capturebrief-state`. The separate repository was **confirmed private with an initialized `main` on October 30, 2026**. The owner reports placing a fine-grained token in the public application's `CAPTUREBRIEF_STATE_TOKEN` Actions secret; its effective permission and first authenticated transfer require the new main-only readback test, not an assertion based on the secret's name. The code refuses any unapproved destination or credential scope.

## Live owner-secret functional rehearsal: VERIFIED WITH FICTIONAL CASES

**Verified October 30, 2026:** [CaptureBrief Actions run #41024445424](https://github.com/P00NSMASHER/capturebrief/actions/runs/41024445424) completed **successfully on both Linux and Windows** at merged commit `09562f7f73370b30879b01d3c6e8b3634cc8e27c`. Each independently started runner used GitHub's protected `CAPTUREBRIEF_STATE_TOKEN` repository secret to read the private `P00NSMASHER/capturebrief-state` repository, then encrypted a **fully fictional** 13-component case using the public `TEST_KEY`, uploaded only AES-256-GCM bytes, re-read the content-addressed bytes from the actual private repository, decrypted them locally and verified 13 exact original hashes.

Two small encrypted demo objects were observed under `encrypted/complete-case/v1/` in `P00NSMASHER/capturebrief-state`. No real customer identity, customer report, plaintext, production encryption key, external send or payment was involved. PermitPlate's private operational repository is a different repository and was never a backup destination.

**Precisely established:** owner-created GitHub Actions secret WORKS for private GitHub authenticated reading and a small real write/readback, and the application backup/restore code interoperates with GitHub on both Linux and Windows. **Not established:** independently held production recovery key, actual off-device restore by a separate authorized owner device, permission-policy approval, customer data storage authorization, or complete SAM.gov amendment history. The two tests each restored a file on their own runner, **not the same archive across two different physical devices**.

The one-time automatic live upload was removed after successful verification. Subsequent routine CI uses mocked provider storage and fictional test keys without reading the private repository secret or uploading new ciphertext. New live exercises require an explicit, separately reviewed main-branch test action.

## Owner-only setup, no new service or paid membership

1. Create `P00NSMASHER/capturebrief-state` as a **private** GitHub repository with an initialized `main` branch. It must be separate from both `P00NSMASHER/capturebrief` (public code) and `P00NSMASHER/permitplate-state` (PermitPlate private operating records).
2. Issue a **new fine-grained token with Contents: Read and write ONLY for `capturebrief-state`**. Do not copy, broaden or reuse `PERMITPLATE_STATE_TOKEN`. Place the new token in the operator's protected secret manager as `CAPTUREBRIEF_STATE_TOKEN`. Never paste either token or the recovery phrase into ChatGPT, documentation, commits, logs, or CLI arguments.
3. Approve an encrypted source workstation/worker, restricted local workspace, retention and access plan, and **separately controlled recovery key**. The GitHub private repository stores only encrypted blobs, not the plaintext report, sources, buyer identity, trial registry or recovery key.
4. Perform a **fictional/public-only first rehearsal on the owner-controlled machine**, and only then validate a new-device download and independent decrypt on a second authorized device. CaptureBrief stays marked not independently recovered until this has been evidenced.

Private storage on GitHub is a provider choice, not blanket permission to handle customer information without the access, retention and recovery acceptance above.

## Current implemented transport (small supervised first-customer pilot)

`scripts/github_private_custody.py` uploads **only the AES-256-GCM encrypted .cbak** created by `scripts/full_case_backup.py`. It uses GitHub's HTTPS Contents API and your existing GitHub account. It **never** writes PermitPlate's state repository, never accepts a caller-supplied alternate repo, and does not open a new service or create a charge.

The pilot is intentionally size-limited to **900,000 encrypted bytes per complete-case bundle**, and the configured private repository must remain within a **40,000 KB inspected size**. Larger backups must **fail closed** for an explicitly reviewed storage plan, not silently create extra cloud charges or drop original evidence. GitHub private repositories can consume account storage, so confirm free-plan limits before expanding this bounded pilot. No automatic pruning or deletion is implemented.

Before an upload or retrieval the transport now checks the **canonical, bounded full-case AES-GCM envelope format**, including field types, salt/nonce, declared plaintext size, payload length and tag-length position. These checks reject a plaintext file with only a forged magic prefix. **They do not authenticate the ciphertext or prove a valid complete-case ZIP without the independently held recovery phrase.** The operator must first run `full_case_backup.py verify`; only an actual separate-device restore can establish operational recovery.

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
