# CaptureBrief — first paid pilot release gates (18 October 2026)

**Verdict: HOLD — not independently validated for a paid customer.**
Authoritative website: https://p00nsmasher.github.io/capturebrief/ on the gh-pages branch. Product core: main branch. Legacy Netlify is not the current website.

## 1. Real first-party pursuit and delivery

- [x] Inspect a genuine first-party SAM.gov opportunity with publicly visible version changes.
- [x] Exercise intake and core refusal on a real public URL paired with fictional buyer claims. No invented source receipts or automatically supported assertions.
- [ ] Select an actual current IT/cyber/cloud pursuit within the offer and retain approved SAM Public API v2 observation, full public-source provenance, required source bytes, exact quotes, reference closure and human-reviewed rule applicability.
- [ ] Produce a complete non-synthetic Decision Evidence package and actual delivery ZIP, verify it using the original independent receipt and inspect each buyer-facing finding.

**Real public metadata rehearsal, not a customer:** First-party GSA notice 47PH5226R0003 at https://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view was inspected on October 18, 2026. Its October 14 Amendment 007 extended offers to November 4, 2026 at 4 p.m. Eastern, superseding October 29. This is a construction procurement, useful for checking the version-control truth boundary but **not** a representative IT/cyber customer sample. No complete SAM API receipt, retained source packet or customer bundle was produced. The fictional intake test uses the superseded deadline as a buyer assumption and must leave it UNPROVEN until evidence is obtained.

## 2. FY2027 SAM archive catalog

- [x] An October 18 read-only inspection of SAM.gov's live first-party Archived Data page visibly found FY2027_archived_opportunities.csv marked Public. FY2026, FY2029 and FY2030 also appeared; FY2028 was not established by that inspection. Official source: https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public .
- [ ] Preserve a distinct **human-reviewed** October FY2027 catalog observation, exact observed year inventory, source identity, observation timestamp, version/hash and independent approval before updating the canonical approved catalog. A browser agent's observation is not a human signoff.
- [ ] Fetch and retain genuine approved first-party active and relevant archive extract bytes, update index receipts and confirm currentness, including FY2027 before issuing any FY2027 FULL_CATALOG completeness claim.
- [x] Retain the existing FY2027 fail-closed production logic until both independent catalog review and required fresh source receipts are complete. Do not silently backdate live checks to FY2026 or invent a FY2028 record.

## 3. Checkout and intake

- [x] The current public website/legal pages are reachable. The CaptureBrief live Stripe payment link was independently read as active for a one-time $149 charge.
- [x] The browser request-builder is local only: it copies a draft or asks the buyer's email client to open a message. It does not submit data to a CaptureBrief backend.
- [x] Proposed gh-pages PR #50 corrects a trust issue: buyer-selectable PAID and a forgeable ?checkout=complete redirect are **not** processor payment evidence. It labels the resulting email claim unverified.
- [ ] Verify exact published email-draft behaviour and actual inbox receipt under owner-approved test sending. A copied or opened draft does not establish that an email was sent or received.
- [ ] For an actual order, reconcile Stripe account, price, payment ID, settlement/payment status and refund path, without relying on the customer-supplied status or website URL. Avoid a real charge for QA; refunds require case-specific authorization.

## 4. Fourteen-day targeted watch

- [x] Existing core watch logic retains the hash-bound baseline, 14-day expiry, fresh-observation requirement, change/reopen events, review state and prohibition of automatic decision changes.
- [ ] For a released genuine source case, create the initial baseline at delivery and perform **actual scheduled fresh approved source observations** across the full 14-day interval; retain per-check proof and an operator exception queue.
- [ ] Exercise changed, no-change, stale, fetch-failure and expiration outcomes using fresh evidence, without automatically emailing customers. Every external message requires independent specific approval.

## 5. Fulfillment and security

- [x] Core delivery rules require audit approval, complete non-synthetic Decision Evidence and ZIP-byte verification.
- [ ] Validate the actual final ZIP against a separately retained original receipt (command: python -m capturebrief_core.trace_cli verify-bundle delivery.zip --expected-sha256 ORIGINAL_SHA).
- [ ] Record written acceptance of one public pursuit, scope, turnaround, exclusions, refund/correction process and safe record retention. Keep credentials, case content, raw buyer emails and private files outside public GitHub.
- [ ] Review any procurement or eligibility judgment with exact source/version evidence. Explicitly approve each outgoing reply, change notice and delivery.

## 6. Independent acceptance and rollout

- [x] Main Product Core at 12d90024f053a78ead7936abf092931fce240d3e passed (https://github.com/P00NSMASHER/capturebrief/actions/runs/39077316900).
- [ ] Verify the final proposed main and gh-pages PR heads against full Linux/Windows Product Core and the GitHub Pages Chromium/WebKit buyer-journey CI.
- [ ] Obtain independent release review; reconcile open material faults, approve releases through existing controls, deploy the correct gh-pages branch and verify live published bytes.
- [ ] Complete one real supervised IT-sector customer workflow from confirmed paid order and reviewed source package through verified delivery and monitored follow-up, recording feedback/corrections.

## Read-only technical preflight (does not certify commercial launch)

From the repository root, run:

    python scripts/pilot_preflight.py --as-of 2026-10-18T12:00:00Z

When private operator-held real evidence exists, supply --case, --bundle, --receipt, --baseline and --observed-case. The tool computes audit, version freshness, bundle integrity and watch status from actual artifacts, without making a network call, emailing, charging, publishing, or accepting payment. It will not auto-approve a pilot. Even when its technical checks pass, independent inbox/payment verification, specific message approval, real-source correctness and approved release are mandatory.

PR #49 concerns a separate older public ZIP packaging lane, not the active GitHub Pages publication. The unrelated PA x402 discovery workflow startup error should not be used as evidence that CaptureBrief's Product Core failed.

**No actual new customer, charge, sent message, downloaded archive, 14-day completed watch or buyer delivery is claimed in this record.**
