# CaptureBrief — private verified-order workbench (proposed, no deployment)

**Purpose:** connect operator-selected private CaptureBrief cases to authenticated
read-only Stripe Checkout observations, prevent duplicate registration, then
surface evidence-based research, delivery and targeted-watch readiness.

**Present state:** candidate-only. No real buyer, Checkout payment, revenue,
customer delivery, 14-day watch, or FY2027 full-history certification has been
established by the fictional tests in this branch. These commands do not
charge cards, refund money, send messages or release customer deliverables.

## Five-step local operator process

1. **Capture the incoming customer request securely.** Save only a reviewed
   CaptureBrief plaintext draft to the private `private-inbox` folder.
   Use the already installed `Preview-CaptureBrief-Private-Batch.cmd`, then
   `Start-CaptureBrief-Private-Batch.cmd`, then
   `Review-CaptureBrief-Private-Cases.cmd`. These create unverified intake
   cases, not paid orders or authenticated email sender records.
2. **Associate checkout safely.** Obtain the **exact Checkout Session ID**
   independently from the intended live Stripe Dashboard, rather than
   customer copy, a success URL or a claimed payment email.
   The preferred local operator action is to use the tested private association
   builder instead of hand-editing a JSON file:

   ```powershell
   py -3 scripts/save_private_checkout_association.py "$env:LOCALAPPDATA\CaptureBrief\private-cases\request-<the exact 64 lowercase hex>.case.json" --associations-dir "$env:LOCALAPPDATA\CaptureBrief\private-checkout-associations"
   ```

   It prompts for the independently obtained Checkout Session ID in the
   operator's terminal, validates the original case/receipt pair, prevents
   assigning the same Checkout ID to two cases, and atomically creates or
   reuses the corresponding private mapping. It does **not** access Stripe,
   assert payment, or identify/authenticate the buyer. Its console output
   includes opaque tags and false authority flags, not the Checkout ID.
   The optional `--session-id` argument is available for isolated tests,
   but using it with real IDs exposes them in command/process history and
   is not recommended. Noninteractive calls without an explicit ID block
   rather than guessing a provider reference.

   For environments that cannot run this helper, the exact JSON mapping
   contract below remains supported; review it carefully before processing.
 For a specific
   imported case `request-<64-byte hex>.case.json`, create a separate
   private text file `request-<the same hex>.order.json` in the existing
   `private-checkout-associations` folder:
   ```json
   {
     "schema": "capturebrief-private-checkout-association-v1",
     "request_sha256": "<same 64 lowercase hex characters>",
     "checkout_session_id": "cs_live_<the actual independently retrieved ID>"
   }
   ```
   The document is an **untrusted correlation request**; it never proves
   payment. Keep this file outside GitHub, Pages, ChatGPT or public storage.
   Do not invent identifiers or reuse a checkout session for two buyers.
3. **Run a no-network preview.** From the pinned candidate checkout:
   ```powershell
   py -3 scripts/process_private_order_queue.py --cases-dir "$env:LOCALAPPDATA\CaptureBrief\private-cases" --associations-dir "$env:LOCALAPPDATA\CaptureBrief\private-checkout-associations" --registry "$env:LOCALAPPDATA\CaptureBrief\private-orders\registry.sqlite"
   ```
   Preview parses associations, validates the original private case/receipt
   pair, identifies missing or duplicate candidates and reports only hashed
   opaque labels.
   **Unfinished or incorrectly named Checkout mappings are blocking items**:
   a `request-...` file with the wrong digest, a temporary
   `.order.json.tmp` or `.order.jsn` filename, an unexpectedly capitalized
   `Request-...` file, or a misnamed `*.order.json` is reported as
   `PRIVATE_ORDER_QUEUE_BLOCKED`, not misreported as an empty queue.
   Counts appear as `unexpected_association_entries` and
   `ignored_non_association_entries`. Ordinary `notes.txt` and unrelated
   PDFs are ignored; private filenames and provider identifiers stay out of
   CLI output. The preview never repairs, moves, deletes or accepts any file.
   An operator must review a malformed local association before invoking
   the authenticated execute path. It does **not** access Stripe, create a registry or
   authenticate the buyer.
