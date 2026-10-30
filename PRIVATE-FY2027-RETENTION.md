# CaptureBrief FY2027 public-source private retention candidate

Status: INTEGRATED OPERATOR UTILITY, NOT FY2027 SOURCE APPROVAL.

The utility is part of main through [PR #69](https://github.com/P00NSMASHER/capturebrief/pull/69).
Integration and passing tests do not attest that private original retention,
full-catalog indexing or independent recovery have been completed.

The official public SAM.gov Contract Opportunities archive listed FY2027
on October 19, 2026. A one-time GitHub Actions observer downloaded the
complete 1,607,260-byte original, counted 1,104 CSV data rows and computed
SHA-256:

    7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce

Automated source evidence:
https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451

## Retain the identical original on an authorized PRIVATE machine

Use a protected directory OUTSIDE the public Git checkout or GitHub Pages.
Disk encryption, least-privilege access and encrypted off-device backups
must be independently verified by the operator.

Example on a private Linux installation:

    python scripts/retain_fy2027_candidate.py --private-dir /var/private/capturebrief/source-candidates

The CLI accepts no alternate URL, expected checksum or test override.
It uses the approved PUBLIC SAM Data Services FY2027 download URL and may
follow only the exact corresponding official falextracts S3 object after
the safe redirect validator approves each hop. It refuses unexpected
file sizes, checksums, redirects, incomplete responses and oversize files.

On success, the private directory contains two immutable local files:

- FY2027-(SHA256).csv: exact original source bytes verified to SHA-256.
- FY2027-(SHA256).receipt.json: separate original provenance metadata,
  observed time, local digest, source entrypoint and unapproved review flags.

No original file content is ever put in the public Git repository by this
command. Temporary failed downloads are cleaned up. The tests use
synthetic files and never contact SAM.gov.

## Requirements still outstanding

1. A reviewer must independently approve the official 36-file archive
   listing. It includes FY1969 and FY1981 in addition to the older
   FY1970/FY1980 and continuous FY1998-FY2027 years. FY2028 was not
   listed; FY2029 and FY2030 were future-listed.
2. A protected, up-to-date private archive index must contain and
   independently verify all required approved original ACTIVE and
   ARCHIVE slot bytes. One original FY2027 file does not prove full history.
3. The reviewed catalog change must be approved separately and must
   preserve fail-closed freshness and provenance requirements.
4. Genuine customer receipt, payment, source packets, independent
   procurement rule review, verified ZIP delivery and live 14-day
   watch operations are distinct release gates.

The candidate command DOES NOT update the source index because the
production catalog still correctly refuses FY2027. It does not approve
publisher origin, charge money, contact a buyer, schedule an activity,
or authorize customer release.

Offline tests:

    python -m unittest tests.test_retain_fy2027_candidate -v
