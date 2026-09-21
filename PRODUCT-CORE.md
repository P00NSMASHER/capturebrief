# CaptureBrief Product Core v0.27 — Deviation-Aware Targeted Watch

Updated: September 21, 2026

CaptureBrief is a human-supervised, public-source Pursuit QA second pass. v0.23 adds a controlled class-deviation discovery path on top of the v0.22 Decision Evidence, release bundle, and targeted-watch system. It can now prove which exact pinned deviation index was inspected and surface agency/FAR-Part candidates without turning corpus membership—or corpus absence—into an applicability decision.

## v0.27 — Deviation-Aware Targeted Watch

v0.26 completed the reviewed class-deviation chain into a specific bid assumption. v0.27 closes the monitoring gap that appears **before** a reviewer has had time to rebuild that rule evidence.

The 14-day targeted watch now preserves privacy-safe fingerprints of:

- the current deviation candidate proposal;
- pinned deviation manifest revision/hash;
- candidate ID set and candidate fingerprint;
- latest captured official PDF receipt and PDF SHA-256;
- current authority review ID/currentness/effective interval;
- current assumption-specific deviation applicability review and rule-version ID.

The watch baseline does **not** retain source text, PDF bytes, or public-source URLs for this purpose.

### Early warning before re-review

A later observation can now trigger review even while the previously issued Decision Evidence trace still contains the old reviewed rule link.

CaptureBrief detects changes to:

- the pinned deviation proposal / candidate set;
- the latest official deviation PDF bytes;
- the reviewed authority state;
- the reviewed applicability state.

Each deviation event is keyed by the stable prior `deviation_source_id` where possible.

### Reopen only the assumptions that depended on it

When a deviation applicability review is current, the watch baseline maps that `deviation_source_id` to the exact assumption that depended on it.

If the official PDF later changes, CaptureBrief reopens that assumption:

`DEVIATION:<id> -> Affected assumption -> REVIEW_REQUIRED`

Other assumptions are not reopened merely because they belong to the same pursuit.

### Proposal refresh handles identity turnover

A newly pinned deviation manifest can create a new content-addressed candidate ID even when the agency/Part search is conceptually the same.

The proposal-change event therefore carries aliases for both the prior and newly observed candidate IDs. An assumption that depended on the prior candidate is reopened even before a new applicability review exists.

### Prior decision is preserved

A watch event never:

- changes `APPLIES` to `DOES_NOT_APPLY`;
- changes an assumption's `SUPPORTED / UNPROVEN / ...` state;
- edits the old rule link;
- rewrites the prior decision date.

Instead the observation records:

- `requires_human_review = true`;
- `previous_decision_preserved = true`;
- `automatic_decision_change = false`.

The buyer can therefore see that a prior decision was reasonable on the evidence available then, while still knowing that one of its dependencies has changed and must be reviewed again.

### Privacy contract

Deviation watch state contains identifiers and hashes only.

It deliberately omits:

- memo text;
- solicitation text;
- raw PDF content;
- deviation PDF URL.

This makes the watch baseline useful for change detection without turning it into a duplicate evidence warehouse.

### Validation target

The regression corpus now proves a two-assumption case:

1. A1 depends on a reviewed class deviation.
2. A2 does not.

When only the official deviation PDF changes:

- A1 reopens;
- A2 does not;
- the old Decision Evidence rule link remains untouched;
- applicability does not change automatically;
- the prior decision remains preserved.

At this point the technical source/rule/version chain is end-to-end:

`solicitation history + exact source bytes + FAR/DFARS/deviation version authority + assumption-specific applicability + dependency-aware change watch`

The next product milestone is no longer another rule-engine feature. It is running this complete chain against real public pursuits and recording whether buyers say it changed a gate decision, closed a costly uncertainty, or surfaced something they had missed.

## v0.26 — Deviation-to-Assumption Decision Evidence

v0.26 closes the class-deviation chain from public candidate discovery all the way to a specific bid assumption.

The full path is now:

`pinned index -> official PDF SHA-256 -> reviewed memo text -> effective/current/supersession review -> separate pursuit-specific basis -> CLASS_DEVIATION rule version -> assumption rule link`

### A current memo does not automatically apply

A reviewed deviation authority record may say `CURRENT` or `SUPERSEDED`, but that still does not answer whether the memo governs a particular pursuit.

Resolved applicability therefore requires a separate exact Decision Evidence passage from retained:

- solicitation text;
- amendment text; or
- other pursuit-specific context.

The deviation memo snapshot itself is forbidden as its own applicability basis.

### Applicability states

The reviewer records:

- `APPLIES`;
- `DOES_NOT_APPLY`; or
- `UNRESOLVED`.

Resolved applicability is prohibited while deviation currentness remains `UNRESOLVED`.

An `UNRESOLVED` deviation may be attached only while the buyer-facing assumption itself remains unresolved (`UNPROVEN` or `SOURCE_LIMITED`). This prevents a visibly unresolved rule question from hiding underneath a supposedly resolved assumption.

### Superseded deviations

A superseded memo is not automatically irrelevant.

If a reviewer concludes that a `SUPERSEDED` deviation still `APPLIES`, the applicability basis must be explicit solicitation or amendment text. A generic deviation review cannot resurrect a superseded memo.

### Native Decision Evidence representation

The reviewed memo becomes a normal content-addressed Decision Evidence rule version:

