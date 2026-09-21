# CaptureBrief Rule Sources

Updated: September 21, 2026

CaptureBrief uses public rule sources to support a human-reviewed Pursuit QA case. The rule-source system preserves exact versions and evidence lineage; it does not autonomously decide procurement/legal applicability.

## Source roles

### GSA FAR / DFARS DITA
Role: **first-party machine-readable rule text snapshot**.

CaptureBrief may normalize a pinned FAR/DFARS DITA topic into a content-addressed rule source when:
- the repository is one of the approved GSA sources in `RULE-SOURCE-CATALOG.json`;
- the full Git revision is retained;
- the exact DITA path and source URL are retained;
- the original text SHA-256 and normalized text SHA-256 are both retained.

A Git revision proves which public source snapshot was inspected. It does not, by itself, prove:
- a rule effective date;
- that the rule was incorporated into a particular solicitation;
- that a clause/provision is applicable;
- that a later publication supersedes a solicitation-pinned edition.

### Agency deviation manifest
Role: **discovery/index evidence**.

The pinned `acqagent/rfo-deviations` manifest can identify agency/Part-specific public deviation artifacts. It cannot, by itself, establish:
- effective date;
- currentness;
- supersession;
- solicitation applicability.

A candidate deviation remains a candidate until the underlying public artifact and solicitation-specific basis are reviewed.

### FAR collector implementation
Role: **collection/reference implementation**.

`acqagent/far-collector` can inform collection and normalization design. The collector is not itself the controlling legal source for a rule. Any rule assertion must resolve to an underlying public authority artifact retained in the case evidence.

## Authority hierarchy

CaptureBrief should prefer, in order:

1. solicitation/amendment text that explicitly incorporates or modifies an edition/rule;
2. a retained official rule/deviation artifact with reviewed effective/currentness evidence;
3. first-party machine-readable publication text;
4. collection/index metadata used only to locate stronger evidence.

A weaker layer cannot silently override a stronger solicitation-specific source.

## Official GSA DITA parsing

GSA FAR/DFARS DITA uses the standard external OASIS declaration:

```xml
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
```

The CaptureBrief parser allows only this exact declaration on the GSA DITA path. It removes the declaration from the local parse copy and never resolves the external DTD.

It continues to reject:
- XML entity declarations;
- arbitrary `SYSTEM` DTDs;
- unrecognized or multiple `DOCTYPE` declarations.

The retained source SHA-256 is computed over the original source, not the sanitized parse copy.

For clause/provision topics, CaptureBrief also reads an embedded month/year edition from the official heading when available. That rule-text edition is kept separate from the Git revision and any repository/publication snapshot label.

Example:
- source revision: exact GSA Git commit;
- source snapshot label: `FAC 2026-01 snapshot`;
- embedded rule edition: `Nov 2021`.

The embedded rule edition is preferred for the rule record; the source snapshot label remains separate provenance. Neither one establishes solicitation applicability by itself.

## Pinned public rule retrieval

The preferred operational path for FAR/DFARS ingestion is `rule_cli sync-dita`.

The operator provides a source ID and citation. CaptureBrief constructs the raw GitHub URL itself from the exact repository revision in `RULE-SOURCE-CATALOG.json`.

No caller-supplied URL, branch, tag, credential, or redirect is allowed to become the source of record.

The fetch receipt retains:
- approved catalog fingerprint;
- repository and exact 40-character revision;
- DITA path;
- requested/final raw URLs;
- byte count;
- original source SHA-256;
- resulting content-addressed rule-source ID.

A redirect or final URL change is a hard failure. The fetch path is intentionally narrower than generic web retrieval.

The sync step establishes **source provenance and exact version retrieval only**. Applicability remains a later human-reviewed claim.

## Missing-rule auto-sync and proposal refresh

A current citation proposal may contain a FAR/DFARS reference with no local rule version yet. That state does not mean the rule is absent or inapplicable.

For explicit FAR/DFARS namespaces, CaptureBrief may schedule an approved exact-revision source sync before human version selection.

The auto-sync path:
- deduplicates repeated mentions of the same missing namespace/citation pair;
- fetches only through the pinned GSA sync contract;
- updates the append-only registry;
- re-runs registry matching over the original citation extraction;
- preserves the prior proposal in history;
- invalidates/archives any active human review bound to the previous proposal SHA;
- leaves applicability untouched.

The active case is updated only after all required source syncs complete. If a later source fetch fails, the original case remains unchanged. Earlier successful registry insertions may remain, but they are content-addressed and safe to reuse on retry.

A refreshed proposal is evidence that the lookup surface changed. It is not authority to change the buyer's bid assumption.

After refresh, the reviewer must again decide whether to track a specific edition, leave the occurrence unresolved, or ignore it. A tracked edition still enters Decision Evidence with applicability unresolved.

## Exact rule evidence preparation

