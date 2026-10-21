# CaptureBrief: exact source-original-to-SQLite row projection audit

**Status: UNAPPROVED, operator-only audit candidate.**

The existing source-history engine now checks all required retained files'
SHA-256/size, official SAM.gov source URL, fiscal-year slot and indexed row
count before issuing a potentially complete history. Those cheap structural
checks alone cannot prove SQLite displayed fields and row digests are still
faithful to the immutable original bytes.

New `scripts/audit_original_index_projection.py` performs an **optional
deep, read-only, one-source-at-a-time comparison**. It:

- Opens an **EXISTING** private SQLite file using `mode=ro`,
  `query_only=ON`, with a consistent read transaction; it will not create
  an index, download any source or mutate current source approval.
- Requires an operator-supplied private `--snapshot-root` and checks
  the database's untrusted `local_path` resolves strictly inside it.
- Requires an exact documented SAM Data Services source URL, archived
  fiscal-year identity (or ACTIVE slot), and complete retained original
  SHA-256 and byte-size equality.
- Re-parses **every row** with strict original-byte text decoding and
  source-column validation; compares row order, NoticeId, normalized
  solicitation, agency/AAC/office/posted date/link fields and independently
  recomputed SHA-256 of the canonical original row against SQLite records.
- Preserves valid **header-only archives** with zero rows.
- Refuses malformed/orphan source paths and mismatched SQLite actions,
  including one changed NoticeId, posted date or row_sha256 with otherwise
  consistent original full-file hash and row count.
- Emits counts and verified source digests only. Original raw CSV data,
  identifiers, private filesystem paths, cloud credentials and client data
  are never printed, uploaded or included in CI artifacts.

For a supervised, authorized **private** source index that already exists:

    python scripts/audit_original_index_projection.py \
      --private-index PRIVATE_HISTORY_SQLITE \
      --snapshot-root AUTHORIZED_PRIVATE_SOURCE_DIR \
      --slot ARCHIVE:2027

A PASS means only that the **local** SQLite projection matches the retained
original byte-for-byte and semantically at the observed moment. It is not
independent publisher authenticity, human-approved FY2027 catalog, full
34-year source history, legal permission, a real customer case, verified
whole-disk encryption, encrypted off-device disaster recovery, or authority
to release anything.

CI uses **fictional files only**, and tests both supported operating
systems. Actual original FY2027 replay must be performed separately
in an isolated operator environment and must leave the accepted original,
unapproved catalog and release holds untouched.

The audit deliberately runs **outside the hot path**, because repeatedly
parsing the complete 20.33-GB FY2027 uncompressed candidate archive for each
customer receipt would be excessive. The existing hot history-coverage
validator still checks full-source hashes and indexed row counts; deeper
row fidelity remains a separate independent acceptance gate.