- namespace: `CLASS_DEVIATION`;
- agency: reviewed agency;
- citation: retained public memo filename;
- edition identity: captured PDF SHA-256 prefix;
- text passage: exact reviewed memo passage;
- effective interval: only when separately reviewed;
- revision reference: captured artifact receipt.

The rule version and reviewed memo snapshot are added to the existing Decision Evidence trace, then linked to the specific assumption with:

- family ID;
- applicability;
- basis class;
- exact pursuit-specific basis passage;
- rationale;
- reviewer identity and time.

No parallel deviation-only buyer report is created. FAR, DFARS and CLASS_DEVIATION evidence appear through the same inspectable rule-link surface.

### Fail-closed history

If the same deviation rule version already has a different Decision Evidence link, CaptureBrief refuses to rewrite it in place. The reviewer must preserve the prior decision and create a new decision version.

A packet-level applicability record also does not count as complete if its corresponding Decision Evidence rule/link has been removed or altered.

### Assumption state remains independent

This transition explicitly records:

- `human_reviewed = true`;
- `applicability_authoritative = false`;
- `assumption_state_changed = false`;
- `can_auto_apply = false`.

The rule review supplies evidence. It does not autonomously turn `UNPROVEN` into `SUPPORTED`, flip GO/NO-GO, or make a legal determination.

### Work queue

Once deviation authority currentness is resolved and an assumption Decision Evidence trace exists, the queue opens:

`deviation-applicability:<id>`

as P0 `HUMAN_REVIEW`.

It closes only when both the packet-level review and the exact Decision Evidence rule link remain intact.

### CLI

Apply assumption-specific deviation applicability:

    python -m capturebrief_core.rule_cli case-review-deviation-applicability \
      case-with-deviation-authority.json deviation-applicability-review.json \
      -o case-with-deviation-decision-evidence.json

This completes the technical deviation-evidence chain. Remaining product validation is commercial: run the complete chain on real public solicitations and measure whether the evidence changes or closes a buyer's actual gate assumptions.

## v0.25 — Structured Deviation Authority Review

v0.24 proved the exact public PDF bytes behind a class-deviation candidate. v0.25 turns the next analyst step into a deterministic evidence transition rather than a free-text note.

The path is now:

`captured PDF SHA-256 -> reviewed text bound to those bytes -> exact memo passage -> reviewed effective-date passage -> separate currentness basis -> content-addressed authority review -> later pursuit-specific applicability`

### Reviewed text bound to captured bytes

Before authority review, a named reviewer prepares text from the captured public PDF.

The preparation:

- requires a current PDF capture receipt;
- binds the source-manifest row to the captured PDF SHA-256;
- creates a content-addressed `DEVIATION` text snapshot;
- records reviewer, preparation time and a mapping note;
- refuses preparation before the PDF observation time;
- leaves currentness, effective date and applicability unresolved.

The reviewed text does not become authoritative merely because it was extracted successfully.

### Exact memo passage

Every authority review requires an exact line-bounded memo passage with a human-readable locator.

The passage is generated from the retained reviewed snapshot, so the reviewer cannot supply a quote that differs from the preserved text.

### Effective-date claims require evidence

A reviewer may record `effective_from` / `effective_until` only with an exact passage from the captured memo snapshot.

Conversely, an effective-date passage cannot create an implicit date. The explicit reviewed date and the supporting passage must both exist.

### Currentness cannot self-certify

A deviation memo may describe its own issue/effective date, but it cannot prove that no later action superseded it.

Therefore `CURRENT` or `SUPERSEDED` requires a **separate retained public Decision Evidence snapshot** as currentness basis.

CaptureBrief verifies that the basis snapshot:

- is content-addressed correctly;
- has a valid retained-text SHA-256;
- binds to a retained public source object;
- was observed no later than the authority review;
- is not the deviation memo snapshot itself.

A `SUPERSEDED` decision also requires an explicit reference to the superseding source/artifact.

Without this evidence, currentness must remain `UNRESOLVED`.

### Human-reviewed state is not automatic applicability

The authority review records:

- `CURRENT`, `SUPERSEDED`, or `UNRESOLVED`;
- exact memo passage;
- reviewed effective interval when established;
- exact effective-date passage;
- exact separate currentness basis when resolved;
- reviewer identity and review time;
- superseding reference when applicable.

It explicitly retains:

- `currentness_authoritative = false`;
- `effective_date_authoritative = false`;
- `applicability = UNRESOLVED`;
- `applicability_authoritative = false`;
- `assumption_state_changed = false`;
- `can_auto_apply = false`.

That means the structured review can improve the evidence without silently changing the customer's bid decision.

### Operator queue

The positive-candidate path is now specific rather than duplicative:

1. `deviation-bytes:<id>` — capture/hash official PDF;
2. `deviation-text:<id>` — human-reviewed extraction bound to PDF SHA;
3. `deviation-authority:<id>` — review memo passage/effective/current/supersession;
4. `deviation-currentness:<id>` — remains open if currentness is still unresolved.

The old aggregate candidate-review task is retained only for **zero-candidate searches**, where bounded-corpus absence still needs human handling.

### CLI

