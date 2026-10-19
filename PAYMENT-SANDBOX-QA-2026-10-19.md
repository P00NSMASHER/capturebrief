# CaptureBrief first-pilot payments — sandbox QA receipt (2026-10-19)

**NO REAL MONEY AND NO CUSTOMER.** This is a connector/Stripe-hosted end-to-end test of one $149.00 transaction, a processor read, and a full refund. It is not a live paid customer or verified operational intake.

## Environment and account

- Stripe: CaptureBrief sandbox, acct_1UItcyDpIBzr6NyS (livemode = false)
- Test checkout Session: cs_test_a1ZhfI6gjb5PCMvRPqjXLrQSiaWg74qh6pfjj0AITTmjzmHmauT8srU3tR
- Sandbox QA order reference: CB-QA-SANDBOX-20261019
- Amount: USD 149.00 one-time, no subscription
- Fictional test card ending 4242; no real payment instrument
- No email sent by CaptureBrief; production payment link unchanged.

## Independently read back from Stripe sandbox API

1. Created a Session with livemode=false, status=open and payment_status=unpaid.
2. Browser verified Stripe TEST MODE and completed one fake card payment. Browser followed the configured success redirect. The destination web preview encountered ERR_TUNNEL_CONNECTION_FAILED; this did not invalidate the Stripe payment result.
3. Read Checkout Session directly from the same CaptureBrief sandbox account: status=complete, payment_status=paid, amount_total=14900, currency=usd, payment_intent=pi_3US8gqDpIBzr6NyS212nSGoe.
4. Independently retrieved PaymentIntent: status=succeeded, amount=14900, amount_received=14900, latest_charge=ch_3US8gqDpIBzr6NyS2GN82u08.
5. Executed one full sandbox refund: re_3US8gqDpIBzr6NyS22rFtlzi, status=succeeded, amount=14900, currency=usd.
6. Independently retrieved original Charge: refunded=true, amount_refunded=14900, paid=true, captured=true.
7. Independently retrieved Refund; status=succeeded, matching PaymentIntent and Charge.

**Sandbox verdict: $149 test transaction and full refund PASS.** No live charge, live buyer, settlement, revenue, customer delivery, or bank transfer occurred.

## Core payment reconciliation change — PR #55

The new CaptureBrief payment reconciler requires real Checkout Session, PaymentIntent and Charge from the exact CaptureBrief LIVE account and approved Payment Link, amount USD 149.00, matching buyer email, succeeded/captured charge, and no refund/dispute. It correctly rejects the above sandbox Session as evidence of a live payment.

The local operator CLI only uses authenticated direct GET requests with a locally available live Stripe secret/restricted key and verifies exact account ID before accessing payment records. It refuses redirects, saves a redacted private receipt, and never transmits email or authorizes fulfillment. No customer data or credentials are committed here.

## Still unverified for launch

- Receipt and authentication of a REAL customer request in the controlled inbox.
- Any actual live successful customer payment and written accepted scope.
- Genuine reviewed-source case and customer delivery.
- Real fresh source monitoring over the 14-day service interval.
- Independent code review and protected production release.

Do not represent sandbox operations as real sales, revenue or paid-customer acceptance.
