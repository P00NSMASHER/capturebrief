# CaptureBrief complete-case encrypted backup and prelaunch recovery rehearsal

**PermitPlate-style private-state durability, not production acceptance.** The website and public GitHub repository are never customer-data storage. This entire process can be rehearsed using a fictional company; **no real customers are needed before launch**.

Earlier scoped AES-GCM backup protected only intake and selected source originals. The separate free-check registry backup protected ten-business reservations. **Neither included the entire report and one-use delivery-authorization ledger.** New scripts/full_case_backup.py can encrypt one complete bounded source/review/report/registry snapshot. It does not upload it off-device, establish production key custody or authorize customer contact.

## Required owner-approved environment

Choose an encrypted restricted primary location and a **separate** approved encrypted off-device destination with access policy, audit trail and retention/deletion rules. Keep the production recovery key under independent custody, outside the primary machine, backup and public source. A GitHub Actions test artifact is not a production backup. Never mix CaptureBrief customer data with the unrelated private PermitPlate state repository.

Work outside Git, Pages, public artifacts and shared sync. Windows requires approved disk encryption and correct NTFS ACLs; Linux/macOS requires owner-only (0700) directories and (0600) files.

## Complete frozen inventory

Create a private JSON file with schema capturebrief-complete-case-backup-inventory-v1, case_id, customer_release_authorized=false, external_send_authorized=false, and a files array of exact id, kind, relative path, and SHA-256 of retained original bytes.

Required kinds are CASE, HISTORY, RESOURCE_INVENTORY, at least one ACTION_ORIGINAL and RESOURCE_ORIGINAL, BUSINESS_EVIDENCE, INBOUND_RECEIPT, SCOPE_AGREEMENT, REPORT, REPORT_RECEIPT, REGISTRY_SNAPSHOT, AUTHORIZATION_LEDGER_SNAPSHOT, MESSAGE_BODY, plus every applicable INCORPORATED_RULE. The CLI refuses incomplete, duplicate, altered or symlinked originals. The explicit cap is 256 MiB total and 64 MiB per original. Larger cases need a separately reviewed streaming design, not an arbitrary override.

**Abbreviated fictional illustration (intentionally rejected because incomplete):**

~~~json
{
  "schema": "capturebrief-complete-case-backup-inventory-v1",
  "case_id": "CB-FICTIONAL-PRELAUNCH",
  "customer_release_authorized": false,
  "external_send_authorized": false,
  "files": [
    {
      "id": "case",
      "kind": "CASE",
      "path": "case.json",
      "sha256": "REPLACE_WITH_ACTUAL_64_HEX_SHA256"
    }
  ]
}
~~~

Use independently **WAL-consistent SQLite snapshots** for the trial registry and the shared one-use authorization ledger. Never copy an actively written SQLite DB as an ordinary file. Existing free_check_registry_backup.py has a consistent encrypted registry snapshot operation. The new command `scripts/snapshot_authorization_ledger.py` safely initializes one **empty** shared nonce ledger before customers exist, then captures a consistent SQLite snapshot including committed WAL records, validates the exact immutable schema, rejects added triggers, normalizes the journal header in memory for Linux/Windows portability, and writes a new protected 0600 snapshot. No message is sent or approved.

~~~
# In an owner-approved private directory, before admitting any real customer:
python scripts/snapshot_authorization_ledger.py init \
  --ledger /approved/private/CaptureBrief/approved-message-nonces.sqlite

# Use a new snapshot file for each complete case/recovery revision:
python scripts/snapshot_authorization_ledger.py snapshot \
  --ledger /approved/private/CaptureBrief/approved-message-nonces.sqlite \
  --snapshot-file /approved/private/CaptureBrief/nonce-snapshot-REVISION.sqlite

python scripts/snapshot_authorization_ledger.py verify \
  --snapshot-file /approved/private/CaptureBrief/nonce-snapshot-REVISION.sqlite
~~~

Include the returned snapshot's SHA-256 in the complete-case encrypted backup inventory as `AUTHORIZATION_LEDGER_SNAPSHOT`. The **single canonical ledger remains authoritative**: the utility has no restore, overwrite or reset command. Even a valid snapshot can be stale, so reconcile every later authorization before any future send or trial admission. This is distinct from the off-device, independently keyed recovery test required for actual operations.

## Encrypted local backup and independent off-device restore

Install pinned cryptography==46.0.4. The CLI uses AES-256-GCM and scrypt with a random salt and nonce, an authenticated manifest and each original's SHA. It asks for a **strong phrase interactively**; do not put it in the command line, environment, repo, email, chat or the backup location.

~~~sh
python -m pip install --only-binary=:all: cryptography==46.0.4

python scripts/full_case_backup.py create \
  --private-root /approved/private/CaptureBrief/fictional-case \
  --inventory /approved/private/CaptureBrief/fictional-case/backup-inventory.json \
  --backup-file /approved/private/backup-staging/fictional-case-1.cbak

python scripts/full_case_backup.py verify \
  --backup-file /approved/private/backup-staging/fictional-case-1.cbak
~~~

The **separate production acceptance** requires an actual approved off-device encrypted upload, remote verification/download receipt, a **different authorized device**, and a separately retained recovery key. On that device use a freshly retrieved encrypted copy:

~~~sh
python scripts/full_case_backup.py restore \
  --backup-file /approved/remote-retrieval/fictional-case-1.cbak \
  --output-dir /approved/new-empty-restore/fictional-case-1
~~~

Compare every restored_files ID and SHA with the **previously retained original inventory**, not an expectation built from the restored bytes. Reconcile registry/authorization state against later authoritative transactions, keep signed separate custodian evidence, and preserve the complete original inventory and backup SHA.

A local create/verify/restore exit 0 establishes byte integrity and a new-directory local restore only. It **never claims** independent off-device recovery, reviewer approval or customer report delivery; all authority flags remain false. No payment, source changes, customer mail or outreach occur.

## Required prelaunch proof, independent of having customers

- Approved private primary and separate off-device encrypted destination.
- Recovery key genuinely controlled separately from the source machine.
- Entire case, accepted-source originals, report, trial registry, and authorization ledger snapshotted and hashed correctly.
- Different authorized device re-downloads and decrypts the actual encrypted backup.
- Every output SHA matches previously retained originals, with signed custodian evidence of location/time/device.
- All stale snapshot/nonce histories independently reconciled; no automatic state promotion.
- Owner independently accepts security, retention and access rules.

These are **prelaunch engineering tests using fictional customer information on real approved infrastructure**, not customer acquisition or fulfillment conditions.
