# FY2027 original: supervised encrypted backup and recovery candidate

**Release status:** BACKUP UTILITY CANDIDATE ONLY. This tool does **not** prove an off-device backup, restoration from off-device storage, recoverability of the key, disk encryption, source catalog approval, customer readiness, or an authorized deployment.

The input is **exactly** the previously reviewed original FY2027 public SAM.gov CSV, SHA-256 `7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce`, **1,607,260 bytes**, plus the intact, nonapproved `scripts/retain_fy2027_candidate.py` receipt from PR #53. Other records, customer files, paid orders and historical years are **not** in scope.

## Cryptographic protection

`cryptography==46.0.4` supplies AES-256-GCM and scrypt (`n=32768, r=8, p=1`, 16-byte random salt). Each backup has an unpredictable fresh 96-bit nonce and authenticated canonical header. An altered encrypted file or wrong passphrase is rejected before any restored source file is written. The original record and receipt are encrypted together; no original or receipt is written to the public repository, cloud service or GitHub Actions by the CLI. The Python standard library alone is not an alternative crypto implementation.

**Secret handling:** An authorized operator must enter a *strong, independently retained recovery passphrase* on a trusted local terminal. Do not give it to ChatGPT, put it in a shell argument, GitHub, cloud-synced settings, or the backup location. Noninteractive operation optionally accepts `--passphrase-file` pointing to a privately ACL-protected **local** file outside the checkout; that option transfers key-management responsibility to the operator. A backup whose only key is on the source device is **not** recoverable after device loss.

Installation (on an authorized private workstation, not in CI production):

    python -m pip install cryptography==46.0.4

The new backup tool is **independent of the source-retention command**: it does not redownload any source, rewrite the approved catalog, create a private source index, or certify FY2027 history.

## Separate operator actions — never automatic cloud transmission

Create an empty, private backup output directory outside the public repository and outside the source-candidates directory. Then, on the private PC, using a trusted local interactive terminal:

    python scripts/fy2027_encrypted_backup.py create \
      --source-dir PRIVATE_ORIGINAL_AND_RECEIPT_DIRECTORY \
      --backup-file PRIVATE_BACKUP_DIRECTORY/fy2027-original.cbak

Recheck the encrypted file locally with the recovery key:

    python scripts/fy2027_encrypted_backup.py verify \
      --backup-file PRIVATE_BACKUP_DIRECTORY/fy2027-original.cbak

For a genuine off-device acceptance test, an authorized operator must separately upload/copy **only the encrypted `.cbak`** to an access-controlled off-device destination, download it into an independently created restore environment, compare its SHA-256 against the operator's original encrypted-backup digest, recover the separately escrowed key, and restore into a private empty directory:

    python scripts/fy2027_encrypted_backup.py restore \
      --backup-file DOWNLOADED_OFFDEVICE_COPY/fy2027-original.cbak \
      --output-dir EMPTY_PRIVATE_RESTORE_DIRECTORY

Then independently verify original SHA-256, unchanged receipt bytes, encrypted off-device storage/access, recovery key availability *independent of the source computer*, and the source machine's disk encryption. Retain evidence in private operator storage. Do **not** upload raw CSV, plaintext receipt, passwords, or customer material. Do **not** claim this one-source archive is full FY2027 historical coverage.

CI runs entirely on invented byte fixtures: intentionally corrupted ciphertext, tampered header, wrong key, changed receipt, overwrite refusal and verified local recovery. Even an all-green CI cannot count as an actual off-device copy, encrypted host, production release, or independent human review.
