# CaptureBrief Decision Evidence

## Product promise

**Know what your bid decision rests on.**

CaptureBrief does not stop at “this solicitation says X.” For each decision-relevant assumption, the product can preserve and show:

1. the exact retained public source;
2. the exact source version;
3. the exact cited passage and human-readable locator;
4. the rule edition reviewed, when a FAR/DFARS/supplement/deviation question is involved;
5. the reviewed applicability basis;
6. what changed between versions;
7. what evidence remains missing.

## Trust boundary

Decision Evidence is a human-supervised evidence layer, not an autonomous procurement/legal decision engine.

The product must not infer that:
- the newest published rule is automatically controlling;
- a newer Git commit establishes a rule effective date;
- a valid hash authenticates a publisher;
- a source observation proves complete solicitation history;
- one matching passage decides legal applicability;
- a changed source silently rewrites an earlier decision.

Applicability remains `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED` with a named reviewer and cited rationale.

## Release behavior

New intake-generated cases require a decision trace. Release remains fail-closed when:
- the trace is absent;
- the trace/case family differs;
- retained text or trace objects are mutated;
- cited text does not exactly match the retained snapshot;
- the snapshot is not bound to the source manifest/document hash;
- a non-public source is used as resolved public evidence;
- the buyer-facing finding differs from the underlying review;
- a rule-dependent finding has no reviewed rule edition/applicability basis;
- an incorporated edition is silently replaced by another edition;
- an unresolved/source-limited assumption has no concrete evidence request.

Older cases that predate this feature remain readable and are not retroactively labeled fully traced.

## Rule-to-assumption evidence

When a FAR/DFARS rule matters, CaptureBrief separates three questions:

1. **What exact rule edition/text was reviewed?**
2. **What pursuit-specific source says that edition applies or does not apply?**
3. **What does that mean for the buyer's bounded assumption?**

The rule text cannot prove its own applicability.

For a resolved applicability decision, the reviewer must cite a separate exact passage from a retained solicitation, amendment, or pursuit-context snapshot. The basis quote must match the retained evidence exactly and carries its own locator.

The resulting rule link records:
- namespace + citation;
- exact edition;
- `APPLIES`, `DOES_NOT_APPLY`, or `UNRESOLVED`;
- basis type;
- incorporated edition when relevant;
- reviewer rationale;
- reviewer identity/time;
- exact pursuit-specific basis passage.

The applicability conclusion is human-reviewed QA, not legal authority. CaptureBrief records `can_auto_apply = false` and does not change the assumption's evidence state automatically.

## Exact source-version deltas

When a finding depends on a source changing across versions, CaptureBrief can retain a paired version delta:

- the exact prior source version;
- the exact newer source version;
- each version's retained document SHA-256;
- an exact before passage and human-readable locator;
- an exact after passage and human-readable locator;
- the reviewed relation: `AMENDS`, `CORRECTS`, or `SUPERSEDES`;
- a concise reviewer summary of the change.

The before passage must belong to the declared from-version and the after passage must belong to the declared to-version. Supplying only one side fails closed. Older retained traces that contain a version relation without exact paired passages remain readable, but the report surfaces that omission as a warning rather than pretending the textual delta was captured.

This lets the buyer inspect **what changed**, not merely see a label saying that a source changed.

## Buyer delivery bundle

A completed Decision Evidence case can be packaged through one release-gated command:

    python -m capturebrief_core.trace_cli bundle case.json -o capturebrief-delivery.zip

The bundle is refused unless:

- `decision_trace_required = true`;
- the full CaptureBrief audit returns `READY_FOR_HUMAN_RELEASE`;
- Decision Evidence returns `TRACE_COMPLETE`;
- the trace is non-synthetic.

The ZIP contains:

- `brief.md` — concise pursuit QA handoff;
- `decision-evidence.md` — exact source/rule/version evidence;
- `decision-evidence.html` — buyer-readable evidence report;
- `decision-summary.json` — machine-readable reviewed conclusions;
- `source-version-manifest.json` — public source/rule version identities and hashes without raw source text;
- `delivery-manifest.json` — SHA-256 + byte length for every delivered file.

The bundle intentionally excludes the raw internal case object and does not package restricted source bytes. ZIP entry metadata is normalized so the same case and generation time produce the same bundle bytes and hash.

## Change watch

The trace is append-preserving.

A newly observed version of a source or rule:
- does not mutate prior evidence;
- does not automatically change applicability;
- emits a review-required event;
- reopens only assumptions dependent on that source/rule key.

Historical trace deletion or in-place mutation is reported as an integrity violation.

## Operator workflow

Decision-evidence gaps enter the existing CaptureBrief work queue as `HUMAN_REVIEW` tasks.

The intended flow is:

`buyer assumption -> exact public source/version -> exact passage -> pinned rule edition -> exact rule passage -> separate pursuit-specific applicability passage -> human evidence state -> buyer finding -> next action -> targeted change watch`

This sits underneath the existing product controls:

`SAM family/history -> current action -> packet/attachments -> reference closure -> required bytes -> assumption Decision Evidence -> human release`

## CLI

```bash
python -m capturebrief_core.trace_cli check case.json
python -m capturebrief_core.trace_cli report case.json --format markdown -o decision-evidence.md
python -m capturebrief_core.trace_cli report case.json --format html -o decision-evidence.html
python -m capturebrief_core.trace_cli freeze case.json --directory evidence/decisions
python -m capturebrief_core.trace_cli compare before.json after.json
```

## Buyer-facing display

The default delivery stays concise. Each important assumption shows:
- assumption;
- evidence state;
- finding;
- next action.

The buyer can expand **Inspect the evidence trail** to see:
- exact passages;
- source/version labels;
- document hash receipts;
- rule edition/applicability review;
- recorded source-version changes.

The objective is not a longer report. It is a short decision brief with inspectable provenance underneath it.
