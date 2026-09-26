# Technical Reserve — Invoice Maid + ChronosGuard

Portfolio capacity cap: 10%.

Purpose: harvest reusable infrastructure for priority products and experiments. This is NOT authorization to launch two additional businesses.

## A. Invoice Maid reserve

Pinned upstream:
`helixzz/invoice-maid@adc14c4c23c26b1b140066cdb0cb7119d5b227a4` (Apache-2.0).

Concrete reusable seams observed in the pinned repository:
- `backend/app/models/extraction_log.py` — extraction/audit trail;
- `backend/app/models/correction_log.py` — human correction history;
- `backend/app/tasks/scheduler.py` — post-save event/webhook path;
- `backend/app/api/scan.py` — scan telemetry/outcome aggregation;
- `backend/app/services/scrapers/base.py` — pluggable source ingestion boundary;
- invoice model/API/export/search primitives elsewhere in the backend.

### Proposed internal primitive: Document Intake Service

```
Source
  -> ingest
  -> classify
  -> deterministic parse
  -> optional model enrichment
  -> confidence/evidence
  -> dedupe
  -> human correction
  -> audit log
  -> signed downstream event
```

Candidate consumers:
- CaptureBrief solicitation/attachment intake;
- freight invoices and rate documents;
- future compliance/policy inputs;
- PermitPlate source-document enrichment only where documents are actually needed.

### Do not import wholesale
Before any code reuse:
- preserve Apache-2.0 LICENSE/NOTICE obligations;
- dependency/SBOM review;
- test the relevant module independently;
- strip product-specific Chinese VAT/SaaS portal assumptions from generic interfaces;
- keep customer/product decision logic outside the generic ingestion layer.

## B. ChronosGuard reserve

Pinned upstream:
`jawwad-ali/chronosguard-compliance-rag@acce7bc3726aec19096bbb2f3ab78ae17eed5edb` (MIT).

Reusable architectural ideas observed:
- effective/expiration-date model rather than a stale active boolean;
- a single date-in-force retrieval path;
- source-backed findings with verified quotations;
- insufficient-evidence state instead of false compliance;
- Postgres row-level tenant isolation;
- durable background jobs with leases/retries;
- ingestion quarantine for suspicious/unsupported documents;
- prompt-injection-aware document handling;
- version retention for historical audits.

### Proposed internal primitive: Temporal Evidence Engine

Input:
- corpus;
- document/version metadata;
- as-of date;
- query/claim.

Output:
- applicable sources;
- expired/future sources;
- exact verified quotations;
- conflicts;
- evidence gaps;
- provenance.

### Candidate consumers
- CaptureBrief amendment/supersession analysis;
- policy/compliance products only after a narrow vertical is validated;
- any future workflow where "what was true on date X?" matters.

## Promotion rule
A reserve component only earns implementation capacity when:
1. a priority product or validated experiment needs it;
2. its pinned upstream revision and dependencies pass audit;
3. adopting it saves more effort/risk than implementing the small needed interface ourselves.

No standalone Invoice Maid or ChronosGuard product is scheduled in this portfolio cycle.
