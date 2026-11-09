# Fantasy HQ v2 — Brock Hard only

Read-only, iPhone-friendly Yahoo football dashboard for **Brock Hard & Tee Baggin**. The existing PR #183 targets gh-pages and remains a **draft**. No public deployment is authorized.

## UI and privacy

- /capturebrief/fantasy/ and /capturebrief/fantasy/brock/ both open the Brock Hard dashboard directly.
- There are no other personal team cards or a league switcher. The bottom navigation switches **Overview, Lineup, Waivers, and Analysis** for Brock Hard only.
- Existing /quick/ and /highlight/ deep links redirect to /brock/ without rendering any other personal team. Only Brock is present in the draft branch's fantasy/data.json archive.
- Historical legacy or private snapshots containing multiple teams are filtered to teams.brock before normalization, browser storage, and display. Old cached copies are filtered on next load. Never commit private Yahoo data to the public repository.
- Original browser import remains schemaVersion 3 and 2 MB maximum. No file upload occurs. Refresh checks published static JSON and **does not contact Yahoo**. Fallback preserves previously verified Brock data.

## Analysis safeguards

- Exact lineup optimization and projected waiver uplift require complete, currently verified individual player projections, eligibility, and league lineup settings. Without that evidence, rankings fail closed.
- Reported Yahoo points are **scored points, not future player projections**.
- Yahoo matchup projections can be pregame estimates below current scores; do not mistake those for live final projection. Yahoo win chance may be provided independently.
- Yahoo-wide percentOwned is a platform-wide market rate, never ownership within this league. Yahoo waiverDate is only a date and does not establish waiver clearance time.
- No lineup submissions, claims, transactions, or trades.

## Current data and future provider access

The static fantasy/data.json is an archived September 30, 2026 capture, now limited to Brock only. The existing Flaim Fantasy connection can read owner-authorized Brock data on demand and make a Brock-only private v3 file. The adapter at fantasy/adapter/flaim-private-v3.mjs accepts only the mapped Brock league/team and never emits other teams. Synthetic fixtures are distinctly labelled and deliberately archived.

For **automatic** Yahoo refresh, obtain API application approval first, then separately obtain owner consent before enabling OAuth, adding secure hosting, handling credentials, changing the published site, or incurring costs. There is currently **no live synchronization** in the static site.

## Verification

Run node --check for fantasy/assets/engine.mjs, fantasy/assets/app-v2.mjs and fantasy/adapter/flaim-private-v3.mjs. Then run node --test fantasy/tests/*.test.mjs.

The fantasy CI also exercises Chrome rendering on /fantasy/ and /fantasy/brock/ and the fictional optimization fixture. Do not merge or publish without explicit owner approval.
