# CaptureBrief Product Core v0.14 — Human Rule Version Review

Updated: September 21, 2026

CaptureBrief is a human-supervised, public-source Pursuit QA second pass. v0.14 adds a hash-bound human rule-version review transition: every citation candidate is explicitly tracked, left unresolved, or ignored by a named reviewer, while applicability remains unresolved until the later Decision Evidence review cites the solicitation-specific basis.

## v0.14 — Human Rule Version Review

Citation discovery and rule-version selection are now separate, auditable states.

A current v0.13 proposal cannot disappear into an informal analyst judgment. Every detected occurrence must receive exactly one human decision:

- `TRACK_VERSION` — retain one specific pinned `rule_source_id` from the proposal as the edition/version that should be carried forward for deeper review;
- `UNRESOLVED` — the reviewer cannot establish which edition should be carried forward yet;
- `IGNORE` — the citation is not material to the bounded pursuit QA review, with an explicit reason.

### No implicit latest-version behavior

When multiple editions are available, the reviewer may choose an older edition if that is what the solicitation/incorporation evidence supports.

The system does not:
- sort “newest” into authority;
- force the most recent observed edition;
- treat a selected edition as applicable;
- change a buyer assumption merely because a rule version was selected.

A `TRACK_VERSION` result always carries:

- the exact selected `rule_source_id`;
- citation, namespace, agency and edition;
- exact upstream repository/revision/path and source hash;
- reviewer reason;
- `applicability = UNRESOLVED`;
- `applicability_authoritative = false`;
- `can_auto_apply = false`.

### Complete human coverage

The review is fail-closed:

- every proposal occurrence requires one decision;
- duplicate decisions are rejected;
- selecting a rule version not present in that occurrence's proposal is rejected;
- `IGNORE` and `UNRESOLVED` may not smuggle in a selected version;
- every decision requires a reason;
- reviewer identity and timezone-aware review time are required.

The complete review is content-addressed and bound to the exact proposal SHA-256. If the proposal changes, the old review is no longer current.

### Work-queue handoff

Before review, the operator queue contains:

`rules:review-candidates`

After a complete human-confirmed review, that lookup task closes. Any remaining rule-dependent assumption work still appears through the Decision Evidence trace.

This is intentional:

**Rule version selected != rule applies != assumption resolved.**

### CLI

Review input example:

    {
      "reviewer": "CaptureBrief reviewer",
      "reviewed_at": "2026-09-21T16:45:00Z",
      "decisions": [
        {
          "occurrence_id": "RULEMENTION:...",
          "decision": "TRACK_VERSION",
          "selected_rule_source_id": "RULESRC:...",
          "reason": "The solicitation cites this edition; applicability still requires trace review."
        }
      ]
    }

Apply the human review:

    python -m capturebrief_core.rule_cli case-review-citations \
      case-with-rule-candidates.json rule-review.json \
      -o case-with-rule-review.json \
      --result-output rule-review-transition.json

The selected version is context for the later Decision Evidence applicability review, not a substitute for it.

## v0.13 — Rule Citation Candidates

CaptureBrief can now turn retained solicitation/amendment text into a **rule-review proposal** without turning citation detection into legal applicability.

The operator supplies reviewed/extracted text associated with a public case source. CaptureBrief:

1. binds the text-processing run to the case source ID and retained document SHA-256;
2. finds explicit `FAR ...` / `DFARS ...` references;
3. conservatively recognizes regulation-shaped bare citations such as `52.204-21` and `252.204-7012`;
4. records line, character span, exact mention, surrounding context and text SHA-256;
5. queries the local append-only rule registry;
6. returns **all matching pinned editions**, not a selected “latest” edition;
7. places the proposal into the operator work queue as `HUMAN_REVIEW`.

### Conservative namespace hints

An explicit FAR/DFARS prefix is recorded as an explicit namespace hint.

For a bare citation, number ranges can be used only as a **non-authoritative search hint**:

- FAR-shaped parts ≤ 53 → FAR candidate lookup;
- 2xx numbering → DFARS candidate lookup.

If a heuristic lookup produces no result, CaptureBrief may fall back to citation-only registry search and exposes that fallback. Namespace inference is never an applicability conclusion.

Bare-citation recognition requires a regulation-shaped three-digit section component to reduce ordinary decimal false positives. Explicitly prefixed citations may still use shorter regulatory forms.

### Candidate proposal semantics

Every matched occurrence records:

- source ID;
- retained document SHA-256;
- extracted text SHA-256;
- line and character span;
- exact citation mention;
- surrounding context;
- namespace hint + hint basis;
- every pinned matching `rule_source_id`;
- edition, agency, source repository/revision/path and source SHA-256 for each candidate.

And every proposal explicitly states:

- `can_auto_select_version = false`;
- `can_auto_apply = false`;
- `review_required = true`.

A missing registry match stays visible for human review rather than being interpreted as “rule does not exist” or “does not apply.”

### Case binding

`case-propose-citations` refuses to process a source unless:

- its source ID exists in the case;
- it is retained as `PUBLIC`;
- the case contains a valid document SHA-256.