Prepare reviewed text:

    python -m capturebrief_core.rule_cli case-prepare-deviation-text \
      case-with-deviation-bytes.json <DEVSRC:...> memo.txt \
      --prepared-by "CaptureBrief reviewer" \
      --prepared-at 2026-09-21T19:00:00Z \
      --mapping-note "Reviewed extraction against captured official PDF." \
      -o case-with-deviation-text.json

Apply a structured authority review:

    python -m capturebrief_core.rule_cli case-review-deviation-authority \
      case-with-deviation-text.json deviation-authority-review.json \
      -o case-with-deviation-authority.json

The next boundary is to bridge a reviewed deviation authority record into the existing Decision Evidence rule/applicability model for a specific bid assumption without weakening its separate pursuit-specific basis requirement.

## v0.24 — Official Deviation Artifact Capture

v0.23 proved which pinned deviation index was inspected and surfaced bounded agency/FAR-Part candidates. v0.24 advances one authority layer deeper: it captures the **actual public acquisition.gov PDF bytes** behind a candidate and gives those bytes their own immutable identity.

The flow is now:

`pinned candidate index -> candidate URL -> exact official PDF capture -> PDF SHA-256 -> human current/effective/supersession review -> pursuit-specific applicability -> Decision Evidence`

### Exact candidate binding

CaptureBrief will fetch a deviation artifact only when:

- the case contains a current content-addressed deviation candidate proposal;
- the requested `deviation_source_id` is in that proposal;
- its source URL is HTTPS on `acquisition.gov` / `www.acquisition.gov`;
- the candidate's 16-character `url_hash` equals the first 16 hexadecimal characters of SHA-256(source URL).

The deviation-manifest parser now validates that URL-hash semantic directly. A syntactically plausible but incorrect 16-character hash is rejected.

### Official PDF capture

For an eligible candidate the capture path:

- uses exactly the candidate URL;
- accepts no caller-supplied replacement URL;
- rejects redirects/final-URL changes;
- permits no embedded credentials, query authority, or fragment;
- caps the response at 25 MiB;
- requires a PDF file signature;
- records observation time, exact final URL, actual byte length and SHA-256;
- records whether the live byte length equals the historical index's declared size.

The captured PDF receipt remains bound to the exact candidate proposal SHA-256.

### Size agreement is not byte identity

The pinned deviation manifest records a declared PDF size but does not provide a cryptographic PDF digest.

Therefore CaptureBrief explicitly records:

`index_byte_identity_proven = false`

even when the live official PDF length equals the index's declared size.

A size mismatch is also preserved rather than silently rejected or normalized away. It can indicate a changed live artifact and therefore requires review.

### Append-only observations

Artifact receipts are append-only. Re-running the exact same observation receipt is idempotent; a later distinct capture is preserved as another observation rather than overwriting the earlier bytes' identity.

For each current candidate, CaptureBrief derives the latest valid capture only when the receipt still binds to the current proposal and candidate metadata.

### Operator sequencing

Before capture, the work queue opens one P0:

`deviation-bytes:<deviation_source_id>`

per uncaptured candidate as `AUTOMATED_APPROVED_SOURCE`.

The human deviation review remains open but is P1 until every candidate PDF has been captured. Once the bytes exist, the human authority/applicability review becomes P0.

A zero-candidate proposal remains P0 human review because there are no bytes to capture and corpus absence is not authoritative.

### Still unresolved after capture

A captured official PDF proves:

> **these exact public bytes were observed at this URL at this time.**

It still does not prove:

- the memo remains current;
- its effective date;
- whether another memo supersedes it;
- that it applies to this solicitation;
- that it changes a specific bid assumption.

Those are separate reviewed claims.

### CLI

Capture a candidate and attach its receipt to the case:

    python -m capturebrief_core.rule_cli case-capture-deviation-artifact \
      case-with-deviation-candidates.json <DEVSRC:...> \
      --observed-at 2026-09-21T18:30:00Z \
      --artifact-output deviation.pdf \
      --receipt-output deviation-receipt.json \
      -o case-with-deviation-bytes.json

The next authority step is structured human review of the captured memo's effective/current/supersession state and exact supporting passage before promotion into Decision Evidence.

## v0.23 — Pinned Class-Deviation Discovery

The new deviation path is:

`pinned corpus revision -> content-addressed manifest receipt -> explicit agency + FAR Part filter -> candidate artifacts -> HUMAN_REVIEW -> underlying official artifact -> reviewed currentness/effective/supersession -> Decision Evidence applicability`

### Immutable discovery source

CaptureBrief retrieves the class-deviation manifest only from the exact `acqagent/rfo-deviations` revision pinned in `RULE-SOURCE-CATALOG.json`.

The sync contract:

- constructs the raw GitHub URL internally;
- requires a full immutable 40-character revision;
- accepts no caller-supplied download URL;
- rejects redirect/final-URL changes;
- requires `raw.githubusercontent.com` over HTTPS;
- permits no URL credentials/query/fragment;
- caps the manifest at 2 MiB;
- requires UTF-8;
- hashes the exact downloaded bytes;
- verifies the parsed manifest digest against those bytes;
- emits a content-addressed fetch receipt.

This proves which candidate index was inspected. It does **not** prove any deviation is current or applicable.

### Real-corpus sentinel handling

The pinned corpus uses `part_number = -1` for multipart/unparsed material and also contains `part_number = 0` rows. The parser now preserves both values rather than rejecting the real corpus.

