# CaptureBrief Reference Review Contract

Updated: September 21, 2026

CaptureBrief separates **reference discovery** from **reference completeness**.

## Automated proposal

`capturebrief_core.references.propose_reference_scan` scans already-retained public text for conservative candidate mentions such as:

- amendments
- attachments
- exhibits
- appendices / annexes / enclosures
- schedules
- drawings
- named procurement systems such as PIEE / FedConnect / eBuy / DIBBS
- external URLs

The result is always `status: PROPOSED`.

Automation is explicitly marked `LOCAL_PROPOSAL_ONLY` and `can_claim_completeness: false`. A regex hit is not proof that the item is controlling or even a true dependency.

## Human confirmation

A scan can become `COMPLETE` only through `confirm_reference_scan`.

The reviewer must:

1. identify themselves;
2. provide a timezone-aware review timestamp;
3. attest that every source in the proposal was reviewed;
4. make a decision on every proposed candidate;
5. provide a reason for every ignored candidate;
6. manually add dependencies the parser missed.

The confirmation output hashes:

- the exact proposal payload;
- the complete review payload;
- the exact final reference-ID set.

Changing the reference list after review invalidates the scan.

## Closure

Human confirmation establishes the **inventory**, not the answer.

Each tracked reference still starts `UNRESOLVED` and must become one of:

- `RESOLVED_TO_RESOURCE` — verified source object plus verified hashed bytes;
- `SUPERSEDED_BY` — verified successor plus explicit supersession evidence;
- `EXTERNAL_DEPENDENCY` — explicit external/restricted state, URL, and reason.

Anything else remains fail-closed.

## CLI

Proposal:

    python -m capturebrief_core.cli references-propose \
      --source notice=notice.txt \
      --source solicitation=solicitation.txt \
      -o reference-proposal.json

Human review JSON must cover every candidate and every source.

Confirmation:

    python -m capturebrief_core.cli references-confirm \
      reference-proposal.json reference-review.json \
      -o reference-review-result.json

The result contains `reference_scan` plus the initial unresolved `references` list.