The extracted text may help find citations, but it does not become authoritative rule evidence merely because a parser found a number.

### Operator queue

A current citation proposal creates:

`rules:review-candidates`

as a human-only P1 task.

The reviewer must:
- decide which candidate edition, if any, is relevant;
- cite the solicitation/incorporation/effective-date basis;
- preserve unresolved state when the controlling edition cannot be established;
- record applicability later in Decision Evidence.

The task can never auto-execute.

CLI:

    python -m capturebrief_core.rule_cli case-propose-citations \
      rules.sqlite case.json \
      --source sam-current=current-solicitation.txt \
      --captured-by "CaptureBrief reviewer" \
      --observed-at 2026-09-21T16:30:00Z \
      -o case-with-rule-candidates.json \
      --result-output rule-candidate-transition.json

This closes the lookup gap between retained solicitation text and the v0.12 rule registry while leaving the actual bid/rule judgment with the reviewer.

## v0.12 — Rule Source Registry

CaptureBrief now has a first-class rule-source layer beneath Decision Evidence.

The registry pins exact machine-readable FAR/DFARS snapshots and deviation discovery sources, normalizes them into content-addressed rule records, and keeps multiple editions side-by-side. It is designed to answer:

> **Which exact rule text/version did the reviewer use, where did it come from, and what changed?**

It does **not** answer:

> **Does this rule automatically apply to this solicitation?**

That remains a human-reviewed Decision Evidence judgment with cited basis.

### Pinned source catalog

`RULE-SOURCE-CATALOG.json` currently pins:

- GSA machine-readable FAR DITA at an exact Git revision;
- GSA machine-readable DFARS DITA at an exact Git revision;
- the `acqagent/rfo-deviations` agency-deviation manifest snapshot;
- `acqagent/far-collector` as collection/reference implementation provenance only.

The source catalog deliberately distinguishes source roles. A collector or deviation index can help locate evidence without becoming authority for applicability.

### Rule version record

A normalized FAR/DFARS rule source retains:

- namespace;
- citation;
- agency;
- edition label;
- exact source repository;
- exact 40-character Git revision;
- exact source path and HTTPS URL;
- raw source SHA-256;
- normalized text SHA-256;
- observation time;
- paragraph-level locators and hashes;
- optional explicit effective dates;
- explicit effective-date authority state;
- `applicability_authoritative = false`.

### Time semantics stay separate

CaptureBrief does not collapse these into one date:

- repository commit time;
- CaptureBrief observation time;
- regulatory publication date;
- rule effective date;
- solicitation incorporation date/version;
- buyer decision time.

**A newer Git commit is not an effective date. A newer rule edition is not automatically the controlling edition.**

If an effective date is not established from a reviewed authoritative source, it remains `UNKNOWN`.

### Append-only history and change review

The SQLite registry stores content-addressed rule versions append-only.

A later source version can be diffed against an earlier version. A changed diff produces:

- `review_required = true`;
- `automatic_applicability_change = false`.

The older version remains available for replay of the earlier bid decision.

### FAR / DFARS DITA handling

The GSA DITA parser:

- accepts a full pinned Git revision;
- derives the citation from the machine-readable title/autonumber;
- retains paragraph locators;
- hashes the original DITA and normalized text separately;
- rejects DTD/entity declarations;
- refuses to infer an effective date from source-control metadata.

### Deviation discovery boundary

The agency-deviation manifest is normalized into content-addressed source candidates with agency, FAR Part, URL, size and source revision.

Those rows are **discovery evidence only**:

- manifest presence does not prove the deviation applies;
- filename/agency/part match does not prove the deviation is current;
- manifest date does not establish effective date;
- a candidate PDF must still be reviewed and tied to the solicitation/rule question before it can support an applicability conclusion.

### Decision Evidence bridge

A validated normalized FAR/DFARS source can be converted into:

1. a CaptureBrief public source-manifest row; and
2. a Decision Evidence rule-text snapshot.

That makes the exact reviewed rule text available to an assumption trace while preserving the human applicability boundary.

CLI:

    python -m capturebrief_core.rule_cli catalog
    python -m capturebrief_core.rule_cli parse-dita rule.dita \
      --namespace FAR --agency "FAR Council" --edition "FAC ..." \
      --repository GSA/GSA-Acquisition-FAR --revision <40-char-sha> \
      --source-path dita/52.204-21.dita --source-url <pinned-url> \
      --observed-at 2026-09-21T16:00:00Z -o rule.json
    python -m capturebrief_core.rule_cli add rules.sqlite rule.json
    python -m capturebrief_core.rule_cli list rules.sqlite --citation 52.204-21
    python -m capturebrief_core.rule_cli diff rule-old.json rule-new.json
    python -m capturebrief_core.rule_cli parse-deviation-manifest manifest.csv \
      --repository acqagent/rfo-deviations --revision <40-char-sha> \
      --observed-at 2026-09-21T16:00:00Z -o deviations.json

See `RULE-SOURCES.md` for the source-authority and review boundary.