A pursuit candidate query remains deliberately narrower: the reviewer must request explicit FAR Parts 1–53. Sentinel rows do not silently attach themselves to a pursuit.

### Agency + Part candidate proposal

A candidate proposal requires:

- an explicit agency;
- one or more explicit FAR Parts;
- a named proposer;
- timezone-aware proposal time;
- a manifest with a valid pinned fetch receipt.

The proposal deduplicates one PDF that appears under multiple matched FAR Parts while preserving all matched parts.

Every returned artifact remains:

- `CANDIDATE_ONLY`;
- effective date `UNKNOWN`;
- currentness `UNRESOLVED`;
- applicability `UNRESOLVED`;
- `can_auto_apply = false`.

### Absence is not authority

A zero-candidate result is **not** evidence that no deviation exists.

The manifest itself documents source-link failures and a bounded civilian-agency collection surface. CaptureBrief therefore keeps `review_required = true` even when the pinned corpus has no matching agency/Part row.

That preserves the same core invariant used elsewhere in CaptureBrief:

**a failed, incomplete, bounded, or non-authoritative observation cannot become a clean negative.**

### Human review boundary

When candidates exist—or when the candidate search returns zero—the operator queue opens:

`deviations:review-candidates`

as a P0 `HUMAN_REVIEW` task.

Before a deviation can affect a bid assumption, a reviewer must still:

1. inspect/retain the underlying public deviation artifact;
2. bind it to immutable bytes;
3. establish effective date/currentness/supersession from appropriate public authority;
4. identify the pursuit-specific incorporation/applicability basis;
5. link that reviewed evidence into Decision Evidence.

Corpus metadata alone can never perform those steps.

### CLI

Sync the pinned candidate index:

    python -m capturebrief_core.rule_cli sync-deviation-manifest \
      --observed-at 2026-09-21T18:00:00Z \
      --manifest-output deviation-manifest.json \
      --receipt-output deviation-manifest-receipt.json

Attach a bounded candidate proposal:

    python -m capturebrief_core.rule_cli case-propose-deviations \
      case.json deviation-manifest.json deviation-manifest-receipt.json \
      --agency DHS --part 39 --part 52 \
      --proposed-by "CaptureBrief reviewer" \
      --proposed-at 2026-09-21T18:05:00Z \
      -o case-with-deviation-candidates.json

The next product boundary is exact underlying deviation-PDF capture/hash plus reviewed effective/currentness/supersession evidence. v0.23 deliberately stops before that authority claim.

CaptureBrief is a human-supervised, public-source Pursuit QA second pass. v0.19 completes the rule-to-assumption evidence chain: a human reviewer binds the exact prepared rule edition/passage to one specific bid assumption and records APPLIES / DOES_NOT_APPLY / UNRESOLVED using a separate exact solicitation/amendment/context passage as the pursuit-specific basis.

## v0.19 — Rule-to-Assumption Applicability Review

CaptureBrief now has an explicit final human transition from prepared rule evidence into the buyer's Decision Evidence trace.

The full path is:

`solicitation citation -> pinned official rule source -> human edition selection -> exact official rule paragraph -> human applicability review -> specific bid assumption`

### Separate rule text from applicability basis

A rule's own text cannot prove that the rule governs a particular solicitation.

For a resolved `APPLIES` or `DOES_NOT_APPLY` decision, the reviewer must supply a **different exact Decision Evidence passage** from retained:

- solicitation text;
- amendment text; or
- other pursuit-specific context.

That basis passage must:
- reference an existing content-addressed trace snapshot;
- have a valid line range;
- match the retained quote exactly;
- include a human-readable locator;
- not be the prepared rule snapshot itself.

This creates two inspectable evidence planes:

1. **What does the exact rule edition say?**
2. **Why does the reviewer believe that edition applies—or does not apply—to this pursuit?**

### Human applicability states

For each prepared rule occurrence the reviewer records:

- affected `assumption_id`;
- `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED`;
- basis class;
- rationale;
- rule-scope rationale;
- named reviewer;
- timezone-aware review time;
- exact pursuit-specific basis passage when resolved.

Supported basis classes:

- `INCORPORATED_EDITION`;
- `SOLICITATION_TEXT`;
- `AMENDMENT_TEXT`;
- `EFFECTIVE_DATE_REVIEW`;
- `DEVIATION_REVIEW`;
- `UNRESOLVED`.

An `UNRESOLVED` decision must stay `UNRESOLVED`; it cannot carry a resolved-looking basis.

For `INCORPORATED_EDITION`, the named incorporated edition must exactly equal the prepared rule edition. A reviewer cannot silently substitute a newer edition.

### Human-reviewed, not legal authority

The applicability conclusion is preserved as a named human QA review, not as an autonomous or legally authoritative system fact.

The record explicitly keeps:

- `human_reviewed = true`;
- `applicability_authoritative = false`;
- `can_auto_apply = false`;
- `assumption_state_changed = false`.

The transition **does not** change the buyer-facing assumption's evidence state or finding. Those remain separately reviewed Decision Evidence fields.

### Decision Evidence mutation boundary

The transition may add:

- the prepared rule snapshot to `decision_trace.snapshots`;
- the prepared rule version to `decision_trace.rule_versions`;
- one exact rule link to the named assumption review;
- `rule_scope = REQUIRED` with the reviewer-supplied scope rationale.

