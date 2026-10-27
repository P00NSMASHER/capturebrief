# CaptureBrief free assumption check — supervised pilot

The free offer is one complete, source-backed assumption check for one public
federal IT/cyber/cloud pursuit. There is no card, charge, automatic subscription,
or included change watch. The paid $149 one-time review still covers up to five
assumptions and the 14-day targeted watch. An upgrade requires a new explicit
purchase and the existing live Stripe reconciliation.

## Request and eligibility

The website creates a local email draft; it does not submit or confirm receipt.
The recipient is `jay@retallyrecovery.com`. Previously generated Gmail-envelope
drafts remain accepted for compatibility; arbitrary recipients are rejected.
The strict free-check contract is:

- Subject: `CaptureBrief free assumption check request`
- Purchase claim: `Free assumption check requested`
- Company, work email, public opportunity URL, current posture and exactly one
  assumption; the public/non-sensitive consent must be present.
- Closing: `Please confirm eligibility, source coverage, and delivery date for one free assumption check. I understand there is no charge, no automatic upgrade, and no included change watch.`

The importer records only a requested offer. It cannot certify receipt,
business identity, trial eligibility, payment, evidence or customer release.
The existing paid and scope-first formats remain valid.

## Private operation

1. Independently reconcile the incoming message and consent in the controlled
   inbox, then use the existing private batch importer. Keep all request/case
   files outside the source and website trees.
2. Review business identity and prior trials. Use one canonical legal entity
   key or verified domain key for the same company, including aliases. A
   customer-supplied email or new address is not proof of a different business.
   Retain the identity-review evidence privately and compute its SHA-256.
3. Use one dedicated retained registry for the whole pilot. Reserve a slot:

   ```sh
   python scripts/register_free_check.py /private/requests/request-SHA.case.json \
     --registry /private/free-checks.sqlite \
     --reviewed-business-key domain:example.com \
     --identity-review-sha256 REVIEW_SHA256
   ```

   The example is illustrative, not a real customer or completed identity review.
   The registry enforces one reservation per canonical business, one request
   per reservation and ten businesses total. Identical retries are idempotent;
   concurrent reservations are serialized. There is no reset/delete command
   or automatic conversion. Retain and back up the original registry.
4. Confirm scope and a feasible delivery date before accepting the engagement.
   The reservation is `RESERVED_REVIEW_REQUIRED`, not proof of admission or
   source readiness. No trial is represented as completed until a real checked
   result is delivered with independently retained provider evidence.
5. Enrich the original case through existing approved source/review steps.
   The selected assumption and original intake must not change to reuse the
   reservation for another question. `inspect_free_check` checks this scope
   against the registry and runs the unchanged source/trace release gates.
   Missing reservation, current-source proof, history, reference closure or
   human review keeps the free result blocked. A free flag is not a bypass.
6. Build the private one-check Markdown report and its separate integrity
   receipt after evidence is complete:

   ```sh
   python scripts/build_free_check.py /private/reviewed-case.json \
     --registry /private/free-checks.sqlite --output /private/free-check.md
   ```

   The report includes the complete handoff, source appendix and exact Decision
   Evidence trace. It contains no watch baseline and creates no paid order.
   Independently compare the written report SHA-256 with the original receipt
   before approved delivery. A file hash proves local integrity, not source
   truth or actual customer receipt.
7. Customer messages and result delivery remain subject to the existing owner
   communication authorization. This implementation sends nothing, schedules
   no watch, creates no payment and grants no customer-release authority.

## Current launch status and remaining work

This is a working request/import/reservation/evidence-inspection/report foundation.
Do not advertise instant output or guaranteed admission. The live-pursuit
source acceptance remains incomplete: the production catalog is approved only
through FY2026, and a current private source index/current SAM API observation
and independent delivery review are still required. The source test report
records the exact October 27 evidence and its limits.

The existing paid ZIP contains a targeted-watch baseline. Use the separate
free-check report builder for the trial. Provider-verified delivery on a genuine
reviewed pursuit remains unproved before broad self-service enrollment.

Measure real usefulness, whether the result changed a next action, recorded
delivery effort and explicit paid upgrades. Free reservations are not paid
customers, revenue, successful delivery or proof of commercial demand.
