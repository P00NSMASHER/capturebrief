# CaptureBrief: source readiness repair and customer simulation

Observed October 27, 2026. Engine base: `34137cf5c3939033717ce8fbc954ece34c264aff`.
This record separates completed engineering and real data checks from source
authority, durable operation, and actual customer delivery.

## Completed repairs and evidence

The free admission preflight now has an explicit `--offer free` mode. It does
not request a Stripe transaction or a 14-day watch for a no-card one-question
offer. It retains catalog, source-index, identity, source-review, and message
authorization boundaries. Paid/default completion is unchanged. The separate
free reservation/report pipeline remains responsible for free completion.

The old FY2027 checksum-retention command intentionally verifies immutable
October 19 bytes. It cannot refresh a source that has since changed from
1,607,260 to 4,518,793 bytes. The new
`scripts/refresh_sam_source_candidate.py` provides the missing current-source
path: an explicit bounded download through the existing guarded SAM transport,
temporary CSV validation, content-addressed immutable originals, a separate
marked candidate index, and independent replay of every indexed source row.
Each actual observation gets a new receipt; no historical receipt is rewritten.
It refuses an unrelated existing directory or production database. Its output
never approves a catalog or customer release.

SAM API and resource transport errors now suppress credential-bearing chained
HTTP/URL exception messages. Status codes remain useful; keys and signed URLs
do not appear in a default traceback. Existing injected test openers remain
supported.

### Genuine full-original checks

Both files were fetched using the approved public SAM Data Services entrypoints
and exact guarded first-party redirects. The maintained refresh command was
then run against the same real originals on October 27 at 14:18:49–14:18:54 UTC.

| Slot | Complete bytes | Rows independently replayed | SHA-256 |
|---|---:|---:|---|
| ACTIVE | 212,898,407 | 70,878 | `9cc53cb26df3bf0c60d4621c872ff861254c80b223fd89e0d9f6c5c9b90d4d80` |
| ARCHIVE:2027 | 4,518,793 | 3,082 | `ea1d2c726566fc9546e80f0ce559f77b104809ad5c86e2095b9935bc03648ea0` |

All **73,960** source rows agreed with the actual SQLite projection, including
row digests and normalized/displayed fields. The two-slot candidate index was
37,781,504 bytes. These are real public originals and actual parser/index runs,
not fixture responses. Raw CSVs, operational database paths, public-source
contact details and signed URLs are excluded from the committed evidence.

Evidence: `research/sam_active_refresh_20261027.json` and
`research/sam_fy2027_refresh_20261027.json`. ACTIVE membership does not prove
which action is currently controlling. Neither complete original establishes
the other 33 required archive slots, source-catalog signoff, or independent
off-device recovery.

## Exact catalog review candidate

The rendered first-party archive listing was independently inspected by the
root operator agent. The retained accessibility snapshot was captured at
**2026-10-27T14:14:00.860Z** from:

https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public

It is an **automated, unreviewed rendered UI snapshot**, not human approval or
original HTTP page bytes. `research/sam_archive_visible_inventory_20261027.txt`
contains 15,140 UTF-8 bytes, SHA-256
`428724d4b0cfecc448994c4caa9eac4e03b73b41087b59004cb37b92a3c320b0`.

The exact inactive proposal is in
`research/sam_catalog_review_candidate_20261027.json`:

| Catalog field | Current approved value | Observed proposal, still unapproved |
|---|---|---|
| Required years | FY1970, FY1980, FY1998–FY2026 | FY1969, FY1970, FY1980, FY1981, FY1998–FY2027 |
| Future-listed years | FY2030 | FY2029, FY2030 |
| Current through | FY2026 | FY2027 |
| Visible files | Historical observation | 36 PUBLIC filenames; 34 at or before FY2027 |

FY2028 is absent. No old year disappeared. A promotion must include newly
observed FY1969 and FY1981, not just append FY2027 to the old inventory.
The proposed observation timestamp is not a human-review timestamp. Reviewer
identity and review reference are deliberately null.

Run `python scripts/validate_catalog_review_packet.py` to verify the entire
retained snapshot hash, exact filenames, public-item descriptions, proposed
year sets, and unapproved state. Negative controls reject invented FY2028,
dropped early years, changed source/time/hash, and simulated reviewer claims.

