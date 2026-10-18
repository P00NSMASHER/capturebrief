# CaptureBrief: private customer-draft import (pilot candidate)

This tool closes a gap between the public local-only request builder and
the Python intake core. It is not an email integration, automated lead
capture, a payment verification service, or permission to contact anyone.

## What it does

1. Accepts only the exact CaptureBrief plain-text draft format, either the
   Copy request version (To/Subject lines) or the body of the locally
   composed email (without those lines).
2. Applies the existing core's stricter validation for company, work email,
   public opportunity URL, posture, and up to five distinct 500-character
   assumptions. Rejects injected headers, malformed numbering, extra
   footers/signatures, unsupported control characters, and incompatible
   subject/payment claims.
3. Creates a case with UNPROVEN assumptions and no invented source evidence;
   no source has been fetched or interpreted.
4. Writes a case JSON and independent review receipt atomically, with
   content-hash idempotency, under caller-supplied private paths outside
   this public repository and its website.
5. Labels any "Already purchased" text as unverified. A copied draft is
   not evidence that the customer sent an email, that Gmail delivered it,
   that Stripe received payment, or that the buyer's claim is true.
6. Prints only opaque case IDs, hash receipts and local artifact locations;
   it does not print buyer names, email addresses or request contents.

## Running it (private machine only)

Save the actual plain-text request to a private .txt file, then:

    python scripts/import_request_draft.py "/private/inbox/request.txt" \
      --case-output "/private/cases/CB-one.json" \
      --receipt-output "/private/cases/CB-one-receipt.json"

Optional reproducible import time (must be timezone-aware):

    --imported-at 2026-10-18T20:00:00Z

The submitted_at in this imported case is the local import time, not
proof of when the customer originally sent an email; the case records this
basis explicitly.

The output paths must be distinct, outside the public repository, and
cannot silently overwrite different bytes. Keep filesystem and provider
access controls, retention policy, and backup practices appropriate for
client contact details. An import error never triggers a message.

## Review gate after import

- Verify the customer's email truly arrived from the expected contact and
  reconcile the sender identity separately.
- Check any claimed order against CaptureBrief's live Stripe account, using
  the unique payment/Checkout record and one-time USD 149 charge. This tool
  DOES NOT validate payment. Do not mistake a website redirect or the word
  "purchased" for processor evidence.
- Confirm the selected pursuit is in-scope public IT/cyber/cloud, and that
  no nonpublic/controlled content has been supplied.
- Use only allowed official SAM sources, source/version review, original
  byte receipts and independent procurement interpretation.
- Complete the normal delivery/monitoring gates before work is described
  as release-ready. Each outbound message still needs owner approval.
- Do not commit cases, receipts, emails, personally identifiable data,
  credentials or source bytes to the public repo or Pages branch.

## Tests

    python -m unittest tests.test_request_draft -v
    python -m unittest discover -s tests -v

The test corpus contains only fictional buyer identity and assumptions.
Passing does not establish real customer delivery or commercial outcomes.
