# CaptureBrief release consistency

Updated: 2026-09-21

This repair builds on main commit `3a5a1306c85d6ae55e671df1cbdaf5002d62d1f6`.
It preserves the existing strict automation lanes, legacy-case delivery refusal,
atomic ZIP publication, source/API evidence checks, and per-message approval boundary.
It does not reinstall the earlier repair archive over newer source files.

## One preparation decision

`capturebrief_core/delivery_readiness.py` supplies the same preflight to the
fulfillment planner and delivery builder. It requires:

- literal `decision_trace_required = true`;
- the full case audit to return `READY_FOR_HUMAN_RELEASE`;
- the Decision Evidence engine to return `TRACE_COMPLETE`;
- non-synthetic evidence;
- no blocking finding in either evidence plane.

A legacy-readable case, an empty work queue, or a contradictory green label
cannot override a missing prerequisite. The planner preserves the existing
`delivery:readiness` human-review task and exposes the same blocker codes that
prevent the builder from producing files.

This is preparation readiness only. It grants no authority to send an email,
transmit a bundle, publish customer data, or make a bid decision.

## One evaluation clock

The preflight fixes a timezone-aware evaluation time. That same instant is
passed through the brief, HTML evidence report, Markdown evidence report,
machine-readable summary, and watch baseline. The summary records `evaluated_at`.

Previously the gate accepted an explicit clock but report renderers evaluated
the trace again using wall-clock time. A historical replay could therefore
contain report verdicts evaluated at a different instant from its release gate.

Existing renderer calls remain compatible; callers may now pass `now=` for a
reproducible review. Equivalent timezone offsets normalize to the same UTC
instant in the bundle builder.

## One case snapshot

Bundle preparation uses a private copy of the submitted case. A caller changing
its own working dictionary after rendering cannot make the final manifest name
a different case state from the reports it contains. The original caller's
object is not modified by the builder.

This is a consistent build snapshot, not a database transaction or an immutable
external evidence store. Callers should not mutate an object while handing it
to the copying operation.

## Receipt belongs to the built archive

The archive's SHA-256 and size are computed from the completed staged ZIP before
atomic publication. They are not reread from the destination path after another
writer could replace it.

The returned receipt therefore records:

`receipt_scope = BUILT_ARTIFACT_NOT_CURRENT_PATH_STATE`

A later replacement does not alter the receipt for this build. Verify the file
against the retained receipt before using or transmitting it. The receipt is
not a signature, publisher authentication, or proof that the output path cannot
subsequently change.

Existing failed-write and no-overwrite protections remain in place. No fallback
publishes partial ZIP contents if atomic publication fails.

## Regression coverage

`tests/test_release_consistency.py` runs with the real repository audit, trace,
work-queue, renderer, and bundle implementations. It uses real repository test
fixtures. Spies call the real evaluator; they do not substitute green verdicts.
Controlled race tests change the caller dictionary or output path after an actual
build to check version/receipt consistency.

Checks include missing history/currentness/manifests, legacy and synthetic cases,
source/quote/hash edits, literal boolean requirements, a pre-evidence evaluation
time, matching planner/builder blockers, explicit renderer clocks, equivalent
timezone offsets, later-writer receipt substitution, and caller-case mutation.

Run from the repository root:

```bash
python -m unittest discover -s tests -v
python -m unittest tests.test_release_consistency -v
```

These are software regression checks. They are not a real-customer delivery,
expert calibration, legal applicability validation, revenue result, or production
deployment proof. The founding offer and external-communication rules are unchanged.