`ARCHIVE-CATALOG.md` explicitly requires a new human-supervised first-party
observation before catalog promotion. `FY2027-CATALOG-REVIEW-CANDIDATE.md`
explicitly says that a bot observation is not this signoff. The completed
packet makes the remaining source approval concrete: independently inspect the
official listing, compare it with these exact 36 filenames, retain the actual
reviewer/time/reference, then submit the corresponding catalog version/year
change with whole-catalog hash and rollover tests through normal review/CI.
No production catalog value changed in this repair.

## Protected operation review candidate

Fresh one-byte observations through the approved guarded extract transport
confirmed all 34 required archive sizes at 14:14:50 UTC. Their total is
**20,346,928,128 bytes**. Adding the fully read current ACTIVE original yields
**20,559,826,535 bytes** for one complete original generation before SQLite,
refresh working copies, historical versions, and backups.
`research/sam_archive_capacity_20261027.json` preserves every declared size.
One byte per archive is capacity evidence, not a complete-file integrity check.

The concrete proposed private deployment layout is:

| Component | Proposed requirement | Acceptance evidence |
|---|---|---|
| Source worker and primary volume | Operator-owned private persistent host; start with 100 GiB encrypted capacity as a planning allowance | Actual location, encryption and owner-only access verified; free-space checks before each bounded fetch |
| Immutable originals | Private `originals/`, keyed by slot and SHA-256; retain the prior generation until replacement/recovery is verified | Full original hashes, exact source identity and per-slot observation receipts |
| Source index | Private SQLite alongside originals, never in GitHub Pages or a public repository | All 35 required slots fresh; exact retained bytes and row projection checks |
| Independent backup | Separate access-controlled encrypted storage; plan 100 GiB initially, then measure actual generations/index footprint | Independently downloaded/restored originals, unchanged index/receipt hashes and verified access |
| Recovery key | Independently retained by the owner, separate from source host and backup | Restore succeeds without depending on a key held only on the lost source host |
| Refresh operation | Active check at least daily; archive revalidation at least weekly, within existing 48-hour/9-day gates | Fresh approved transport observations; stale/error cases remain blocked |

The capacity allowances are proposals, not purchased storage or capacity
measurements. No specific approved durable host, off-device backup location or
independent key/recovery evidence was supplied in this session. A private
temporary QA directory is not substituted for that infrastructure.

On the chosen protected host, the new candidate refresh tool can prepare one
source at a time without promoting it:

```sh
python scripts/refresh_sam_source_candidate.py --private-dir /private/review-candidate --slot ACTIVE --max-bytes 300000000
python scripts/refresh_sam_source_candidate.py --private-dir /private/review-candidate --slot ARCHIVE:2027 --max-bytes 16000000
```

The same command accepts each explicitly observed required archive year with
an explicit bound up to 2 GB. It excludes unobserved FY2028 and future FY2029/
FY2030 from candidate ingestion. It never adopts the production index. After
actual catalog/source and storage review, use the existing production history
index fetch/sync commands and the retained originals; do not rename the TEST
customer registry or claim that a two-slot candidate is complete coverage.

## Simulated customer reviews on real public inputs

`scripts/run_customer_source_simulation.py` uses the exact private candidate
originals and rechecks every indexed row before selecting two ACTIVE federal
software notices with future recorded response deadlines and one FY2027
archived technology notice. It rejects future observation times and sources
outside the existing 48-hour ACTIVE / 9-day archive freshness limits. It performs
actual request parsing/private import,
one-business free reservation, idempotent retry, exact source text/quote
construction, observation-only history, report rendering, and structured
simulated customer review. It sends nothing and does not access a real customer
or paid registry.

One current input was **Global Macroeconomic Software Licenses**, solicitation
`2031JW27Q00011`, recorded in the ACTIVE original as posted October 26 with a
November 9, 2026, 10:00 −05:00 response deadline. The preview explicitly does
not certify that this is the newest controlling deadline.

Each readable preview starts with the public input, the question, the bounded
answer, the unverified-currentness disclosure, a specific next action, and
the no-card free versus explicit $149 paid scope. The technical appendix is
the real product renderer. All cases have `decision_trace.synthetic=true`.

Two fictional perspectives review factual accuracy/citation trace, whether
the question is answered, currentness disclosure, next action and offer clarity:

