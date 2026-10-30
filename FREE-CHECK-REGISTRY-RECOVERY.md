# CaptureBrief free-check reservation registry: private recovery

**Status:** operator-only recovery tooling. This is not evidence that any real
business enrolled, that an off-device production backup exists, or that a
restored registry is complete. Neither backup nor restore grants customer
admission, report release, payment, or contact permission.

The ten-business trial registry is a **separate SQLite asset** from each
case's SAM.gov originals, Decision Evidence, identity-review documents and
intake receipts. The existing scoped-case backup protects only one case and
does **not** protect the pilot's irreversible one-per-business reservations.
Use both recovery procedures. Never publish a registry or decrypted case in
public Git, GitHub Actions, Cloudflare Pages, or browser storage.

## Prepare private storage

Use an approved, device-encrypted operator workstation or private worker.
Source and destination directories must already exist and be restricted to
the authorized operator. On Linux/macOS, owner-only 0700 directories and 0600
registry files are mandatory; on Windows, verify operator-only NTFS access,
full-disk encryption and recovery-key custody outside the source device.

The CLI requires the pinned cryptography==46.0.4 dependency. It accepts a
strong recovery phrase **only through an interactive trusted terminal**.
Never put it in chat, command-line arguments, GitHub, environment variables,
backup filenames, tickets, or the same off-device location as the archive.

    python -m pip install --only-binary=:all: cryptography==46.0.4

## Create and verify a new immutable encrypted registry snapshot

After each **committed** reservation, independently check the source registry,
create a **new** .cbak name, and retain its returned encrypted-file SHA-256:

    python scripts/free_check_registry_backup.py create \
      --registry /private/capturebrief/free-checks.sqlite \
      --backup-file /private/backup-staging/free-checks-REVISION.cbak

    python scripts/free_check_registry_backup.py verify \
      --backup-file /private/backup-staging/free-checks-REVISION.cbak

The CLI performs a consistent SQLite backup including committed WAL changes,
checks quick_check, requires the exact trial schema, validates a maximum of
ten hashed business reservations, and rejects any nonzero charge, automatic
upgrade, customer-release or external-send flag. AES-256-GCM protects the
snapshot using scrypt and fresh authenticated salt/nonce. The archive cannot
silently overwrite an existing backup. It contains no raw buyer email or
customer case document; these other assets still require their own backup.

**Off-device recovery is a separate operator duty:** independently copy only
the encrypted .cbak to access-controlled off-device storage. Verify the
remote copy SHA-256, use a separately held recovery phrase, and download a
fresh copy to another approved machine. Neither GitHub CI nor a local test
counts as this production acceptance.

## Restore to a new private SQLite path, never overwrite

    python scripts/free_check_registry_backup.py restore \
      --backup-file /private/downloaded-from-offdevice/free-checks-REVISION.cbak \
      --output-registry /private/independent-restore/recovered.sqlite

Restore refuses an existing destination or SQLite journal sidecars.
The resulting status deliberately remains
FREE_REGISTRY_LOCALLY_RESTORED_RECONCILIATION_REQUIRED.

**Critical anti-rollback rule:** a previously valid encrypted backup can be
**stale**. Before trusting a recovered registry, independently reconcile
every actual reservation since its snapshot against retained original
requests, identity reviews, case receipts and any newer registry copies.
Do not use an older recovered database to restart the ten-business limit or
admit a previously enrolled business. If the latest complete reservation
history cannot be independently established, **halt new free-check admission**
until resolved. No automatic promotion or registry replacement is provided.

This tool protects only the reservation database. It does not prove that
case-specific source evidence is complete, that private source originals or
a production key were actually recovered, that human review occurred, or that
a customer report may be delivered. Continue using inspect_free_check,
evaluate_delivery_readiness, exact Decision Evidence review and explicit
per-message authorization for every real case.

## Test evidence

Synthetic Linux/Windows tests check WAL-consistent snapshots, exact schema,
idempotent restored reservations, altered ciphertext, wrong keys, unexpected
tables, forged authorization flags, invalid hashes, over-cap cohorts,
public-path rejection, and restore overwrite refusal. Test keys and records
are fictional. Passing CI establishes a working **candidate utility**, not a
production off-device restore or operator approval.