## v0.11 — Decision Evidence

The product promise is now:

> **Know what your bid decision rests on.**
>
> CaptureBrief shows the exact public-source passages, source versions, reviewed rule editions, and changes behind the assumptions your team is using — plus what still needs verification.

Decision Evidence sits after the existing acquisition and packet-integrity controls:

`intake -> complete history -> current authority -> packet/reference closure -> required bytes -> assumption Decision Evidence -> human release`

It does not replace any earlier gate.

### Exact evidence contract

For every reviewed assumption, CaptureBrief can retain:

- a content-addressed public source snapshot bound to the case source manifest and original document SHA-256;
- an exact line-bounded passage plus human-readable page/section/paragraph locator;
- the evidence state and buyer-facing finding, which must match the underlying review exactly;
- reviewer identity and timezone-aware review time;
- explicit rule-review scope: `REQUIRED`, `NOT_RELEVANT`, or `UNRESOLVED`;
- a pinned FAR / DFARS / agency-supplement / class-deviation edition when a rule review is required;
- applicability state: `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED`, with a reviewed rationale and cited basis;
- source-version relationships such as `AMENDS`, `CORRECTS`, and `SUPERSEDES`;
- a concrete evidence request for unresolved/source-limited assumptions.

### Fail-closed invariants

- **Newest publication is not automatically the controlling edition.**
- Repository commit date, observation time, rule effective date, solicitation incorporation, and controlling edition are separate facts.
- A hash proves retained-byte consistency; it does not independently authenticate the publisher or decide legal applicability.
- Rule applicability remains a named human review decision with cited basis.
- Synthetic/illustrative traces cannot authorize customer release.
- New intake-generated cases set `decision_trace_required = true`.
- Older stored cases remain readable and are not retroactively represented as fully traced.

### Change watch

Decision history is append-preserving.

When a new source/rule version is observed:
- the older trace remains intact;
- applicability does not change automatically;
- a review-required event is emitted;
- only assumptions dependent on the changed source/rule are reopened.

Deletion or in-place mutation of retained trace history is reported as an integrity violation.

### Operator behavior

Decision-evidence gaps enter the existing work queue as `HUMAN_REVIEW` tasks. Automation may preserve evidence and identify that review is required; it may not approve the assumption or rule applicability.

CLI:

    python -m capturebrief_core.trace_cli check case.json
    python -m capturebrief_core.trace_cli report case.json --format markdown -o decision-evidence.md
    python -m capturebrief_core.trace_cli report case.json --format html -o decision-evidence.html
    python -m capturebrief_core.trace_cli freeze case.json --directory evidence/decisions
    python -m capturebrief_core.trace_cli compare before.json after.json

See `DECISION-EVIDENCE.md` for the product contract and buyer-display boundary.

## v0.3 source architecture

### Automated
- **SAM Get Opportunities Public API v2** — current/latest-active assertion and current `resourceLinks`.
- **SAM Data Services Contract Opportunities extracts** — action/version membership across active and declared fiscal-year archive coverage.

### Human-supervised
- SAM UI pages and the undocumented resource-manifest web-UI implementation surface, used only when deletion/tombstone or historical packet state cannot be established from approved APIs/extracts.

The old automated SAM web-UI manifest poller and canary are retired. Production code now throws if asked to automate that surface.

## History receipt

`history-from-extracts` scans official Contract Opportunities CSV extracts, hashes each extract, exact-matches the solicitation number, disambiguates by AAC when possible, and issues a Data Services history receipt.

A Data Services receipt records:
- every observed Notice ID/action UUID;
- per-action source-row hashes;
- extract SHA-256 values;
- active vs archive source;
- supplied and missing fiscal-year coverage;
- AAC/office family context;
- `ordering_authoritative = false`;
- `current_action_authoritative = false`.

A receipt becomes `COMPLETE` only when the declared archive-year scope is explicitly confirmed and every required archive year plus the active extract is present. CaptureBrief does not guess the family start year.

## Current-action receipt

`current-from-api` uses the documented Opportunities v2 API with an API key supplied through an environment variable. The API observation is not allowed to redefine the history set: its `noticeId` must already be a member of the Data Services receipt.

This creates the required separation:

`HISTORY MEMBERSHIP != CURRENT ACTION`

The documented API's latest-active assertion proves currentness; Data Services proves version membership.

## Attachment evidence

Historical/deletion-inclusive SAM resource manifests can still be normalized and hashed, but only as human-supervised observations. Automated polling of the undocumented web-UI manifest endpoint is disabled by source policy.

For current attachments, CaptureBrief may download only an exact `resourceLinks` URL bound to an approved Opportunities API observation. It refuses guessed resource URLs.

## Release gates

The existing case schema remains backward-compatible. The evidence pipeline adds stricter acquisition rules without silently changing the case format.

A case can reach `READY_FOR_HUMAN_RELEASE` only when applicable gates pass:
1. current/terminal authority;
2. complete history evidence;
3. deletion-inclusive per-action packet evidence where required;
4. semantic reference closure;
5. required public byte hashes;
6. assumption/source/timezone rules.

