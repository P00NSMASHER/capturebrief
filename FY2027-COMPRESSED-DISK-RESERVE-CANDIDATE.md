# FY2027 private compressed archive — single-source disk reserve

**Candidate only. NO FY2027 catalog approval, bulk-download authority,
independent reviewer signoff, customer release, or production deployment.**

PR #60 proposes verified streaming original-byte gzip retention one frozen FY
at a time. This incremental security check fails closed **before opening the
approved SAM.gov network source** if the destination cannot demonstrate:

- Enough free bytes to tolerate a worst-case **incompressible** annual
  source (declared original size plus at least 1% / 256 KiB gzip allowance);
- At least **4 GiB remaining unused** after that potential temp file.
  This reserve is deliberately separate from, and NOT enough to certify,
  the active extract, SQLite index, working files and independently encrypted
  off-device backups.

Read-only, no-source-fetch capacity diagnostic after creating an approved
PRIVATE directory:

    python scripts/source_disk_budget.py --private-root PRIVATE_ARCHIVE_ROOT --year 2026

Exit 0 means ONLY that the single-source transient file has adequate free
space under the conservative 4-GiB floor. Exit 3 means insufficient local
space; exit 2 means invalid/unavailable capacity metadata. No original CSV
is accessed by the diagnostic. The private directory must exist.

The production retainer invokes the same fail-closed preflight after checking
the destination path and least-privilege ACL, but **before** opening any
HTTP original response or creating a download temp. If the check fails,
the source original remains untouched and no compressed/receipt file appears.
All tests use synthetic originals and mocked disk-space values.

The 34-year FY2027 public archive still declares 20.33 GB (18.94 GiB)
uncompressed, with a non-guaranteed sampled gzip estimate of 4.60 GiB.
Neither this disk reserve nor sampling demonstrates aggregate capacity,
publisher authenticity, disk encryption, off-device restore/key escrow or
source-catalog review. PAAM-L044 should not be used for bulk history
collection until those separate requirements are independently verified.

**Do not auto-merge.** Independent safety review is required for each
stacked source PR, followed by actual approved operator capacity evidence
and a separate governed customer-release decision.
