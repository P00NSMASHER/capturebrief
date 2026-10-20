# FY2027 archive history: read-only public metadata capacity candidate

**Status: UNREVIEWED PLANNING ONLY.** This tool is not source-download acceptance, full-original evidence, source indexing, catalog promotion, a machine-capacity acceptance, live customer work, or independent reviewer signoff.

The previously observed first-party SAM.gov public listing contained 36 filenames: FY1969, FY1970, FY1980, FY1981, each year FY1998–FY2027, plus future-listed FY2029 and FY2030. No FY2028 was listed. The candidate FY2027 historical requirement is **34 archive-year objects plus a separate ACTIVE extract**. This probe excludes the active extract and future-listed years, and cannot establish source completeness.

## No original bulk acquisition

The tool constructs only documented public SAM Data Services `FY####_archived_opportunities.csv` download entrypoints for the **34 frozen candidate years**. It uses the exact PR #53 transport verifier, which guards every official SAM-to-S3 redirect before a connection. It requests `Range: bytes=0-0` and accepts a `206` response only when Content-Range describes exactly byte zero of a positive total. At most **one byte** of each actual response is read; `200`/Range-ignored responses are closed without reading the body and explicitly marked unknown.

The recorded object size is a **server-declared metadata value**, not a hash, authenticity proof, a source file or independent source review. Errors are type-only to prevent presigned URL disclosure. The CLI writes no data to disk, prints only bounded numeric metadata and non-sensitive transport hosts, and does not use the undocumented SAM UI listing API as a new automation source.

The initial isolated GitHub Actions observer checks just FY1969, FY1981, FY2026 and FY2027. It runs no scheduler, upload, billing, deployment, customer communications, source index updates or local-retention operations. The 34-year size sum is available only if each candidate returns valid Range metadata; otherwise the result is incomplete and cannot be used as a comprehensive capacity estimate. The ACTIVE extract and private SQLite indexing overhead also require separate accounting.

Run **only in an already-authorized network environment**, if a reviewer needs a further read-only diagnostic:

    python scripts/fy2027_archive_capacity_probe.py --live-public-metadata --years 1969,1981,2026,2027

Later full candidate probe, after independent source-collection policy review:

    python scripts/fy2027_archive_capacity_probe.py --live-public-metadata --years all

Do **not** download the 34 complete originals into PAAM-L044's limited local disk merely because metadata estimates appear to fit. Do not introduce FY2027 into production until original publisher bytes, private retention, disk encryption, encrypted off-device restoration, catalog signoff and independent QA all pass.


## October 19, 2026 — all 34 years: metadata observation complete

[Exact GitHub Actions #39350338311](https://github.com/P00NSMASHER/capturebrief/actions/runs/39350338311)
returned **34 of 34** guarded HTTP 206 responses, each with a strictly
bounded `Range: bytes=0-0` and declared source-object size. Exactly
**34 source bytes** were sampled across the archive year set; no bulk CSV
originals were retained.

- **34 archive CSVs, server-declared sum: 20,333,624,076 bytes**,
  or approximately **20.33 decimal GB / 18.94 GiB**.
- The largest declared annual object is FY2023, **1,277,614,651 bytes**.
- FY2026 alone declares **1,023,490,271 bytes**.
- FY2027 declares **1,607,260 bytes**, consistent with the previously
  independently hashed FY2027 original, but the present range probe did
  not itself rehash the complete object.
- **Excluded**: current ACTIVE CSV, disk space needed for SQLite and
  working files, duplicate staging, backups, encryption overhead, and
  real-case customer data.

A frozen numeric **unreviewed metadata receipt**, with all 34 exact
FY-to-size mappings, lives in
`research/fy2027_archive_capacity_observation_20261020.json`.
Offline tests assert it does not grant source-index, publisher, catalog,
human-review or customer-release authority.

**Operational decision:** A private host with less than 18.94 GiB available
cannot hold even one complete uncompressed set of the 34 candidate
originals. A significant additional allowance is needed for index,
inflight working files and independently protected backups. Do not
launch indiscriminate bulk collection on an undersized machine.

As a **possible zero-spending planning option only**, Oracle currently
documents **200 GB combined Always Free boot/block volume storage** in
a tenancy's home region, subject to the tenancy's actual quota,
eligible VM capacity and provisioning choices:
https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
Cloudflare R2's **10 GB-month** free allowance is insufficient for these
uncompressed 34 archive objects:
https://developers.cloudflare.com/r2/pricing/
No Oracle infrastructure or Cloudflare bucket was provisioned by this
research, and free-tier availability/billing safety must be verified in
the actual connected account before any infrastructure changes.