Unknowns remain unknown. Restricted or source-limited evidence cannot become a resolved gate-changing fact.

## CLI

    python -m capturebrief_core.cli history-from-extracts SOL-123 active.csv \
      --archive 2026:FY2026_archived_opportunities.csv \
      --seed-notice-id <NOTICE_ID> --scope-start-fy 2026 --scope-end-fy 2026 --confirm-scope \
      -o history.json

    SAM_API_KEY=... python -m capturebrief_core.cli current-from-api \
      SOL-123 history.json 09/01/2026 09/30/2026 -o current.json \
      --observation-output current-observation.json

    python -m capturebrief_core.cli normalize-manifest <ACTION_UUID> manually-saved-manifest.json \
      --observed-at 2026-09-21T13:00:00-04:00 -o manifest.json

    python -m capturebrief_core.cli capture-api-resource current-observation.json '<RESOURCE_LINK>' \
      -o artifact.bin --receipt-output artifact-receipt.json

## Operator workflow

The product now turns the existing website intake directly into fulfillment work.

`case-from-intake` maps the Netlify form fields into a deliberately non-evidentiary case:
- customer assumptions begin as `UNPROVEN / VERIFY_NOW`;
- no source is invented;
- no intake statement is promoted to evidence;
- the public/non-sensitive confirmation is required.

`work-queue` then derives the smallest next-step queue from the case state. Tasks are deduplicated, prioritized, and labeled by execution mode:
- `AUTOMATED_APPROVED_SOURCE` — safe for documented API/extract automation;
- `HYBRID` — automated retrieval plus an explicit human boundary;
- `HUMAN_REVIEW` — source interpretation or evidence CaptureBrief must not automate.

The queue currently covers history establishment, family/current authority, missing historical manifests, reference closure, required public-byte capture, source linkage, ownership, next actions, and deadline timezone defects.

CI exercises the full path:

    website-shaped intake JSON -> case skeleton -> operator work queue

This makes the fulfillment process reproducible rather than dependent on the founder remembering the next evidence step.

## Remaining P0

The remaining automation gap is proving the **history scope start** without guessing. Until GSA exposes a narrower all-version family query with authoritative completeness semantics, CaptureBrief requires an explicit scope boundary for Data Services archive coverage. The product should prefer one extra human confirmation over a false “all amendments found” claim.


## Receipt contract verification

Approved automation receipts are verified semantically, not only by their outer SHA-256.

For `APPROVED_EXTRACT` history receipts, release requires the Data Services source contract, non-authoritative ordering/currentness flags, action-set equality, valid row hashes, confirmed archive scope with no gaps, approved source-snapshot URLs and hashes, active-extract evidence, and a valid family/seed binding.

For `APPROVED_API` current-action receipts, release requires the documented Opportunities v2 source class, the `SAM_GET_OPPORTUNITIES_V2` contract, Notice ID equality, a valid API-payload digest, and resource links that remain inside the approved API-resource-link contract.

Recomputing an outer receipt hash after altering those semantics cannot make the receipt green.


## Full-catalog Data Services index

The preferred history path is now a reusable, content-addressed Data Services index rather than per-case CSV scanning.

A pinned human-supervised first-party archive catalog defines the public Contract Opportunities archive slots CaptureBrief must inspect through the current fiscal year. For the September 21, 2026 catalog snapshot, that means FY1970, FY1980, and every FY1998-FY2026 archive plus the active extract. The future-listed FY2030 entry is retained in the catalog evidence but is not required for FY2026.

The SQLite evidence index:

- streams CSV rows instead of loading the active extract into memory;
- hashes each extract before indexing;
- can retain a read-only content-addressed CSV copy named by SHA-256;
- preserves old source snapshots when a slot refreshes while `current_sources` points to the newest indexed snapshot;
- indexes solicitation number, Notice ID, AAC, office, source slot, row hash, and source-extract hash;
- performs large-source work once and reuses the index across customer pursuits.

A `FULL_CATALOG` history receipt is accepted only when the pinned catalog snapshot verifies, every required archive slot plus ACTIVE is indexed, the independently supplied seed Notice ID is present, and the family filter is anchored to that seed rather than chosen from bulk ordering.

Useful commands:

    python -m capturebrief_core.cli archive-catalog
    python -m capturebrief_core.cli history-index-plan history.sqlite
    python -m capturebrief_core.cli history-index-fetch history.sqlite ARCHIVE:2026 fy2026.csv --snapshot-dir evidence/snapshots
    python -m capturebrief_core.cli history-index-ingest history.sqlite active.csv --kind active --snapshot-dir evidence/snapshots
    python -m capturebrief_core.cli history-index-status history.sqlite
    python -m capturebrief_core.cli history-from-index history.sqlite SOL-123 --seed-notice-id <VERIFIED_ACTION_UUID> -o history.json

`history-index-fetch` downloads exactly one explicitly requested approved source slot. CaptureBrief does not silently initiate a whole-catalog multi-gigabyte sync.


## Data Services freshness

