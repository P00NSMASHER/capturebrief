# Historical-award context: source-bound operator research candidate

**Status:** engineering candidate, not a production launch, customer-ready competitor report, incumbent determination, or verified live USAspending integration.

## Problem and paid decision
CaptureBrief sells a supervised, source-backed $149 one-pursuit assumption check. A pursuit team often asks whether an existing contractor, agency spend trend, or approximate incumbent budget justifies a GO/HOLD/PASS decision. A broad keyword match or top 25 unfiltered awards can mislead buyers, so the review must distinguish **prior-award hints** from an **identified incumbent or a pursuit-specific decision**.

This proposed optional step produces a bounded *prior-award context* side note to support a reviewer. It cannot change the buyer's assumption state, certify a specific incumbent, establish a bidder's eligibility, or directly update the signed Decision Evidence / delivery bundle.

## Official source contract

Official USAspending API: `https://api.usaspending.gov/api/v2/search/spending_by_award/` (POST). Contract documentation:
- https://api.usaspending.gov/docs/intro-tutorial
- https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_award.md
- https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/search_filters.md

The bounded request is produced by `capturebrief_core.award_context.approved_request`: contract award codes A/B/C/D; **exact reviewed top-tier awarding agency name**; optional exact six-digit NAICS; bounded date range; page 1; <=25 rows; base obligation date descending; documented `Award ID`, `Recipient Name`, `Awarding Agency Code`, `Awarding Agency`, `Base Obligation Date`, `Award Amount`, `NAICS`, and `generated_internal_id` fields. A broad federal top-N search is not an acceptable answer to an agency-specific question.

In the operator's separate authorized/private workspace only:
1. Obtain a genuine first-party source response and retain its original request and response bytes plus independently authenticated transport, observation time, and SHA-256. This implementation **does not perform network operations**, attest to HTTP provenance, or store credentials.
2. Verify the exact issued request with `approved_request` and analyze the locally held UTF-8 JSON bytes with `evaluate_award_context(request_bytes, response_bytes, observed_at=..., pursuit_as_of=..., target_agency_code=..., target_agency_name=..., target_naics=...)`.
3. Independently confirm the agency identity mapping, action dates, supplemental award modifications, award/IDV type, and (only if applicable) procurement lineage to the buyer's **exact solicitation**. This code does not claim any of those links.
4. Human reviewer may cite the sources as *research leads* in a separate work queue; unsupported linkage stays `PRIOR_AWARD_CONTEXT_REVIEW_ONLY`, **never "incumbent confirmed"**. Do not place unverified research results into the signed paid customer delivery or a sales claim.

## Explicit boundaries

- A matching agency/NAICS award is **not automatically the incumbent** and is not independently tied to the exact pursuit.
- Current USAspending totals may include later modifications, so a current response cannot reconstruct what was known as of an earlier solicitation date. The code distinguishes `RETROSPECTIVE_ONLY_NO_AS_OF_CLAIM` from contemporaneous observations.
- Incomplete pagination, source warnings, duplicate IDs, wrong agency or NAICS, missing IDs or awardees, and future-dated obligation rows cannot silently establish complete market coverage or win likelihood.
- `Award Amount` is not cash already paid or a buyer saving. One page is not the whole historical population. A source hash proves byte integrity, **not** independent official-HTTP authenticity.
- Keep all original requests/responses, public recipient-level results, buyer profiles and working papers in approved protected storage; do not commit them, write them to GitHub Actions logs, expose them on the Netlify site, or e-mail automatically.
- This is read-only and offline, with no key use, spend, customer contact, price change, trial activation, or production scoring modification.

## Local adversarial checks

```bash
python -m unittest tests.test_award_context -v
```

The complete Product Core Linux/Windows workflow also discovers this suite. No live USAspending response or paid customer accuracy is claimed from these tests.

**Release and pricing rule:** Do not advertise prior-award incumbent intelligence until a genuine source retrieval, verified opportunity linkage and a customer-relevant finding are independently accepted. CaptureBrief's $149 supervised decision QA offer is a hypothesis to test with actual paid deliveries and buyer feedback, not proven ROI or automatic recurring revenue.