It does not rewrite a different existing link for the same rule version. If an already-issued link differs, CaptureBrief fails and requires a new preserved decision version rather than silently rewriting history.

### Buyer-facing report

The expandable evidence trail now shows:

- FAR/DFARS namespace + citation;
- exact rule edition;
- `APPLIES` / `DOES_NOT_APPLY` / `UNRESOLVED`;
- applicability basis type;
- incorporated edition when relevant;
- reviewer rationale;
- reviewer identity + time;
- pursuit-specific source locator;
- exact pursuit-specific basis passage.

The short finding remains on top; this deeper rule history stays inspectable underneath.

### Work queue

Once exact rule evidence has been prepared and the case has an assumption Decision Evidence trace, the queue opens:

`rules:review-applicability`

as a P0 `HUMAN_REVIEW` task.

The task does not appear before the Decision Evidence trace/assumption reviews exist, because there is nothing safe to bind the rule to yet.

### CLI

Review example:

    {
      "reviewed_by": "CaptureBrief reviewer",
      "reviewed_at": "2026-09-21T17:15:00Z",
      "decisions": [
        {
          "occurrence_id": "RULEMENTION:...",
          "assumption_id": "A-1",
          "applicability": "APPLIES",
          "basis": "INCORPORATED_EDITION",
          "incorporated_edition": "Nov 2021",
          "rationale": "The solicitation explicitly incorporates this edition.",
          "scope_rationale": "This assumption depends on the cited safeguarding requirement.",
          "basis_passage": {
            "snapshot_id": "SNAP:...",
            "line_start": 42,
            "line_end": 42,
            "locator": "Section I, clause list",
            "quote": "..."
          }
        }
      ]
    }

Apply:

    python -m capturebrief_core.rule_cli case-review-rule-applicability \
      case-with-prepared-rule-evidence.json applicability-review.json \
      -o updated-case.json \
      --result-output applicability-transition.json

After this stage, the buyer can inspect both the exact official rule version and the separate source passage supporting the reviewer’s pursuit-specific applicability conclusion.

## v0.18 — Exact Rule Evidence Preparation

A selected rule edition is now converted into exact trace-ready evidence before it can support an assumption review.

The controlled state transition is:

`human TRACK_VERSION -> exact paragraph selection -> prepared source/snapshot/rule-version -> Decision Evidence applicability review`

### Exact paragraph selection is human

Once the v0.14 human rule review contains one or more `TRACK_VERSION` decisions, the work queue opens:

`rules:prepare-evidence`

with:

- priority `P0`;
- actor `HUMAN_REVIEW`;
- `can_auto_execute = false`;
- `can_auto_bind_assumption = false`;
- `can_auto_apply = false`.

The reviewer selects one exact paragraph locator from each selected pinned rule source.

CaptureBrief refuses:
- unknown paragraph locators;
- duplicate preparation for one occurrence;
- missing preparation for any tracked occurrence;
- a selected rule source that is no longer in the local registry;
- selected-rule metadata that no longer matches the content-addressed registry record.

### Trace-ready objects

For each selected occurrence CaptureBrief prepares:

1. a deterministic public source-manifest row;
2. a content-addressed rule-text snapshot;
3. an exact line-bounded passage with the selected official paragraph locator;
4. a content-addressed Decision Evidence `rule_version` object whose `revision_ref` points back to the exact `RULESRC:...` record.

The preparation retains:

- occurrence ID;
- citation;
- human rule-version review reason;
- exact selected `rule_source_id`;
- paragraph locator and paragraph text SHA-256;
- source row;
- source snapshot;
- exact passage;
- prepared rule-version object.

### No assumption binding or applicability

Preparation deliberately stops before the legal/procurement judgment.

Every prepared item contains:

- `applicability = UNRESOLVED`;
- `applicability_authoritative = false`;
- `bound_assumption_id = null`;
- `can_auto_bind_assumption = false`;
- `can_auto_apply = false`.

The preparation step does **not** create a Decision Evidence review, attach the rule to an assumption, or change any buyer-facing evidence state.

The ordinary `trace:...` work remains open until a human later cites the solicitation-specific incorporation/effective/applicability basis.

### Review binding and history

The complete preparation is content-addressed and bound to the current human `rule_candidate_review.review_sha256`.

If the selected-version review changes, the old preparation is no longer current.

When a new preparation replaces an older one, the older preparation is retained in `packet.rule_evidence_preparation_history`.

Prepared public rule sources are added to the case source manifest under a deterministic source ID derived from the content-addressed `RULESRC` identifier. A conflicting existing source ID is a hard failure.

### CLI

Preparation input:

    {
      "prepared_by": "CaptureBrief reviewer",
      "prepared_at": "2026-09-21T17:00:00Z",
      "selections": [
        {
          "occurrence_id": "RULEMENTION:...",
          "paragraph_locator": "p-FAR_52_204_21_1"
        }
      ]
    }

Apply:

    python -m capturebrief_core.rule_cli case-prepare-rule-evidence \
      rules.sqlite case-with-rule-review.json rule-evidence-preparation.json \
      -o case-with-prepared-rule-evidence.json \
      --result-output rule-evidence-transition.json

The output is ready for the later Decision Evidence assumption/applicability review, but it is not itself a releasable applicability decision.

## v0.17 — Missing Rule Auto-Sync

