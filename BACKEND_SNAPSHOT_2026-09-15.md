# CaptureBrief Backend Snapshot — 2026-09-15

Authoritative artifact located in the user's Library:

`CaptureBrief_Backend_Deploy_Ready_2026-09-15.zip`

SHA-256:

`a8a147371ac95ec69f3e8f7473b2379f1b74183ef1e4675af9cd5e8f35b1850d`

Local verification on 2026-09-18:

```
43 passed, 19 subtests passed
```

Verified modules in the release bundle:
- `capturebrief_evidence.py`
- `entitlement_ledger.py`
- `job_queue.py`
- `source_budget.py`
- `webhook_boundary.py`

Verified tests:
- `tests/test_entitlement.py`
- `tests/test_evidence.py`
- `tests/test_job_queue.py`
- `tests/test_source_budget.py`
- `tests/test_webhook_boundary.py`

Release documentation:
- `README.md`
- `RELEASE_MANIFEST.md`
- `DEPLOYMENT_NOTES.md`

## Status
The artifact is the current verified backend source snapshot for consolidation work. The public CaptureBrief repository still primarily contains the static site, so source consolidation remains P0.

## Next source-control step
Unpack these modules into a normal `backend/` source tree on an implementation branch, preserve the verified tests, and rerun them from a clean checkout before any open-source provider adapter is enabled.

No upstream open-source code has been incorporated into this snapshot.