GSA's Get Opportunities documentation states that active notices are updated daily and archived notices weekly. CaptureBrief therefore treats source freshness as part of history completeness, not an operator convenience.

Current full-catalog policy:
- ACTIVE slot: must have an approved first-party source check within 48 hours;
- ARCHIVE slots: must have an approved first-party source check within 9 days.

The extra margin allows normal publication/check scheduling without silently stretching a daily/weekly source into an indefinite cache.

The index distinguishes:
- `APPROVED_FETCH` — bytes were fetched by CaptureBrief from the approved SAM Data Services extract URL;
- `OPERATOR_FILE` — a local file was imported for analysis but its claimed source retrieval was not independently performed by the product.

An operator import may populate the index and accelerate analysis, but it appears in `unverified_slots` and cannot support `HISTORY_COMPLETE`.

`history-index-plan` now identifies three remediation reasons:
- `MISSING`
- `STALE`
- `UNVERIFIED`

A fresh approved fetch of unchanged bytes reuses the existing content-addressed source snapshot while updating that slot's source-check time. Source snapshots remain immutable; freshness is a property of the current slot verification, not a rewrite of historical bytes.

Official cadence reference: https://open.gsa.gov/api/get-opportunities-public-api/


## Index-aware operator queue

The fulfillment queue now accepts the shared Data Services index plan as operational context.

When history is not yet complete:

- **index complete + documented API seed available** → queue `history:issue-from-index` as an approved automated step;
- **index complete + no current-action seed yet** → queue `history:seed-current-action` so the family is anchored by the documented Opportunities API rather than bulk ordering;
- **index missing/stale/unverified slots** → queue one `history-index:refresh` task carrying the exact source-slot remediation plan and reason counts;
- **index says incomplete but cannot explain why** → queue `history-index:diagnose` for human review;
- **no index context supplied** → retain the generic hybrid `history:establish` fallback.

CLI:

    python -m capturebrief_core.cli history-index-plan history.sqlite -o index-plan.json
    python -m capturebrief_core.cli work-queue case.json \
      --api-observation current-observation.json \
      --history-index-plan index-plan.json \
      -o work-queue.json

This reduces the operator workflow from “remember how to establish history” to an explicit executable next action.


## v0.4 — Intake resolution without bulk guessing

The reusable full-catalog Data Services index now resolves customer intake references directly.

Supported identity inputs:
- SAM action URLs such as `https://sam.gov/opp/<ACTION_UUID>/view`;
- SAM workspace URLs containing `/opp/<ACTION_UUID>/`;
- a bare 32-character SAM action UUID;
- a bare solicitation number.

A SAM action URL/UUID is treated only as an **independent seed identity**, not as proof that the action is current. CaptureBrief looks that exact Notice ID up in the current content-addressed Data Services index, resolves its solicitation family/AAC, and issues the history receipt from the full catalog.

A bare solicitation number is intentionally weaker. CaptureBrief returns candidate family/action groups but will not let Data Services choose a seed or current action. The operator must supply an independent Notice ID/currentness source.

Useful commands:

    python -m capturebrief_core.cli parse-opportunity-ref 'https://sam.gov/opp/<ACTION_UUID>/view'

    python -m capturebrief_core.cli history-index-resolve history.sqlite       'https://sam.gov/opp/<ACTION_UUID>/view' -o resolution.json

    python -m capturebrief_core.cli case-resolve-history history.sqlite intake-case.json       -o resolved-case.json --resolution-output resolution.json

The case resolver:
- preserves the buyer's assumptions as unproven;
- attaches the source-hashed Data Services history receipt;
- replaces the unresolved family ID with a SAM family identity;
- keeps `family_status = UNKNOWN` until a separate approved current/terminal authority source proves status;
- never links customer assumptions to Data Services history merely because the family was resolved.

Index freshness still controls whether the resolution is `RESOLVED` or `RESOLVED_PARTIAL_COVERAGE`. Missing, stale, or operator-imported/unverified slots cannot be promoted by the resolver.

## Resumable explicit catalog synchronization

The index can now advance its missing/stale/unverified slot plan without one command per archive:

    python -m capturebrief_core.cli history-index-sync history.sqlite evidence/downloads       --snapshot-dir evidence/snapshots

The safe default processes **one** remediation slot. This makes the operation resumable and prevents an accidental multi-gigabyte full-catalog pull.

A whole remaining catalog sync requires an explicit opt-in:

    python -m capturebrief_core.cli history-index-sync history.sqlite evidence/downloads       --snapshot-dir evidence/snapshots --all

Fresh approved slots are skipped. Each requested extract is still streamed, SHA-256 hashed, indexed, and optionally copied into content-addressed evidence storage.

## Updated remaining P0

History membership no longer needs a guessed family start year when the full pinned archive catalog is indexed. The next production bottleneck is **case orchestration after history resolution**:

1. use the documented Opportunities API to verify active currentness without bulk ordering;
2. preserve current API resource links and capture required current public bytes;
3. route historical deletion/tombstone gaps to human-supervised review;
4. complete conservative named-reference extraction/closure;
5. return only then to the decision-changing assumption review.