A missing local FAR/DFARS rule version is now an actionable source-acquisition state rather than a dead-end human lookup.

When a current citation proposal contains an occurrence with `candidate_count = 0` and an explicit FAR/DFARS namespace, CaptureBrief can create:

`rules:sync-missing-pinned-sources`

with:

- priority `P0`;
- actor `AUTOMATED_APPROVED_SOURCE`;
- `can_auto_execute = true`;
- `can_auto_apply = false`.

The ordinary human version-review task remains P1.

This ordering means CaptureBrief should acquire the exact approved public source before asking a reviewer to choose among versions, while unrelated P0 case blockers may still coexist.

### Narrow automatic scope

Only missing references with an explicit/recognized `FAR` or `DFARS` namespace are eligible for this automatic source sync.

The mapping is fixed:

- FAR → `gsa-far-dita`;
- DFARS → `gsa-dfars-dita`.

Unknown namespaces and non-GSA deviation/supplement candidates remain manual/reviewed workflows.

Duplicate occurrences of the same missing namespace/citation pair are synced once.

### State transition

The controlled flow is:

`citation proposal with missing version -> exact pinned GSA sync -> registry insert -> proposal re-match -> human version review`

After all required syncs succeed:

1. the old proposal is copied to `packet.rule_candidate_proposal_history`;
2. the active proposal is rebuilt against the updated registry;
3. the refreshed proposal records `refreshed_from_proposal_sha256`;
4. if an old human `rule_candidate_review` exists, it is moved to `rule_candidate_review_history` and removed from active state;
5. the human version-review task reopens against the new candidate set.

This prevents an old `UNRESOLVED` or previous candidate choice from surviving newly acquired official evidence.

### Partial failure behavior

The case object is not mutated until every requested source sync succeeds.

If a later network fetch fails after an earlier registry insert:

- the original case remains unchanged;
- the registry may contain the successfully fetched content-addressed rule;
- rerunning is safe because the registry is idempotent.

This is deliberately different from pretending the multi-source operation is globally transactional.

### Proposal history and no automatic applicability

Proposal refresh changes lookup evidence, not the bid decision.

Even after successful source acquisition:

- `can_auto_apply = false`;
- no assumption evidence state changes;
- no controlling edition is chosen automatically;
- applicability stays a later human Decision Evidence claim.

### CLI

    python -m capturebrief_core.rule_cli case-sync-missing-rules \
      rules.sqlite case-with-rule-candidates.json \
      --catalog RULE-SOURCE-CATALOG.json \
      --observed-at 2026-09-21T17:00:00Z \
      -o refreshed-case.json \
      --result-output rule-sync-transition.json

The refreshed case must still pass human rule-version review and Decision Evidence applicability review before rule-dependent findings can be released.

## v0.16 — Pinned Rule Source Sync

CaptureBrief can now fetch and register a specific FAR/DFARS topic from the approved source catalog in one controlled operation.

Example:

    python -m capturebrief_core.rule_cli sync-dita rules.sqlite \
      --source-id gsa-far-dita \
      --citation 52.204-21 \
      --observed-at 2026-09-21T17:00:00Z \
      --receipt-output fetch-receipt.json \
      --record-output rule-record.json

### No caller-supplied rule URL

The sync command accepts:
- approved source ID;
- citation;
- observation time.

It does **not** accept a download URL or Git branch.

The URL is constructed internally from `RULE-SOURCE-CATALOG.json`:

`raw.githubusercontent.com/<approved-GSA-repo>/<exact-40-char-revision>/dita/<citation>.dita`

Only the pinned FAR and DFARS GSA repositories are accepted on this path.

### Immutable revision requirement

The catalog revision must be a full lowercase 40-character Git SHA.

Values such as:
- `main`;
- `master`;
- tags;
- shortened SHAs;
- arbitrary repository names

are rejected before network access.

### Retrieval controls

The pinned sync:

- uses HTTPS;
- uses the allowlisted `raw.githubusercontent.com` host;
- permits no credentials in the URL;
- permits no query/fragment authority;
- rejects redirect/final-URL changes;
- caps a DITA response at 5 MiB;
- requires UTF-8;
- verifies that the citation inside the fetched DITA equals the citation requested.

A fetch therefore cannot silently turn `52.204-21` into another rule.

### Fetch receipt

Each successful retrieval emits a content-addressed receipt containing:

- source ID;
- citation/namespace;
- repository;
- exact revision;
- exact DITA path;
- requested and final raw URL;
- approved catalog SHA-256;
- observation time;
- byte length;
- source SHA-256;
- resulting `rule_source_id`;
- explicit `mutable_ref_used = false`;
- explicit `caller_url_used = false`;
- explicit `credentials_used = false`.

The receipt byte hash must agree with the normalized rule record's original-source hash before insertion.

### Idempotent local registry

Syncing the same pinned citation/source snapshot twice is idempotent:

- first run → `INSERTED`;
- same content-addressed rule source again → `EXISTS`.

A source/version change produces a different content-addressed rule record rather than overwriting prior history.

### Still human-reviewed

A successful pinned sync proves:

**this exact public source snapshot was retrieved and normalized.**

It does not prove:
- the rule applies to the solicitation;
- the edition was incorporated;
- a deviation modifies it;
- a bid assumption should change.

Those remain v0.13/v0.14/v0.11 human-review stages.

