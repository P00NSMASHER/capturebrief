# CaptureBrief simulated pilot

**Status:** PASS

> This is a deterministic validation exercise using fictional customer numbers. It is not real customer evidence, revenue, conversion data, or a market forecast.

## Pilot coverage

- 12 fictional customer records tested
- 6 accepted for human review
- 4 direct-checkout records correctly routed to refund before work
- 2 scope-first records correctly declined before payment
- 7 buyer-safe files built in the golden delivery check

## Direct-checkout stress route

The intentionally failure-heavy mix sent 8 fictional buyers through direct checkout: 4 passed intake and 4 triggered the pre-work refund rule. The scope-first route tested 4 more records: 2 passed and 2 were stopped before payment.

These ratios are test coverage, not expected conversion or refund rates.

## Hardening decisions

- Expose direct checkout while retaining the free pre-purchase scope check.
- Promise a full refund when a paid request is declined before work begins.
- Require public-only confirmation and no more than five distinct assumptions.
- Accept customer-facing PASS and normalize the legacy NO-GO label.
- Never treat payment, intake, or a built bundle as authority to send or decide for the buyer.

## Customer matrix

| Customer number | Route | Expected | Actual |
|---|---|---|---|
| SIM-CUST-001 | DIRECT_CHECKOUT | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-002 | DIRECT_CHECKOUT | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-003 | DIRECT_CHECKOUT | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-004 | DIRECT_CHECKOUT | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-005 | SCOPE_FIRST | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-006 | SCOPE_FIRST | ACCEPTED_FOR_REVIEW | ACCEPTED_FOR_REVIEW |
| SIM-CUST-007 | DIRECT_CHECKOUT | REFUND_BEFORE_WORK | REFUND_BEFORE_WORK |
| SIM-CUST-008 | DIRECT_CHECKOUT | REFUND_BEFORE_WORK | REFUND_BEFORE_WORK |
| SIM-CUST-009 | DIRECT_CHECKOUT | REFUND_BEFORE_WORK | REFUND_BEFORE_WORK |
| SIM-CUST-010 | SCOPE_FIRST | DECLINED_BEFORE_PAYMENT | DECLINED_BEFORE_PAYMENT |
| SIM-CUST-011 | SCOPE_FIRST | DECLINED_BEFORE_PAYMENT | DECLINED_BEFORE_PAYMENT |
| SIM-CUST-012 | DIRECT_CHECKOUT | REFUND_BEFORE_WORK | REFUND_BEFORE_WORK |

## Delivery safety check

The golden fixture built a `READY_FOR_HUMAN_RELEASE` bundle with a `TRACE_COMPLETE` trace. The bundle excludes the raw case and restricted source bytes, and it does not authorize an external send.