The product should continue preferring an explicit unknown/human-review task over a guessed current action or silently incomplete packet.


## v0.5 — Apply documented current-action evidence

Once the full history receipt exists, a documented SAM Opportunities API observation can now be applied to the case as one validated state transition:

    python -m capturebrief_core.cli case-apply-current       resolved-case.json current-observation.json       -o current-case.json --transition-output current-transition.json

The transition refuses to run unless:
- history already validates as `HISTORY_COMPLETE`;
- the API observation is `SAM_GET_OPPORTUNITIES_V2 / APPROVED_API`;
- the API Notice ID belongs to the retained history set;
- the API solicitation number agrees with the retained history family;
- the generated current-action receipt passes the approved API semantic contract;
- every returned resource link is inside the approved SAM API-resource-link contract.

On success it:
- sets `family_status = ACTIVE`;
- records the independently verified current action ID;
- appends/deduplicates the current-action receipt;
- adds/replaces the controlling `sam-current-api` source;
- preserves the API payload digest and current resource-link inventory;
- creates source-object artifact stubs for current API resource links without pretending their bytes or semantic importance have been reviewed;
- leaves every customer assumption unchanged and unlinked.

The transition is idempotent: replaying the same observation does not duplicate receipts, sources, or resource objects.

### Why the resource stubs stay conservative

A URL returned by the documented API proves a current public source object is discoverable. It does **not** prove:
- the object is required for the buyer's decision;
- its bytes were captured;
- its filename/semantic role;
- historical tombstone completeness;
- reference closure.

Therefore newly discovered API resources begin as `required_for_analysis = false` and `BYTES_NOT_YET_CHECKED`. The later reference/compliance review decides which objects become load-bearing.

## Updated orchestration boundary

The operator path is now:

`intake -> resolve seed/family -> complete history receipt -> apply current API observation -> historical packet review -> reference closure -> required byte capture -> assumption QA`

The next automation target is generating the documented API search windows from retained history evidence so an operator does not have to hand-enter `postedFrom/postedTo` ranges. Those windows may guide API retrieval, but they must never become currentness evidence themselves.


## Human-confirmed reference inventory

Named-dependency extraction now uses a two-stage trust contract after current-action evidence is applied:

1. `references-propose` performs deterministic local candidate extraction from retained public text and can only emit `PROPOSED`.
2. `references-confirm` requires explicit human source coverage, a decision on every candidate, reasons for ignored hits, and allows manual additions for parser misses.

Automation may surface likely references to amendments, attachments, exhibits, appendices, annexes, enclosures, schedules, drawings, procurement systems, and external URLs. It may not declare that inventory complete or decide that a missing reference is irrelevant.

A `COMPLETE` reference scan is cryptographically bound to:
- the exact proposal payload;
- reviewer identity and timezone-aware review time;
- the exact source set reviewed;
- a decision for every proposed candidate;
- every manual reviewer addition;
- the exact final reference-ID set attached to the case.

Changing the case reference set after review invalidates the scan.

After human confirmation, every tracked dependency begins `UNRESOLVED`. It must become:
- `RESOLVED_TO_RESOURCE` with verified source object and hashed bytes;
- `SUPERSEDED_BY` with a verified successor and explicit supersession evidence; or
- `EXTERNAL_DEPENDENCY` with explicit non-public state, URL, and reason.

Anything else remains fail-closed.

CLI:

    python -m capturebrief_core.cli references-propose \
      --source notice=notice.txt \
      --source solicitation=solicitation.txt \
      -o reference-proposal.json

    python -m capturebrief_core.cli references-confirm \
      reference-proposal.json reference-review.json \
      -o reference-review-result.json

The operator queue is sequential:
- no reviewed scan → `references:propose` (local automation);
- proposal exists → `references:review-proposal` (human-only);
- reviewed inventory exists → individual reference-resolution tasks.

This closes a major failure mode exposed by the packet-integrity research: “the parser did not see a named amendment” can never become evidence that the amendment is safely irrelevant.


## v0.6 — Derive documented API search windows from history

Operators no longer need to hand-enter `postedFrom` / `postedTo` ranges for the documented Get Opportunities API.

CaptureBrief derives bounded retrieval windows from the posted-date observations already retained inside a complete Data Services history receipt:

    python -m capturebrief_core.cli current-search-plan resolved-case.json -o current-plan.json

The plan is deliberately non-authoritative:
- `currentness_authoritative = false`;
- `ordering_authoritative = false`;
- every individual window carries `date_basis_authoritative = false`.

The dates only answer: **which documented API requests should we try?** They never answer: **which action is current?**

If any history action lacks a usable posted date, the automated plan is marked incomplete and CaptureBrief refuses automated current retrieval rather than silently searching an incomplete time range.

### One-command documented current retrieval

With a complete history case and a SAM API key:

    SAM_API_KEY=... python -m capturebrief_core.cli case-fetch-current       resolved-case.json -o current-case.json --result-output current-result.json

