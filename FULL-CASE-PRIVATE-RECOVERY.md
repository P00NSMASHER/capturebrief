# CaptureBrief complete private case backup: pre-customer rehearsal

**Status:** portable encrypted full-case snapshot utility, NOT production
off-device recovery acceptance. No real customer is required to test this
tool. Use fictional case identities and public federal source documents
for the first independent rehearsal.

The existing scoped-private backup protects a narrow SAM observation.
The separate free-check registry backup protects ten-business reservations.
This utility fills the missing pre-release *entire case inventory* backup:
intake case, first-party action and resource originals, original incorporated
rule editions, incoming-request receipt, business/scope proof, report and
report receipt, source inventory, registry snapshot, and prepared message body.
The actual client data never belongs in public GitHub or CI.

## Offline source preparation

Use an owner-approved private encrypted workstation, restricted 0700
directories and 0600 files on Linux, or operator-only NTFS ACLs on Windows.
No secret, customer or signing key belongs in Git, Pages or Actions.

Create the source inventory inside the private case directory, never inside
source control. The schema is capturebrief-complete-private-case-snapshot-v1.
It must contain case_sha256 of the canonical reviewed case JSON and a files
array of {id, kind, path, sha256} records. Populate every pre-release file
kind enumerated in capturebrief_core.accepted_case_release.REQUIRED_KINDS,
except OFFDEVICE_BACKUP and RECOVERY_RECEIPT. Those two cannot exist before
the backup and independent restore. Include at least one ACTION_ORIGINAL.
Missing or altered originals, duplicate IDs and unsafe paths fail closed.

This validates file bytes only. It does not authenticate SAM provider origin,
history completeness, business identity or human signoff.

## Create, verify, and restore

On a trusted operator machine install pinned cryptography and type a strong
recovery phrase interactively. Do NOT put it in a command argument,
environment variable, GitHub secret or chat message.

    python -m pip install --only-binary=:all: cryptography==46.0.4

    python scripts/full_case_private_backup.py create \
      --private-root /approved/private/capturebrief/case-001 \
      --inventory /approved/private/capturebrief/case-001/backup-inventory.json \
      --backup-file /approved/private/staging/case-001-REVISION.cbak

    python scripts/full_case_private_backup.py verify \
      --backup-file /approved/private/staging/case-001-REVISION.cbak

Encryption is AES-256-GCM and scrypt with fresh authenticated salt and nonce.
The tool verifies originals and canonical case identity, rejects source
symlinks and Windows junctions, and refuses overwriting existing archives or
restoration directories.

For an independently held NON-CUSTOMER recovery rehearsal, copy only the
encrypted file to approved off-device storage, retain its remote hash, then
download it to a different approved machine with separately held recovery
material. Never transfer decrypted customer content to unapproved services.

    python scripts/full_case_private_backup.py restore \
      --backup-file /approved/private/fresh-offdevice-download/case-001-REVISION.cbak \
      --output-dir /approved/private/empty-restore-path

Compare every restored file with its original inventory and retain the
off-device retrieval receipt and independent restoration evidence. Local/CI
tests are not production proof. A recovered archive can be stale; reconcile
newer cases and reservations before use.

The backup itself and its independent RECOVERY_RECEIPT are excluded from
this snapshot to avoid a circular hash, then added to the approved signed
release manifest after the genuine external restore. The shared one-time
authorization ledger, owner-controlled trust roster, independently held
recovery secret and other customers' cases remain separate protected assets.

Delivery remains blocked until per-case full official amendment history,
retained originals, approved private recovery, independent internal review
of the complete report and explicit authorization of the exact recipient,
message and report. No customer is needed to rehearse these operations.

## CI evidence

Pinned Linux and Windows tests use only fictional documents and test
passphrases. They exercise encrypted snapshots, exact restored-byte hashes,
corrupted ciphertext, wrong key, changed source, unsafe paths and overwrite
refusals. This proves a technical candidate, NOT a genuine customer backup
or independently held production key.
