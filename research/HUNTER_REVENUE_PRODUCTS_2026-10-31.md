# Revenue-products GitHub Hunter: 2026-10-31

Scope: CaptureBrief latest-active API observation integrity; zero customers, zero transactions, zero live network calls. This entry records a concrete integration and the separate candidate search. No inference of launch readiness or revenue.

## Reproducible issue and fix

The original `capturebrief_core/current_api.py::_nonnegative_int` called `int(value)` on SAM.gov pagination fields. In Python, `int(True) == 1`, `int(False) == 0`, `int(1.9) == 1` and `int(0.9) == 0`. Provider JSON like `{"totalRecords":1.9,"limit":1,"offset":0,"opportunitiesData":[...one row...]}` could therefore pass the complete-page check even though the actual count was not a valid integer. The same gap affected retained `validate_api_observation` receipts. Neither proves correct latest-active truth.

Repair: permit genuine JSON integers and whole-number decimal strings for compatibility; reject JSON booleans, floats and malformed strings before checking nonnegativity and completeness. No new dependency, network call, payment permission or customer-send authority. The existing strict first-party source boundary and source hashing remain unchanged.

Targeted synthetic regression: `tests/test_current_api_pagination_types.py`, covering fetch/retained-receipt booleans, fractional counts, decimal-string compatibility and missing/negative values. Product CI runs the full `python -m unittest discover -s tests -v` corpus on GitHub and requires Windows compatibility before merge. Results are not asserted until the exact PR head has independently passing GitHub checks.

## External GitHub source reconnaissance

Two source libraries and their exact license files were reviewed for solving the same strict-type verification problem:

1. [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema) [source type checker](https://github.com/python-jsonschema/jsonschema/blob/main/jsonschema/_types.py), [MIT-style COPYING](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) (observed COPYING Git blob `af9cfbdb134f42e5205ecbad597421d778826481`). Its integer-type checker explicitly excludes Python booleans, matching the needed principle. Not adopted because introducing a whole JSON Schema runtime to guard three scalar API fields adds needless dependencies and increases operational surface.
2. [pydantic/pydantic](https://github.com/pydantic/pydantic), [strict-type utilities](https://github.com/pydantic/pydantic/blob/main/pydantic/types.py), [MIT LICENSE](https://github.com/pydantic/pydantic/blob/main/LICENSE) (observed LICENSE Git blob `488c6260c10f2e88fa1fae58a63fccec8d600cd1`). Not adopted: strict model validation would require a nontrivial dependency and schema migration for a bounded compatibility-sensitive API function.

No external source bytes or new dependencies were copied, bundled or installed; no dependency-advisory audit was necessary for a non-adoption decision. Both candidates are reusable for larger future schema needs, subject to current version, advisories and dependency-license audit **at adoption time**. The code change is an independently written standard-library guard informed by the general strict-type validation concept.

## Division of labor / other product lane

The existing shared-lab [PR #883](https://github.com/P00NSMASHER/github-value-hunt-ledger/pull/883) owns bounded FY2027 SAM archive readback; [PR #889](https://github.com/P00NSMASHER/github-value-hunt-ledger/pull/889) owns RecoveryOS decimal-safe money rounding; [x402 factory PR #60](https://github.com/P00NSMASHER/x402-product-factory/pull/60) owns watchdog recovery durability. **No changes to any of those PR branches**: continue review/acceptance there before opening duplicate integrations. The next complementary Hunter B opportunity is to inspect deterministic reconciliation/idempotency at the boundary between original invoice source records and RecoveryOS settlements, preserving the other team's evidence ledger and source hashes.

## Engineering-time accounting and next checkpoint

Measured files changed: one Python validator, one targeted regression suite, this checkpoint. No measured engineer-hours saved or real customer-impact data available; do not invent either. Quality benefit is rejection of eight classes of false pagination metadata under two call paths, not an assertion of full historical-source verification.

Next action: read exact GitHub PR head and required CI checks; repair failures; merge only when all actual protection/approval gates permit, preserving explicit no-payment/no-send controls. Then choose the next real first-customer bottleneck or the non-overlapping RecoveryOS workstream.