This operation:
1. builds the non-authoritative search plan;
2. queries the documented Opportunities API across the required <=1-year windows;
3. ignores zero-result windows without treating them as terminal evidence;
4. rejects multiple conflicting current candidates;
5. binds the returned Notice ID back to the independent history set;
6. applies the validated current-action transition to the case.

A zero-match result is explicitly:

`NO_ACTIVE_MATCH`

with the product meaning:

> No active API match was found. This does not prove cancellation, archival, or inactivity.

Terminal state still requires an appropriate first-party terminal source.

## v0.6 + reference-review boundary

The current retrieval layer and the human-confirmed reference inventory intentionally stay separate.

Approved automation may establish:
- complete history membership;
- latest-active currentness;
- current API resource-link discovery.

Only human review may establish that the retained notice/document source set was semantically reviewed for named dependencies. Automated retrieval cannot promote a proposed reference inventory to `COMPLETE`.

## Updated next bottleneck

The approved automated path now covers:

`intake seed -> full history -> planned current API retrieval -> current-action case transition -> current resource discovery`

The highest-value remaining product work is on historical packet review and reference closure: reduce the manual burden of matching human-confirmed references to observed resources and captured bytes without crossing the source-policy boundary into automated SAM UI scraping.


## v0.7 — Apply reviewed references without hand-editing the case

The human-confirmed reference inventory can now be applied directly to a case:

    python -m capturebrief_core.cli case-apply-reference-review       current-case.json reference-review-result.json       -o referenced-case.json --transition-output reference-review-transition.json

This transition accepts only a `COMPLETE / HUMAN_CONFIRMED` inventory. Every newly attached reference must still be:

- `resolution = UNRESOLVED`;
- `source_object_state = UNRESOLVED_SOURCE_OBJECT`;
- `byte_state = BYTES_NOT_YET_CHECKED`.

A review result cannot smuggle pre-resolved dependencies into the case.

Reapplying the exact same review is idempotent. If closure work has already begun, replaying the same review preserves those later resolutions rather than resetting them. Replacing the reviewed inventory with a different one after closure work begins is rejected.

### Explicit reference-resolution transition

Each confirmed dependency can then be resolved with a separate human decision record:

    python -m capturebrief_core.cli case-resolve-reference       referenced-case.json <REFERENCE_ID> resolution-decision.json       -o resolved-case.json --transition-output resolution-transition.json

Every resolution decision requires:

- reviewer identity;
- timezone-aware review time;
- explicit reason;
- a hash-bound resolution decision record.

Supported outcomes remain:

- `RESOLVED_TO_RESOURCE`;
- `SUPERSEDED_BY`;
- `EXTERNAL_DEPENDENCY`.

### Stronger byte binding

A `RESOLVED_TO_RESOURCE` reference now has to satisfy all of these simultaneously:

1. the resource ID exists in retained manifest evidence;
2. the case contains a retained artifact/byte receipt for that resource;
3. the artifact is `BYTES_VERIFIED_HASHED`;
4. the artifact SHA-256 is valid;
5. the reference SHA-256 exactly matches that artifact SHA-256.

A syntactically valid but unrelated SHA-256 can no longer satisfy reference closure.

### Supersession and external dependencies

A `SUPERSEDED_BY` transition requires:
- the successor resource to exist in retained manifest evidence;
- the supersession source ID to exist in retained case sources.

An `EXTERNAL_DEPENDENCY` transition requires:
- an absolute HTTP(S) URL;
- an explicit reviewer reason;
- an explicit `BYTES_EXTERNAL_DEPENDENCY` or `BYTES_RESTRICTED` state.

### Change watch

Because reference IDs do not change when closure state changes, applying a resolution emits the existing `REFERENCE:<id>` / packet-reference-closure change events. Only assumptions that declared those triggers reopen.

## Updated operator path

The end-to-end path is now:

`intake -> history resolution -> documented current retrieval -> current case transition -> reference proposal -> human reference confirmation -> apply review -> resolve each dependency -> required byte capture -> assumption QA`

The remaining friction is attaching byte-capture receipts to case artifacts without manual JSON editing and proposing likely resource matches for human review. Matching may reduce reviewer effort, but automation must never auto-close a reference.


## v0.8 — Apply captured byte receipts to artifacts

An approved current-resource download receipt can now be applied directly to the corresponding case artifact:

    python -m capturebrief_core.cli case-apply-byte-receipt       current-case.json resource-receipt.json       -o byte-case.json --transition-output byte-transition.json

The transition does not trust a SHA-256 value by itself. It verifies that:

- the receipt contract is `SAM_GET_OPPORTUNITIES_RESOURCE_LINK`;
- the receipt was collected as `APPROVED_API`;
- the receipt state is `BYTES_VERIFIED_HASHED`;
- the receipt has a valid observation time, size, and SHA-256;
- its source URL is an approved SAM API resource link;
- that exact URL was retained in the case's current API resource-link inventory;
- the receipt's API payload digest exactly matches the case's retained current API observation;
- the derived resource ID identifies exactly one verified source-object artifact in the case.

