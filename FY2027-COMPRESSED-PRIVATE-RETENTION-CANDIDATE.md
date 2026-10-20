# CaptureBrief FY2027 review candidate — immutable lossless compressed original storage

**STATUS: UNAPPROVED SECURITY AND SOURCE-RETENTION CANDIDATE.**

A guarded, single-fiscal-year operator tool is available at
`scripts/retain_compressed_sam_archive_candidate.py`. The official
PUBLIC SAM.gov Data Services extract entrypoint is the ONLY network input.
All signed intermediate redirect hops are checked by PR #53's exact
transport validator. Archive years and expected byte sizes are frozen to
the 34-year **UNREVIEWED** metadata observation in PR #58.

The live study on GitHub Actions #39353747897 sampled THREE distinct
small ranges of each of 34 official archived CSV originals; aggregate
sample-based compressed-size proxy was approximately **4.60 GiB** against
**18.94 GiB** of declared original bytes. These are estimates, **not
complete compressed originals** or a guaranteed archive-space maximum.
The active source, SQLite index, working room and independently encrypted
off-device backups require separate capacity budget.

## Bounded on-demand retention only

In a reviewed PRIVATE storage location, outside GitHub, Cloud Sync and
a public web root, and only AFTER validating device disk encryption,
local directory ACLs, sufficient free disk and off-device encrypted
backup/restore arrangements, an authorized operator may run:

    python scripts/retain_compressed_sam_archive_candidate.py retain --year 2026 --private-dir PRIVATE_ARCHIVE_ROOT

This **does not happen automatically**, it has no scheduler, and only
one exact candidate-year source is fetched per invocation. The CLI accepts
no custom URL or checksum override. Exact first-party S3 binding is
enforced before any redirected bytes are read. The entire source
is streamed to an on-disk `.csv.gz` archive; it is SHA-256 hashed
over its original uncompressed bytes and independently decompressed
and rehashed **before publication**. A reproducible SHA-named compressed
file and a separate immutable, explicitly UNAPPROVED provenance receipt
are retained, but the uncompressed CSV is not stored as a temporary file.
On Windows and POSIX, an immutable existing matching gzip artifact
is reused rather than overwritten. A mismatched prior receipt fails
closed, while a true idempotent replay preserves the prior
`original_observed_at` timestamp byte-for-byte.

Offline Linux/Windows tests use **only fictional originals**; no
production source is downloaded by GitHub Actions. A failed on-demand
download never approves a source and never puts a partially downloaded
archive at the content-addressed destination.

## Read-only integrity replay

    python scripts/retain_compressed_sam_archive_candidate.py verify --year 2026 --private-dir PRIVATE_ARCHIVE_ROOT --original-sha256 VERIFIED_RAW_SOURCE_SHA256

A PASS here proves **local compressed file integrity only** against
its recorded checksum and original metadata. It does not grant human
publisher approval, source-index registration, full 34-year coverage,
legal source licensing, original uncompressed-file retention signoff,
encrypted host, off-device recovery, any paid work or customer release.

**Never run a bulk 34-year operation on PAAM-L044 yet.** The machine had
14.47 GiB free on the last direct check; genuine full compressed
source, index and backup footprint are not yet established. Storage
compression is not encryption. The earlier locally encrypted FY2027
backup protects ONE original but does not provide independent recovery-key
escrow or off-device restoration.
