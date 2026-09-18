# Open-Source Provenance Ledger

This ledger is a gating artifact. No external code is incorporated into a production product until its exact revision, license obligations, dependencies, assets/data terms, and modifications are recorded here.

| Candidate | Intended use | Observed license | Pinned revision | Incorporation status | Required next check |
|---|---|---|---|---|---|
| blencorp/capture-mcp-server | SAM.gov + USASpending provider patterns for CaptureBrief | MIT | `e91ce243cd6a62e9c2a55609d34a187fca89703b` | NOT INCORPORATED | dependency/license audit; adapter-only design |
| EthanHNguyen/rfp-map | future API-key-free bulk discovery only | MIT | `5c046e1abb80f515951a0d1c8ebb20a95aeb46d3` | NOT INCORPORATED | HOLD for current core: normalized `responseDeadline` may fall back to ArchiveDate, `id` may fall back to solicitation/link/title, and description is truncated; do not use as controlling-source QA |
| pretorin-ai/simple-crm | govtech CRM/workspace infrastructure patterns | MIT | `276b5fd871663605138fce5486831a422368b130` | NOT INCORPORATED | auth/dependency audit; extract only needed modules |
| chakmarebel/federal-proposal-copilot | federal proposal/compliance workflow ideas | MIT | `fc8618e08d2bce924b412a22c2f0857beb3ceabf` | NOT INCORPORATED | separate methodology concepts from third-party marks/content; note upstream self-test warning in pinned commit |
| jmapb/nycaabs | NYC address/building/BIN/permit normalization patterns | MIT | `149c27b6a42d3dc33f77be8e7c2b84dcc227239c` | NOT INCORPORATED | dependency/data-source audit; extract only normalization patterns |
| ramos333oz/Municipal-Permit-Scraper | municipal permit adapter/scraper patterns | LICENSE file = MIT; README badge says ISC (inconsistent documentation) | `427d27e4506cea91a969e3f2e2e0ddc49a379c21` | NOT INCORPORATED | treat LICENSE file as controlling candidate but obtain/review dependency/data-source terms before reuse; do not rely on README badge |
| RantumBits/addressintel-mcp | permit/parcel/buildability adapter concepts | MIT | `e714e1451e80bdd64543ec3e374a5aa42f5681c7` | NOT INCORPORATED | external API/data terms; dependency audit |
| shreelathadev/construction-lead-agent | permit-to-commercial-lead classification concepts | MIT | `6015b1c54d8a559eb5c54a93140bdeda3681537d` | NOT INCORPORATED | inspect implementation depth/dependencies before reuse |
| cneuralnetwork/ScopeSignal | scope-change detection prototype | MIT | `d470659a009e9944fd6c4a7969a903dfc28c443e` | NOT INCORPORATED | dependency/asset audit; isolate validation MVP |
| helixzz/invoice-maid | document/email ingestion and extraction primitives | Apache-2.0 | `adc14c4c23c26b1b140066cdb0cb7119d5b227a4` | NOT INCORPORATED | NOTICE/patent/dependency audit; independently run claimed tests before reuse |
| jawwad-ali/chronosguard-compliance-rag | temporal evidence/security primitives | MIT | `acce7bc3726aec19096bbb2f3ab78ae17eed5edb` | NOT INCORPORATED | run test suite; isolate date-in-force model |
| tritaptheduc/logistics-freight-audit | freight discrepancy rules/analytics concepts | MIT | `635594f7bf541e4bb184872ba21c32535a01139c` | NOT INCORPORATED | inspect implementation depth and sample-data rights |

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
