# Fantasy HQ v2 — Brock Hard only

Read-only, iPhone-friendly Yahoo football dashboard for **Brock Hard & Tee Baggin**. Owner-merged [PR #183](https://github.com/P00NSMASHER/capturebrief/pull/183) is published on `gh-pages` at commit `36f0c75379078c1c28d39227774b8fe53cca0a93` (November 9, 2026 UTC). GitHub Pages deployment and the exact-source smoke checks completed successfully. This is a **released static dashboard**, not a live Yahoo connection.

## UI and privacy

- /capturebrief/fantasy/ and /capturebrief/fantasy/brock/ both open the Brock Hard dashboard directly.
- There are no other personal team cards or a league switcher. The bottom navigation switches **Overview, Lineup, Waivers, and Analysis** for Brock Hard only.
- Existing /quick/ and /highlight/ deep links redirect to /brock/ without rendering any other personal team. Only Brock is present in the released `fantasy/data.json` archive.
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

The fantasy CI also exercises Chrome rendering on /fantasy/ and /fantasy/brock/ and the fictional optimization fixture. The owner approved and completed publication of the Brock-only static site; future releases and live Yahoo OAuth/backend require separate approval.

## Automatic publisher (November 9, 2026)

The owner authorized publication of Brock Hard roster and matchup data on public GitHub Pages. This does not authorize exposing Yahoo credentials, authorization tokens, account emails, or other personal fantasy teams.

An enabled hourly ChatGPT task named Brock Hard | Auto Yahoo Data is configured to read only Brock's Yahoo league through the existing Flaim Fantasy connection and update only fantasy/data.json on gh-pages. Before writing it must validate league and team identity, current roster, week, scoring slots, standings, matchup, availability, timestamps and a safe schema-v3 output. Any failure must preserve the last verified capture. The initial Week 9 snapshot was manually verified and published November 9; unattended scheduled execution remains unverified until an actual run is observed.

The public site does not itself authenticate with Yahoo. On open, every five minutes while visible, and on Safari foreground return, the app checks the latest published JSON. It compares verified timestamps and automatically supersedes an older local private import. Header Refresh rechecks the published snapshot, not the Yahoo API. A failed, stale, wrong-team or incomplete snapshot cannot replace a newer verified capture.

Expect up to an hour between scheduled captures plus GitHub Pages build/caching delay; this is not continuous live scoring. The UI displays capture age. Missing future player projections stay null and projected lineup and waiver optimizers remain disabled.

Private JSON import remains an optional fallback. Never store passwords, Yahoo OAuth tokens, cookies, or private Flaim source envelopes in the repository.