- **Small federal-IT bidder:** the recorded fact is understandable, the free
  terms are explicit, but a controlling current deadline/action is still open.
- **Proposal manager:** source hashes and locators are traceable and the limits
  are disclosed; the preview cannot clear the pursuit for delivery or a bid
  decision. The technical blocker appendix is longer than a final customer
  handoff should be.

The simulated result is `SIMULATED_REVIEW_REQUIRES_SOURCE_COMPLETION`, not a
satisfaction score, real customer approval, conversion or paid sale. The actual
LIVE free-report builder rejected all three cases, including the explicit
`DELIVERY_SYNTHETIC_EVIDENCE` blocker. Mutated exact quotations were rejected.
The simulation separately writes visibly TEST previews and feedback; no LIVE
delivery file is created. Aggregate evidence is
`research/customer_source_simulation_20261027.json`; private previews contain
no source contact fields or real buyer identities.

## Remaining real boundaries

The first-customer requirement is not circular: `--stage admission` already
defers real customer case, deliverable and watch evidence until the appropriate
later stage. The new free offer additionally removes irrelevant payment/watch
requirements. Simulated customer reviews satisfy workflow testing only.

The remaining source boundaries are the actual human-supervised catalog
observation, all required original/index freshness on protected retained storage,
independent recovery, and a valid documented current-action API observation for
the actual pursuit.

The actual main-only SAM access observation ran after PR86 on engine revision
`42b41620b230cce49f5ca8866605654b17060da7`. At **2026-10-27T14:39:46 UTC** it
returned `BLOCKED_SAM_API_KEY_UNAVAILABLE`, with `api_key_present_in_runtime=false`,
`api_access_verified=false`, and `latest_active_observation_verified=false`.
This establishes that this Actions job did not receive the required credential;
it does not claim that no credential exists anywhere in the owner's accounts.
The redacted artifact upload succeeded. The observed job outcome and declared
artifact digest are retained in
`research/sam_current_access_runtime_20261027.json` and linked to
[the actual workflow run](https://github.com/P00NSMASHER/capturebrief/actions/runs/40523225120).

The concrete next access step is to add the owner's valid SAM API key as the
`SAM_API_KEY` GitHub Actions secret for this repository through GitHub's secure
settings, then rerun the bounded main-only observation. Never paste the key in
chat, a commit, a workflow log, or an issue. A successful access observation would
establish only its bounded current record; it would not approve the whole
family/history or replace source review.

No existing FY2027 limited-history escape exists: `DECLARED_RANGE` explicitly
requires its end year not exceed the production-approved catalog. A FY2027
range remains `OBSERVED_ONLY`, and the free report still uses unchanged source,
history, manifest, reference and currentness gates. A document-specific preview
must not be relabeled as a completed current-pursuit review.

## Verification of this change

The complete local regression suite passed **736 tests** on October 27, 2026
(`python -m unittest discover -s tests -q`, 12.898 seconds). Fourteen new tests
cover the refresh/retention boundary, unchanged catalog restrictions,
offer-specific admission, credential-safe errors, the frozen review packet,
source freshness and mutation, transport-receipt/index provenance binding, and
simulated delivery rejection. Compilation
of the core and scripts and `git diff --check` also passed.

After integrating the three exact probe files merged in PR86 at
`42b41620b230cce49f5ca8866605654b17060da7`, the combined local tree passed
**742 tests** in 13.585 seconds, with compilation and whitespace checks passing.
The integration retained the reviewed source-refresh changes and all three
probe blobs unchanged.

The maintained catalog-packet command returned
`EXACT_RENDERED_CATALOG_CANDIDATE_REVIEW_REQUIRED`, with the production catalog
still FY2026. The maintained free admission command returned
`PILOT_ADMISSION_BLOCKED`, specifically `BLOCKED_STALE_CATALOG` and
`BLOCKED_CATALOG_STALE`, while reporting `NO_PAYMENT_FOR_FREE_CHECK` and
`NOT_INCLUDED_IN_FREE_CHECK` correctly.

The final actual-source simulation ran at **2026-10-27T14:25:19.357550+00:00**.
It passed all three TEST scenarios using the genuine originals above, preserved
exact-source and preview hashes, and wrote zero external messages, payments,
real customer registry changes, or LIVE customer reports. This is engineering
acceptance evidence for the simulated workflow; it does not close the real
boundaries above.