On success the artifact receives:

- SHA-256;
- `BYTES_VERIFIED_HASHED`;
- byte size;
- byte observation time;
- byte receipt SHA-256;
- source contract.

The complete receipt is also retained in `packet.byte_receipts`, keyed by a canonical receipt digest.

Reapplying the same verified bytes is idempotent. A later receipt with a different SHA-256 for an already verified artifact is rejected rather than silently replacing evidence.

## Reference closure now binds to retained artifact bytes

For `RESOLVED_TO_RESOURCE`, the closure validator now requires the reference SHA-256 to exactly match the retained case artifact SHA-256. A valid-looking but unrelated digest can no longer satisfy closure.

The explicit reference-resolution transition also marks the matched artifact `required_for_analysis = true`, so the artifact becomes part of the release audit as soon as a reviewer makes it decision-relevant.

This creates an auditable chain:

`documented API observation -> approved resource URL -> byte receipt -> case artifact -> human-confirmed reference -> reference resolution`

## Updated remaining friction

The next operator-time reduction target is a **local reference-to-resource match proposal**. CaptureBrief can use normalized names and retained metadata to suggest likely resource IDs, but the result must remain a proposal only. Ambiguous same-name resources, deleted predecessors, and historical/current replacements must stay visible, and a human must still make the closure decision.


## v0.9 — Local reference-to-resource proposals

After the human-confirmed dependency inventory exists, CaptureBrief can now propose likely retained source objects without changing any reference resolution:

    python -m capturebrief_core.cli case-propose-reference-matches       reviewed-case.json -o matched-case.json       --transition-output match-transition.json

The proposal operates only on evidence already retained in the case:
- manifest resource IDs;
- presentation names;
- action membership;
- deletion/access state;
- declared size and MIME type;
- captured byte state/SHA-256 where available.

It does not browse, scrape, retrieve new sources, or use hidden external data.

### Deterministic matching

The local matcher uses normalized tokens, attachment/amendment number anchors, name containment, and token overlap. It penalizes conflicting numeric anchors, so `Attachment 4` is not casually matched to `Attachment 5`.

The proposal is hash-bound to:
- the human-confirmed reference scan;
- the exact confirmed reference set;
- the retained resource-union digest.

Any change to those inputs makes the proposal stale and the work queue requests a new one.

### Ambiguity is a first-class output

The proposal retains:
- candidate resource ID;
- deterministic score and reasons;
- all observed names;
- action IDs;
- artifact states;
- deletion/tombstone risk;
- access/unavailable risk;
- retained byte state/hash.

If two resource IDs share the same filename, both remain visible. A tie at the top score sets `ambiguous_top_score = true`; same-name multi-resource IDs are listed explicitly.

This addresses the real packet-history failure mode where a deleted predecessor and a later replacement share the same presentation name.

### No automatic closure

Every proposal and every per-reference row carries:

`can_auto_resolve = false`

Even an exact normalized name, exact resource URL, verified bytes, and a unique top score do not change the reference. A human must still apply a `case-resolve-reference` decision.

### Work queue sequence

For a complete human-confirmed inventory:

1. unresolved references + no current match proposal → `reference-matches:propose` (`AUTOMATED_LOCAL`);
2. current match proposal exists → human `reference:<id>` tasks receive up to five top candidates and ambiguity flags;
3. reviewer chooses/justifies a closure state through the validated reference transition.

This reduces lookup work without weakening the evidence boundary.


## v0.10 — Capture current bytes directly from retained case evidence

Once a documented current API observation has been applied to the case, CaptureBrief no longer needs the original observation JSON supplied again just to capture a current resource.

A current artifact can be captured and applied in one step:

    python -m capturebrief_core.cli case-capture-artifact       current-case.json <ARTIFACT_ID>       -o captured-case.json       --bytes-output artifact.bin       --transition-output capture-transition.json

Before any download, the transition verifies:

- the case retains a `SAM_GET_OPPORTUNITIES_V2` current observation;
- the retained API payload SHA-256 is valid;
- the retained resource-link count matches the retained resource-link set;
- the artifact is exactly one verified public source object;
- its resource URL is in that retained current API resource-link set;
- the URL is inside the approved SAM resource-link contract.

It then performs the approved download, hashes the bytes, creates the resource receipt, and applies that receipt back into the case through the v0.8 byte-binding contract.

### Idempotency

If an artifact already carries `BYTES_VERIFIED_HASHED` plus a valid SHA-256, the command does not download the file again. It returns `ARTIFACT_ALREADY_CAPTURED`.

Conflicting later bytes remain fail-closed.

### Work queue authorization

The work queue now recognizes the case's retained validated current API observation as sufficient evidence that a matching current resource URL can use `AUTOMATED_APPROVED_SOURCE`.

Operators no longer have to pass an external API-observation object merely to make a byte-capture task executable.

This creates the approved straight-through segment:

`history-complete case -> documented current API -> current resource discovery -> current byte capture -> retained artifact receipt`

Human review remains required for historical tombstone state, semantic reference completeness, and final reference closure decisions.
