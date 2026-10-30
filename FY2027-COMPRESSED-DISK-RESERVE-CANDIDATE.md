# FY2027 private compressed archive — single-source disk reserve

**Candidate only. NO FY2027 catalog approval, bulk-download authority,
independent reviewer signoff, customer release, or production deployment.**

PR #60 proposes verified streaming original-byte gzip retention one frozen FY
at a time. This incremental security check fails closed **before opening the
approved SAM.gov network source** if the destination cannot demonstrate:

- Enough free bytes for **TWO concurrent worst-case incompressible gzip
  copies** (each declared original size plus 1% / 256 KiB allowance): the
  streaming compression temp and `ensure_exact_file`'s atomic publication
  copy. A further 1 MiB budgets receipt/lock/filesystem metadata;
- At least **4 GiB remaining unused** after both copies and that overhead.
  This reserve is deliberately separate from, and NOT enough to certify,
  the active extract, SQLite index, working files and independently encrypted
  off-device backups.

Read-only, no-source-fetch capacity diagnostic after creating an approved
PRIVATE directory:

    python scripts/source_disk_budget.py --private-root PRIVATE_ARCHIVE_ROOT --year 2026

Exit 0 means ONLY that the two simultaneous single-source compressed copies
plus metadata have adequate free space under the conservative 4-GiB floor. Exit 3 means insufficient local
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


## Simultaneous candidate-source download protection

The on-demand compressed retainer also holds a **private-root-wide,
fail-fast filesystem lock** from before disk-capacity inspection until
compressed-source publication, provenance receipt verification, and
temporary-file cleanup finish. A second candidate download targeting the
same directory fails **before opening an HTTP response**, rather than
both spending the same observed free-space reserve. Crash leftovers are
never assumed stale or automatically deleted; an authorized operator must
independently verify that no first run remains active before resolving a
stale lock. A post-publication crash or operator modification that leaves
an existing compressed archive writable also fails closed on retries and
read-only verification; matching SHA-256 alone cannot silently reseal it.

This guards only concurrent invocations that use the **same private root**.
Other applications and alternate roots on the same disk may still consume
space independently; the capacity check and the 4 GiB reserve do not
guarantee uninterrupted free space. Protected-main, reviewed publisher
sources, actual disk-encryption status, authenticated off-device restore
and customer release remain BLOCKED.


## Exact shared gzip expansion bound

The disk preflight and final immutable gzip writer use **the same**
`worst_case_gzip_bytes(original_bytes)` function. Previously, preflight
correctly allowed at least 1% or 256 KiB expansion, while the writer
rejected output exceeding the original by just 4 KiB. That inconsistency
could discard a valid large incompressible original after a successful
download. A dedicated 16 MiB high-entropy fictional-source regression
now requires successful lossless retention even when gzip expands by more
than 4 KiB, while still rejecting output beyond the conservative
preflight allowance. This change does not increase source download
limits or weaken checksum, protected-origin, private-file, catalog or
customer-release checks.
