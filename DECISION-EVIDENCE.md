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

`buyer assumption -> exact public source/version -> exact passage -> optional rule-edition review -> human evidence state -> buyer finding -> next action -> targeted change watch`

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
