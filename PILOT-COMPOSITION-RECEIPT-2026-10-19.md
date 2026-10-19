# CaptureBrief — proposed release composition acceptance (technical only)

**Date:** 2026-10-19 UTC  
**Decision:** TECHNICAL COMPOSITION PASS; PRODUCTION / PAID PILOT STILL ON HOLD.

This receipt documents a temporary, no-write-to-origin integration replay
of six **unmerged** proposed pull requests. It does not authorize merging,
payment acceptance, procurement decisions, customer messages, source
certification or a live 14-day watch.

## Exact release inputs

| Target | Pull request | Immutable candidate head |
|---|---|---|
| Customer website / gh-pages | #50 | 2f5af397fc5d46e6f919f11b0f6e3701df69c665 |
| Pilot core, source-index gates, watch | #51 | 620842390d741bb5bcfa9bc1994b1bdfb650c884 |
| Private website-draft intake parser | #52 | c95fd399c3d3816ac02e628d86347ff96b263bdc |
| Official SAM public CSV/S3 transport security | #53 | 414d1d667257d02420b346df439b0d695cec58a6 |
| Unrelated PA x402 CI YAML parse fix | #54 | 567c648ac91f23423a808b85ec3c617a919dcc36 |
| Live Stripe three-record reconciliation | #55 | bbbac444705b0a95ea4af12430c287a984b427ee |

Base public Python core: main at 12d90024f053a78ead7936abf092931fce240d3e.
Production website: gh-pages at 415edcaf1bc05f522e22141b3b59cdd9a7c6a0a0.

The workflow builds a local ephemeral branch and merges the five main-based
candidates with Git. It checks each fetched branch against the exact pinned
head SHA, rejects unresolved merge conflicts or movement of upstream heads,
and separately checks out the immutably pinned gh-pages candidate.
**It does not push, merge, deploy, charge, contact, or run a source fetch.**

## Results

Original composition run: #39272506993
https://github.com/P00NSMASHER/capturebrief/actions/runs/39272506993

That first replay found a real Windows test-fixture defect: SQLite connections
were left open by a test fixture, causing WinError 32 when cleaning up temporary
source-index files. This was repaired on PR #51 by explicitly closing every
fixture SQLite connection, without relaxing source verification or the
production database's own fail-closed rules.

Corrected exact-candidate composition run: #39272784471
https://github.com/P00NSMASHER/capturebrief/actions/runs/39272784471

- All five main-based PR candidate commits composed without conflicts.
- **Linux**: 508 Product Core unit tests PASS.
- **Windows**: 101 targeted pilot, history-index, payment and security tests PASS.
- **Chromium + WebKit**: website draft -> actual Python intake parser ->
  fictional Stripe reconciliation PASS. This includes payment-forgery,
  refund, wrong-account, stale source, protected data and no-send boundaries.
- No live Stripe records, API keys, production secrets, private customer data,
  actual customer deliveries or real customer communications were used.
- The PA x402 workflow's branch-push startup failures on main were handled as
  a separate existing defect; the proposed YAML fix is included in the
  combined test tree, but **an actual production x402 job is not accepted
  solely by this composition replay**.

## Independent release decision: REQUIRED / NOT ISSUED

The following must be evidenced separately before shipping, even if the
composition tests are green:

1. Independent reviewer approvals for the exact PR heads and any required
   target branch protection, including separate approval before deploying
   public gh-pages changes. No review can be manufactured by tests.
2. Human-reviewed, authoritative FY2027 SAM source-catalog inventory
   and a private, complete, fresh archive/source index with original
   publisher bytes and independently checked digests for all required slots.
   An automated original FY2027 SHA-256 alone does not cover all years.
3. Real approved in-scope IT/cyber/cloud public-source case, verified buyer
   scope, authenticated controlled inbox intake, processor-paid live order
   if appropriate, human source/rule review and original delivery ZIP receipt.
4. Real 14-day scheduled source-operation proof from **genuine** automatic
   checks and immutable previous-receipt chain, including missing/stale/changed
   cases, not a simulated 14-day clock replay.
5. Authorized private machine/host, access control, retention/privacy policy
   and verified backups before any actual customer case is stored.
6. Specific explicit approval for each outgoing customer email/message.
   The website draft, automation output and Stripe redirect authorize
   no communication.

**Do not label this a production rollout, an independent release acceptance,
a paying customer pilot, or an independently certified service.**

## Reproduction

The read-only workflow lives at
.github/workflows/capturebrief-release-composition.yml on this branch.
It is intentionally restricted to this QA branch and an explicit manual
dispatch after approval. It runs no periodic schedule. To repeat safely,
verify branch heads are unchanged or update the pinned SHAs, rerun the
synthetic composition, require Linux/Windows and browser PASS, then
request a separate independent release review.