After a human rule-version review chooses `TRACK_VERSION`, CaptureBrief requires a second human step before that rule can enter the assumption trace: select the exact official paragraph that supports the rule text being reviewed.

The preparation stage reads only the exact content-addressed `RULESRC` selected by the reviewer.

For each tracked occurrence it prepares:
- a deterministic case source row;
- a content-addressed normalized rule snapshot;
- an exact paragraph passage;
- a Decision Evidence rule-version object whose revision reference is the exact `RULESRC`.

The paragraph selection must identify exactly one retained paragraph locator. Unknown, missing, or duplicate selections fail closed.

The preparation is bound to the human rule-review SHA. If the rule review changes, the preparation is stale and must be redone.

Prepared rule evidence never makes these claims:
- that the rule applies;
- that the rule is incorporated;
- that the selected paragraph controls the acquisition;
- that a buyer assumption is resolved.

Instead every prepared item remains:
- `applicability = UNRESOLVED`;
- `bound_assumption_id = null`;
- `can_auto_bind_assumption = false`;
- `can_auto_apply = false`.

The later Decision Evidence reviewer must still bind the rule to a specific assumption and cite the solicitation/incorporation/effective-date basis.

## Time model

The following are deliberately distinct:

- **source revision** — exact Git/source snapshot inspected;
- **observed_at** — when CaptureBrief observed the source;
- **published_at** — publisher-stated publication time when available;
- **effective_from / effective_until** — reviewed authoritative effective interval when available;
- **incorporated edition** — edition/version the solicitation or amendment binds;
- **decision_at** — when the buyer-facing Pursuit QA decision was made.

Never substitute one for another.

## Version changes

A later rule source may be added without replacing the earlier one.

When versions differ:
- both records remain;
- the textual diff is preserved/inspectable;
- the dependent assumption is eligible for re-review;
- applicability does not change automatically.

The system reports `review_required`, not `newer_version_applies`.

## XML handling

GSA DITA is parsed as untrusted input.

The parser:
- rejects DTD/ENTITY declarations;
- uses only local XML parsing;
- retains original-content and normalized-content hashes;
- extracts paragraph text/locators without executing embedded instructions.

## Citation candidate discovery

CaptureBrief may scan retained public solicitation/amendment text for candidate FAR/DFARS references before the reviewer builds the final Decision Evidence trace.

This is a lookup accelerator, not a rule-selection engine.

The proposal:
- binds the scan to the retained case source ID and document SHA-256;
- records an independent SHA-256 of the text used for citation discovery;
- stores exact mention/context/line information;
- uses an explicit FAR/DFARS prefix when present;
- may use regulation-number ranges only as non-authoritative namespace search hints for bare citations;
- lists every matching pinned registry edition;
- never chooses the newest edition;
- never decides applicability.

A citation with no current registry match remains an unresolved lookup item. It cannot become evidence that no rule exists.

A proposal is routed to a human-only `rules:review-candidates` task. The reviewer must establish the relevant edition and solicitation-specific basis before a rule link can enter Decision Evidence.

## Human rule-version review

A citation proposal must be reviewed before its candidate versions can be carried forward.

The review is bound to the exact proposal SHA-256 and requires one decision for every occurrence:

- `TRACK_VERSION` with one selected rule source that actually appeared in that occurrence's candidate list;
- `UNRESOLVED` with a reason;
- `IGNORE` with a reason.

The review records a named reviewer and timezone-aware review time.

Selecting a version does **not** establish applicability. Every tracked rule remains:

- `applicability = UNRESOLVED`;
- `applicability_authoritative = false`;
- `can_auto_apply = false`.

This permits an older incorporated edition to be carried forward even when a newer edition exists in the registry. The system never silently upgrades a solicitation to the latest known rule.

The selected rule version becomes context for the later Decision Evidence review, where the reviewer must cite the solicitation/incorporation/effective-date basis for `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED`.

## Decision Evidence boundary

A normalized rule source may be bridged into Decision Evidence as:
- a public source-manifest item; and
- a content-addressed rule-text snapshot.

A reviewer must still record:
- why rule review is required;
- which edition/version is being evaluated;
- applicability: `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED`;
- the cited basis;
- any solicitation/incorporation passage;
- reviewer identity and review time.

## Fail-closed examples

- A repository has a newer commit → **does not mean the new rule applies**.
- A deviation PDF exists for the agency → **does not mean it applies to the pursuit**.
- A clause text changed → **reopen dependent assumption for review**.
- No effective date is known → **effective date remains UNKNOWN**.
- The solicitation names an older edition → **do not silently replace it with the latest edition**.
- A source cannot be tied to public authoritative evidence → **SOURCE_LIMITED / UNPROVEN**.

## Current pinned catalog

The canonical machine-readable source list is `RULE-SOURCE-CATALOG.json`.

Source revisions are intentionally pinned. Updating a pin is a reviewed product change and must pass the full Product Core regression suite.