## v0.15 — Official Rule Ingestion

The FAR/DFARS parser now matches the actual shape of GSA's machine-readable DITA rather than only simplified XML fixtures.

### Known external DITA declaration

Official GSA FAR/DFARS topics include the standard OASIS DITA declaration:

    <!DOCTYPE dita
      PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">

CaptureBrief now accepts **only that exact known declaration** for this parser path. It removes the declaration before local `ElementTree` parsing and does not resolve or fetch the external DTD.

The parser still fails closed on:

- any XML `ENTITY` declaration;
- an arbitrary `SYSTEM` DTD;
- an unrecognized `DOCTYPE`;
- multiple/extra DTD declarations.

The original unsanitized DITA bytes/text remain the material hashed by `source_sha256`; stripping occurs only in the local parsing copy.

### Clause/provision edition from the rule text

For clause/provision topics, GSA DITA commonly includes the operative month/year in the rule heading, for example:

    Basic Safeguarding of Covered Contractor Information Systems (Nov 2021)

CaptureBrief extracts that embedded month/year when present.

The normalized rule record now distinguishes:

- `edition` — the embedded rule-text edition when available;
- `edition_basis = EMBEDDED_RULE_TEXT`;
- `embedded_edition_locator` — the source paragraph containing the edition;
- `source_snapshot_label` — an optional repository/publication snapshot label supplied by the operator;
- `source_revision` — exact Git provenance.

An operator/source-snapshot label can no longer silently replace an embedded clause edition. If the DITA says `Nov 2021` and the repository snapshot is labeled `FAC 2026-01 snapshot`, both facts are preserved separately and the rule edition remains `Nov 2021`.

If the DITA contains no embedded rule edition, an explicit source/edition label may still be supplied as a fallback and is marked `OPERATOR_SOURCE_LABEL`.

### Still not applicability

An embedded rule edition is stronger version evidence than a manually typed edition label, but it still does **not** prove:

- solicitation incorporation;
- effective applicability to the acquisition;
- agency-deviation applicability;
- whether an amendment overrides or modifies the rule.

Those remain human-reviewed Decision Evidence questions.

### Regression boundary

CI now includes an official-shaped GSA DITA fixture with the standard multiline OASIS declaration and embedded clause edition, plus negative fixtures for malicious/internal entities and arbitrary external DTDs.

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


## v0.20 — Inspectable source-version deltas

Decision Evidence now makes source-version changes inspectable instead of reporting only that a change occurred.

For every retained `AMENDS`, `CORRECTS`, or `SUPERSEDES` relation, the trace can carry:

- the exact from-version source metadata and document SHA-256;
- the exact to-version source metadata and document SHA-256;
- an exact before passage + locator;
- an exact after passage + locator;
- the concise reviewer change summary.

The trace evaluator validates that both passages belong to their declared source versions. A one-sided delta fails closed. Older traces that retained only the relation/summary remain compatible, but emit `TRACE_CHANGE_PASSAGES_MISSING` as a warning so the buyer can distinguish “version relation recorded” from “exact textual delta captured.”

The HTML and Markdown buyer reports now show the two source versions side by side / sequentially with their exact passages and hashes.

This strengthens the product promise from:

> a source changed

to:

> this exact text in this retained source version changed to this exact text in that retained source version.

The change remains evidence for human Pursuit QA; it does not automatically alter rule applicability or the customer's bid decision.


## v0.21 — Release-gated buyer delivery bundle

A completed case can now be turned into the actual customer delivery in one command:

    python -m capturebrief_core.trace_cli bundle case.json -o capturebrief-delivery.zip

The bundle builder refuses to operate unless the case passes the full product audit as `READY_FOR_HUMAN_RELEASE`, requires `decision_trace_required = true`, and requires a complete non-synthetic Decision Evidence trace.

The delivery contains:

1. `brief.md` — the concise CaptureBrief pursuit handoff;
2. `decision-evidence.md` — the exact evidence report;
3. `decision-evidence.html` — the buyer-readable expandable evidence report;
4. `decision-summary.json` — machine-readable reviewed conclusions;
5. `source-version-manifest.json` — public snapshot/rule identities, versions, URLs and hashes without raw source text;
6. `delivery-manifest.json` — SHA-256 and byte length for every delivered file.

The ZIP normalizes entry timestamps and ordering, making the same case at the same declared generation time byte-deterministic. The resulting ZIP SHA-256 can therefore be retained as the delivery receipt.

The bundle deliberately excludes the raw internal case object and customer intake metadata. It also does not package restricted source bytes. A trace tamper, missing evidence, synthetic demonstration, or other release blocker prevents bundle creation rather than generating a partially trusted customer artifact.

CI now exercises the complete release path against a dedicated release-ready Decision Evidence fixture.


## v0.22 — Targeted 14-day watch baseline

The 14-day watch is now an explicit product artifact rather than a generic monitoring promise.

Every release-ready delivery bundle includes a content-addressed `watch-baseline.json` containing only the minimum public/evidence state needed to detect whether a delivered assumption should be reopened:

- current-action identity;
- complete history-set hash;
- latest action-manifest fingerprints;
- artifact/resource byte state and hashes;
- reference closure state;
- source-version identities;
- rule-version identities;
- assumption dependency/reopen keys.

It excludes source text, customer intake fields, and the raw internal case.