4. **When operator-approved and a suitable LIVE read-only/restricted Stripe
   key is available locally, run an authenticated account check.**
   The key is read from the local environment
   `STRIPE_CAPTUREBRIEF_SECRET_KEY`. **Never put it in GitHub, a command
   argument, chat, mail, log file or example.** The command is the
   exact preview command above **plus `--execute`**. It makes only
   GET requests to the expected Stripe account for the Checkout Session,
   PaymentIntent and Charge, and checks the expected one-time USD 149
   payment link, buyer email consistency, capture, refunds and disputes.
   A record conflict cannot create or reassign an order. A later
   contradictory direct Stripe recheck places an *append-only review
   hold* on the previous order; a clean later check does not silently
   clear that hold. The registry is a private SQLite file. This does NOT
   authenticate the email sender or authorize work, delivery or a message.
5. **Review source/research/delivery/watch blockers separately:**
   ```powershell
   py -3 scripts/inspect_private_order_fulfillment.py --cases-dir "$env:LOCALAPPDATA\CaptureBrief\private-cases" --registry "$env:LOCALAPPDATA\CaptureBrief\private-orders\registry.sqlite"
   ```
   The dashboard reads the real fulfillment planner but never updates
   cases or promotes source evidence. It reports that the frozen approved
   archive catalog reaches only **FY2026**, so current FY2027 completeness,
   official source authentication, source byte checks and retention must
   be established separately. It refuses to describe an unverified customer
   intake as research complete, delivery verified or 14-day watch started.

## Test versus live semantics

- Offline tests inject fictional Stripe Checkout/Intent/Charge responses
  including `cs_live_TESTONLY`-style **synthetic placeholders**. This is
  permitted only inside explicit test code and is **not a live payment**.
  The operator CLI exposes NO synthetic-provider switch and requires
  an independent live provider read for an actual order attempt.
- Both the registry and fulfillment summaries deliberately avoid actual
  names, email addresses, opportunity URLs, card data, API keys and
  original raw case text. They contain only opaque tags, status codes,
  counts and last observation timestamps.
- Duplicate protection is exact case SHA plus unique Stripe Session and
  PaymentIntent. Semantically similar edited requests remain separate
  until a human confirms identity and required scope.
- A posted payment, a customer-supplied "Already purchased" claim, or a
  signed/hashed local copy cannot independently establish that the
  customer was authenticated, the project was accepted or a message
  may be sent.
- Payment-recheck alerts are a **one-way hold** until separately
  reconciled. This preserves the original paid observation rather
  than silently rewriting history or restoring a questionable order.
- No automated email polling, authenticated SMTP delivery, verified
  customer acceptance, complete FY2027 original archive collection,
  publisher attestation or independent second-device restore is
  established by the current candidate. Do not claim an active
  14-day customer watch without actual approved baseline and
  observed change cycles.

## Synthetic, repeatable acceptance

```powershell
py -3 -m unittest tests.test_payment_reconciliation tests.test_private_order_os tests.test_private_order_pipeline -v
py -3 scripts/run_private_order_acceptance.py
```

The pilot runner creates fictional customers and provider responses in
temporary storage. It proves the Preview → Import → Order Association →
Direct-GET-shaped Reconciliation → Duplicate-Safe Registration → Source
Review dashboard **as a synthetic flow**, then separately proves that a
frozen **golden demo case** can produce an integrity-verified delivery ZIP
and watch baseline at its historical test timestamp. These are
**different cases**. The fictional order is NOT treated as delivering
the golden demo's ZIP or starting its watch.

**Operational status:** User-facing release remains separate from this
candidate. Main/gh-pages merges, a real customer pilot, purchase
fulfillment, FY2027 catalog promotion and any off-device restore must
be independently evidenced before those claims can become true.
