# CaptureBrief — supervised first-pilot operating runbook

Version: 2026-10-18 candidate. Applies only to a **single human-supervised,
public-source federal IT/cyber/cloud pursuit**. This document does not turn
software QA into first-customer validation or change any customer terms.

## A. Source, identity, and prepayment intake

1. Confirm that the incoming request actually arrived in the controlled
   Gmail account. A generated browser draft or clipboard copy is not delivery.
2. Capture the sending address, customer-reported work email, company,
   public SAM.gov notice URL, current GO/HOLD/PASS/UNSURE posture, up to
   five distinct non-sensitive assumptions, and explicit public-only consent.
3. Validate those fields using CaptureBrief's existing intake core. The
   buyer's assertions create only UNPROVEN case assumptions and cannot
   establish a sourcing, deadline, eligibility or payment fact.
4. Reject private documents, credentials, CUI, protected portals,
   pricing/staffing strategy and proprietary proposal contents. The first
   pilot must be fully supportable using public official sources.
5. Match the opportunity to the actual public **IT/cyber/cloud** offer
   and confirm what is being reviewed before promising a delivery date.
6. State clearly what the service will **not** do (no legal advice, no
   bid submission, no guarantee of eligibility or award). Confirm the
   customer owns bid and procurement decisions.

## B. Payment: live account, never website assertion

1. If a free scope check was requested, confirm fit before requesting
   payment. If a live Checkout payment is claimed, independently inspect
   CaptureBrief's own **live** Stripe account.
2. Match the account, customer identity, product, one-time USD 149.00
   amount, unique payment or Checkout Session ID and terminal paid state.
   A URL containing checkout=complete, selected PAID field, email, browser
   screenshot, invoice link, or sandbox payment is NOT payment evidence.
3. Record processor reference and billing reconciliation only in the
   private operator system; never the public GitHub repository.
4. Decline and refund out-of-scope paid requests *before work begins*,
   consistent with the published terms. Verify actual refund via Stripe
   and retain an opaque receipt; do not claim it has happened from a
   simulated test.
5. Do not start work or send a payment/acceptance email solely on the
   strength of the customer's claim.

## C. Evidence production, review, and release

1. Obtain a fresh official SAM Public Opportunities API v2 observation
   through the approved key-bearing operator environment, and retain
   canonical raw-response, pagination and current-action proof. Never
   use a UI-only/web-search observation as a substitute.
2. Establish explicit history scope. For a FULL_CATALOG claim in FY2027,
   the reviewed catalog must be current through FY2027 and **every**
   required active/archive source slot must have retained approved,
   hash-bound and fresh original bytes. A filename seen on a website
   does not satisfy this.
3. Confirm every controlling public solicitation, amendment, attachment,
   reference and exact source version. Separate current rules from
   superseded ones, and record every unresolved or source-limited item.
4. Require human review for acquisition rule applicability and each
   decision-relevant conclusion; never manufacture signoff or resolve
   unsupported bidder-specific facts.
5. Independently run case audit, Decision Evidence and delivery checks.
   Bundle only if READY_FOR_HUMAN_RELEASE and TRACE_COMPLETE with
   non-synthetic evidence:
       python -m capturebrief_core.trace_cli bundle case.json -o delivery.zip > delivery-receipt.json
6. Independently verify actual ZIP bytes against the separately retained
   original build receipt; the ZIP integrity pass alone does not prove
   source correctness:
       python -m capturebrief_core.trace_cli verify-bundle delivery.zip --expected-sha256 ORIGINAL_SHA
7. Keep the ZIP, raw case, reviews and original receipts in protected
   operator storage. Never put customer records in public GitHub,
   GitHub Pages, GitHub Actions logs or public artifacts.

## D. The 14-day targeted watch

1. At actual delivery, freeze the validated case and build the 14-day
   baseline with capturebrief_core.trace_cli watch-baseline.
2. Record agreed official public watch targets, cadence, responsible
   operator and end timestamp in the private engagement record. The
   watch is scheduled, not continuous. Do not promise sources that
   cannot be checked under the approved collection policy.
3. At each scheduled check, independently fetch and retain fresh,
   approved first-party observations for agreed sources. Merely rerunning
   a comparator on an old case is not a fresh check.
   For an already history-resolved active case, the on-demand approved
   SAM current-action portion can run with an operator-held API key:

       python scripts/run_current_watch_cycle.py /private/case.json /private/baseline.json \
         --updated-case /private/case-refreshed.json \
         --receipt-dir /private/watch-receipts

   This command uses SAM_API_KEY from the operator environment, requires
   a complete retained history receipt, fetches and verifies only the
   documented latest-active API source, and produces an immutable review
   receipt. A no-active-match or missing historical action is a REVIEW
   REQUIRED event, never proof of termination. It does not fetch archived
   CSVs, all references or rule editions; those agreed watch sources
   still require separate approved observations. It is not scheduled,
   not a completeness certification, and never sends updates.
4. Use scripts/run_watch_receipt.py on the delivered baseline and the
   actually refreshed private case. It writes an immutable, content-
   addressed receipt outside the public repo. Exit 0 = fresh proven
   unchanged; 3 = human review required/expired/stale/change; 2 =
   invalid input or another controlled failure.
5. When status changes, reviewer assesses affected assumptions; the
   original buyer decision must not be silently changed. Record changed,
   missing, stale, inaccessible and expired source results distinctly.
6. Draft—but DO NOT send—the affected finding/update until the owner
   explicitly approves that specific recipient, text and attachments.
7. Confirm completion/expiration against the exact 14-day deadline;
   do not label a 14-day watch complete from a simulated clock.

## E. Written operating acceptance, privacy and follow-up

- Before any live work: retain the customer's written scope, public
  evidence boundary, agreed delivery date, correction/cancellation terms,
  and an authorized contact.
- Separate operator review, case audit, delivery integrity, and external
  message approval. No single PASS flag substitutes for the rest.
- Protect access to messages, payment references and case records; retain
  only as long as legitimately needed for service, correction, security
  and accounting/legal obligations. Handle deletion requests using the
  published data-handling policy; do not promise a fixed retention period
  without a documented business/legal schedule.
- Track real buyer usefulness, actual delivery effort, repeat demand,
  refunds and corrections using the existing outcome ledger, without
  fictional revenue or fake testimonials.
- Complete independent exact-head QA and the normal protected PR
  release review before deploying product or website source changes.

## F. Go/no-go

NO-GO unless a real in-scope first buyer can be processed from
verified arrival + payment (or scope-first) through approved-source
acquisition, independent human-review, verified customer bundle and
an actually operable fresh-source watch. External emails/deliveries
require explicit approval **for each specific message**.

Operator preflight is read-only:
    python scripts/pilot_preflight.py

This output always distinguishes core technical checks from processor,
inbox, signoff, and publication proof. It does not charge, send or grant
release permission.