The comparison path:

    python -m capturebrief_core.trace_cli watch-check \
      watch-baseline.json refreshed-case.json -o watch-observation.json

produces explicit events and a targeted `reopened_assumptions` list. It never rewrites the previous finding, never automatically changes rule applicability, and always records `automatic_decision_change = false`.

An artifact/byte change keeps the precise `ARTIFACT:<id>` event while carrying the existing `RESOURCE:<id>` trigger alias so cases created under the prior change-watch convention continue to reopen correctly.

The watch observation is hash-bound and also surfaces Decision Evidence integrity failures. This turns the paid 14-day watch into:

`delivered evidence state -> fresh approved observations -> explicit delta -> only affected assumptions reopened -> human review`

rather than “send an alert when something on SAM changes.”


## v0.24 — Evidence-grounded commercial outcome ledger

CaptureBrief now has an append-only commercial-learning plane instead of relying on informal notes to decide whether the founding pilot should expand.

Outcome evidence is event-sourced through `capturebrief_core/outcomes.py` and the existing hash-chained evidence ledger.

Supported events:

- `PAYMENT` — current paid/unpaid/refunded/unknown state; paid/refunded events require an opaque evidence reference;
- `DELIVERY` — timezone-aware work-start and delivery timestamps plus delivery evidence;
- `FEEDBACK` — explicit usefulness, action effect, source-limited state, finding classes and buyer-feedback evidence reference;
- `RETRACTION` — critical/noncritical correction with a controlled reason and evidence reference;
- `REPEAT_REQUEST` — explicit requested-repeat / would-repeat / no-repeat state.

The schema intentionally rejects customer identity/contact fields, free-text notes and unsupported economic claims such as ROI, PWin uplift, proposal savings or revenue uplift.

Operator commands:

    python -m capturebrief_core.cli outcome-validate outcome.json

    python -m capturebrief_core.cli outcome-append outcomes.jsonl outcome.json

    python -m capturebrief_core.cli outcome-summary outcomes.jsonl

The append path refuses an invalid existing hash chain.

The summary derives only observable commercial evidence:

- distinct engagements;
- current paid engagement count;
- recorded collected amount where provided;
- delivery turnaround count and distribution;
- explicit usefulness/action-effect labels;
- source-limited cases;
- retractions;
- explicit repeat requests;
- finding-class counts.

Refunded engagements are not counted as currently paid.

The commercial-proof summary exposes the factual gates from Business Model v7:

- at least 3 current paid engagements;
- at least 1 explicit repeat request;
- at least 1 changed action or explicitly closed costly uncertainty;
- turnaround evidence present.

It never automatically changes price, creates a subscription, claims product-market fit, or decides whether turnaround/retraction levels are acceptable. Those remain human commercial decisions.

See `OUTCOME-LEDGER.md` and `BUSINESS-MODEL-v7.md`.


## v0.28 — Fulfillment Effort Evidence

CaptureBrief now measures the human work required to produce the evidence product, not only elapsed delivery time.

A privacy-safe commercial outcome event can record whole operator minutes against a controlled fulfillment stage:

- `INTAKE_SCOPE`
- `HISTORY_CURRENT`
- `PACKET_BYTES`
- `REFERENCE_REVIEW`
- `ASSUMPTION_REVIEW`
- `RULE_REVIEW`
- `DEVIATION_REVIEW`
- `WATCH`
- `DELIVERY`
- `CUSTOMER_COMMS`
- `OTHER`

Each `EFFORT` event requires an opaque evidence reference and is append-only. It contains no buyer identity, free-text notes, or unsupported ROI claims.

Operators can record effort directly:

    python -m capturebrief_core.cli outcome-effort \
      outcomes.jsonl CB-CASE <CASE_SHA256> ASSUMPTION_REVIEW 35 timer:CB-CASE:review-1 \
      --event-at 2026-09-21T18:30:00Z

The commercial summary now reports:

- engagement-level effort hours;
- total/median/min/max recorded labor;
- minutes by fulfillment stage;
- paid-engagement effort coverage;
- collected cents per recorded effort hour by currency when payment amount and labor are both explicitly evidenced.

This does not auto-reprice the product or decide whether labor is acceptable. It prevents the founding $149 offer from being judged solely by sales or calendar turnaround while hidden founder labor remains unmeasured.

The pre-expansion evidence surface now distinguishes:

`buyers paid`

from:

`buyers paid + delivery was useful + labor was measured + economics can be reviewed`.

### Fulfillment cockpit

The existing fail-closed work queue can now be converted into one operator plan:

    python -m capturebrief_core.cli fulfillment-plan case.json -o fulfillment-plan.json

The plan does not create evidence or make procurement/applicability decisions. It reorganizes existing work into:

- current release state and blocker codes;
- P0 safe-automation batch;
- P0 human/hybrid review batch;
- later P1/P2 work;
- one deterministic next task;
- an effort stage for every task so actual labor can be timed consistently.

When a case is already releasable and the work queue is empty, the plan returns:

`READY_TO_BUILD_DELIVERY`

The operating loop is therefore:

`plan -> clear approved automation -> perform named human review -> log actual effort -> re-plan -> release-gated bundle -> commercial outcome events`

This is intentionally an operator cockpit, not an autonomous capture agent.

The next optimization target should be selected from measured stage minutes rather than intuition.
