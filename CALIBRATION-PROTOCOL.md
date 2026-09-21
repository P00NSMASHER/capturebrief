# CaptureBrief Internal Calibration Protocol

Updated: 2026-09-21

CaptureBrief may use a qualified external practitioner to challenge a frozen public-source sample and the methodology demonstrated by that sample.

The calibration is **internal product evidence**. It is not:

- a customer outcome;
- a legal or procurement determination;
- proof that every future case is correct;
- an endorsement;
- permission to use the reviewer’s name, company, credentials, logo, testimonial, or likeness publicly.

Public attribution remains prohibited unless a separate written approval is retained and referenced explicitly.

## Freeze the reviewed object

Before an external review is acted on, retain:

- an opaque review ID;
- the exact sample/reference reviewed;
- SHA-256 of the reviewed sample;
- review receipt time;
- opaque reviewer reference;
- scope/agreement reference.

A later product version must not be represented as the version the practitioner reviewed unless separately reviewed.

## Convert feedback into bounded findings

Each finding is classified as one of:

- DECISION_LOGIC
- HARD_GATE
- ELIGIBILITY_SECURITY
- DEADLINE_SUBMISSION
- SOURCE_CONTROL
- CAVEAT_LANGUAGE
- CHECKLIST
- PRODUCT_BOUNDARY
- OTHER

Severity is:

- CRITICAL
- MATERIAL
- MINOR
- OBSERVATION

The internal structured record paraphrases the finding and links to the retained review evidence. Raw review correspondence or a consultant memo does not need to be copied into the repository.

## Adjudicate every finding

Disposition is explicit:

- PENDING
- ACCEPT
- PARTIAL
- REJECT
- DEFER

Accepted or partially accepted findings are not considered closed merely because the team agrees with them. They close only after the implementation is linked to both:

1. a change reference; and
2. a regression/test reference.

Rejected and deferred findings require a recorded rationale.

## Calibration closure

The structured summary remains open while:

- any finding is PENDING; or
- an ACCEPT/PARTIAL finding has not been implemented.

CRITICAL or MATERIAL open items are called out separately.

A calibration can be summarized as CLOSED only after every finding has a disposition and all accepted/partial changes have implementation + test evidence.

CLOSED means the bounded calibration feedback was handled. It does **not** mean CaptureBrief is certified, independently validated for every pursuit, or legally correct.

## Product safety rule

No calibration finding may silently weaken:

- source/version provenance;
- first-party history/currentness separation;
- reference closure;
- byte/hash binding;
- Decision Evidence exact-passage checks;
- human rule/deviation applicability;
- targeted-watch history preservation;
- release gates.

If an expert recommends a weaker evidence boundary, that recommendation must be explicitly adjudicated and cannot be implemented without regression evidence supporting the new boundary.

## CLI

Validate a structured calibration review:

    python -m capturebrief_core.cli calibration-validate calibration.json

Summarize disposition/implementation state:

    python -m capturebrief_core.cli calibration-summary calibration.json

The example fixture is intentionally fictional:

    fixtures/calibration_review_example.json

## Commercial boundary

The practitioner’s internal feedback can improve the product before supervised pilots.

Do not publish wording such as:

- “expert approved”;
- “CPCM reviewed”;
- “independently certified”;
- “endorsed by”;

unless the exact public statement and attribution are separately authorized in writing.

The best commercial evidence remains real paid customer use, explicit buyer feedback, measured delivery effort, repeat demand, and correction/retraction history.
