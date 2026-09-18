# Open-Source Provenance Ledger

This ledger is a gating artifact. No external code is incorporated into a production product until its exact revision, license obligations, dependencies, assets/data terms, and modifications are recorded here.

| Candidate | Intended use | Observed license | Adoption status | Incorporation status | Required next check |
|---|---|---|---|---|---|
| blencorp/capture-mcp-server | SAM.gov + USASpending provider patterns for CaptureBrief | MIT | reviewed | NOT INCORPORATED | pin commit; dependency/license audit; adapter-only design |
| EthanHNguyen/rfp-map | bulk SAM opportunity ingestion/discovery patterns | MIT | reviewed | NOT INCORPORATED | pin commit; confirm bulk data terms; isolate ingestion logic |
| pretorin-ai/simple-crm | govtech CRM/workspace infrastructure patterns | MIT | reviewed | NOT INCORPORATED | pin commit; auth/dependency audit; extract only needed modules |
| chakmarebel/federal-proposal-copilot | federal proposal/compliance workflow ideas | MIT | reviewed | NOT INCORPORATED | pin commit; separate methodology concepts from third-party marks/content |
| jmapb/nycaabs | NYC address/building/BIN/permit normalization patterns | permissive candidate from prior research | reviewed conceptually | NOT INCORPORATED | verify repository license + pin commit before any reuse |
| ramos333oz/Municipal-Permit-Scraper | municipal permit adapter/scraper patterns | license metadata requires reconciliation | reviewed | NOT INCORPORATED | resolve LICENSE-vs-README mismatch; pin commit |
| RantumBits/addressintel-mcp | permit/parcel/buildability adapter concepts | MIT | reviewed | NOT INCORPORATED | pin commit; external API/data terms |
| shreelathadev/construction-lead-agent | permit-to-commercial-lead classification concepts | MIT | reviewed | NOT INCORPORATED | pin commit; inspect implementation depth |
| cneuralnetwork/ScopeSignal | scope-change detection prototype | MIT | reviewed | NOT INCORPORATED | pin commit; dependency/asset audit; isolate validation MVP |
| helixzz/invoice-maid | document/email ingestion and extraction primitives | Apache-2.0 | reviewed | NOT INCORPORATED | pin commit; NOTICE/patent/dependency audit; test claimed coverage |
| jawwad-ali/chronosguard-compliance-rag | temporal evidence/security primitives | MIT | reviewed | NOT INCORPORATED | pin commit; verify test suite; isolate date-in-force model |
| tritaptheduc/logistics-freight-audit | freight discrepancy rules/analytics concepts | MIT | reviewed conceptually | NOT INCORPORATED | pin commit; inspect code depth and sample-data rights |

## Incorporation checklist
For every adopted component:
- repository + exact commit SHA;
- LICENSE and NOTICE copied as required;
- dependency SBOM/license scan;
- data/API terms reviewed separately from code license;
- trademarks/branding removed unless independently permitted;
- imported files listed;
- local modifications documented;
- regression/security tests added;
- provenance retained in release artifacts.

## Proprietary boundary
Open-source components may provide ingestion, normalization, storage, workflow, or generic analysis primitives. The proprietary product layer should remain the customer-specific decision logic, evidence synthesis, reliability controls, product UX, commercial scoring, workflow integration, and accumulated outcome data.