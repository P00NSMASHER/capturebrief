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

## November 9 verified analytics repair

The Brock Hard-only interface now derives Yahoo roster status alerts from the captured player flags instead of treating an absent manual alerts array as a healthy roster. When future player forecasts are unavailable, the lineup tab shows an exact highest-scoring-combination comparison using **already scored week-to-date** points, explicitly labelled retrospective and never as start/sit advice. Waiver scouting ranks captured league-available players by *Yahoo-wide* roster rate only; it does not imply projected add/drop gains.

The Analysis tab shows saved Yahoo league rank, record, points for/against, and, when available, strictly Brock-only upcoming matchups with provider **team-level pregame forecasts**. A separate `analysisAsOfIso` preserves the observation time independently from the original core roster capture. The trade section reports verifiable Brock roster depth without pretending to value other teams or future performance. Full-season playoff odds, player-level optimization, and fair-value trades remain gated until their missing supporting evidence exists. Published captures older than six hours retain the original archive-only safety fallback, with explicit age warnings and a private import option; stale roster advice is not presented as current.

All source enrichment must fail closed on wrong identity/week, missing counts or player IDs, non-finite stats, and privacy fields. Existing automatic publication remains a separate read-only ChatGPT task; no extra OAuth backend, paid API, GitHub Actions publisher, roster transaction, or private-team navigation was introduced by this change.


## Premium league design — November 9, 2026

**User experience:** the four-tab Brock Hard application now presents Home, Lineup, Players and League with a touch-friendly native-app layout, high-contrast glossy navy/teal components, and an iPhone-safe bottom navigation. The Home screen prioritizes the current captured matchup, verified record/rank, near-term Yahoo team-level opponent forecasts, a short available-player list, and source-backed player status. The Lineup screen retains the exact scored-points retrospective explanation without rebranding it as a future prediction. The Players screen includes working QB/RB/WR/TE/K/DEF filter chips, Yahoo-wide roster-rate rankings and clear acquisition states. The League screen shows all eight verified league team identities, Brock-only standings metrics, upcoming opponents and completed Brock transactions.

**Crests:** \`assets/league-branding.mjs\` provides eight distinct *original SVG mascot crest illustrations*, rendered inline and accessible at all screen sizes. These are visual replacements for initials, **not claims to be the Yahoo-uploaded logos**: the existing Flaim snapshots do not include those original team image files. If authoritative image URLs become available, replace the corresponding crest with verified owner-supplied assets rather than scraping logins or guessing. No third-party image host, custom font or tracking service is used.

**Technical boundaries:** no provider account or another owned fantasy league is read by the visual UI. The hourly ChatGPT publisher still writes only \`fantasy/data.json\`; this redesign does not alter its credentials, schedule or quota governor. All future individual player projections remain null. Authenticated Yahoo operations, claim, trades, roster changes and alleged live streaming remain unavailable in the static app. The premium stylesheet is additive to the prior visual CSS, so regression-gated analytical functionality remains intact.

**Verification:** run \`node --test fantasy/tests/*.test.mjs\` and the Fantasy HQ GitHub CI that renders Home/brock, synthetic optimizer, private import, automatic snapshot supersession, and premium interaction acceptance at mobile width. Review all screenshot artifacts (Home, Lineup, Players, League, desktop) before a protected or owner-approved delivery. Validate exact Pages deployment and inspect the public HTML after merge.


## Fifth tab: Brock Hard Coach (November 9, 2026)

The **Coach** tab provides a simple, prioritized, explainable game plan derived from the existing, owner-authorized **Brock-only** Yahoo 2026 schema-v3 snapshot. It contains: team and league-position insights; flagged starting-player checks; an exact scored-points **retrospective** comparison (never mislabeled as a next-week projection); waiver scouting for verified positional gaps and league-available players; conservative trade strategy that explicitly withholds unsupported player-for-player deals; and playoff-preparation checks based on saved Yahoo team-level forecasts and verifiable roster coverage.

Implementation is split into the pure, tested \`fantasy/assets/coach-engine.mjs\`, a five-tab view in \`fantasy/assets/app-v2.mjs\`, and responsive \`fantasy/assets/coach-v1.css\`. Coach automatically recomputes from the selected local or published snapshot, with no new network or third-party APIs. Action buttons navigate to **Lineup**, **Players** (with a working QB filter), or **League**. They never submit adds, drops, trades, claims, or lineup edits.

**Reliability / provenance:** Only season 2026, league \`470.l.290846\`, team \`2\`, and a unique-ID roster pass. If the capture is more than six hours old (or future/malformed), the Coach engine returns no actionable recommendations; the app's existing archived-snapshot safety fallback stays in place. Player status is Yahoo-at-capture, not a fresh injury report. Waiver candidates are confirmed league-available **at capture**; Yahoo-wide roster percentages are not player projections. The top future-matchup margin uses only saved Yahoo *team-level pregame projections*. No playoff-clinch or probability calculation, guaranteed acquisition, lock-time inference, or invented trade valuation is made. Names and other potentially untrusted snapshot text are HTML-escaped in display.

This is an evidence-based **static decision-support module**, not a model running persistently in the browser or an authenticated Yahoo manager. Accurate start/sit optimizers, actual named trade packages, and postseason odds require separately verified full forward player projections, player locks, opponent rosters/valuations, remaining schedule, and league playoff rules. The existing recurring Brock publisher remains enabled and unchanged, including its rate-limit governor; it continues to write only \`fantasy/data.json\`.

Regression requirements: \`node --test fantasy/tests/*.test.mjs\`, exact-head Fantasy HQ CI with headless mobile Chrome, premium five-tab browser acceptance including Coach→Players QB filter, and a Coach screenshot artifact. Test missing identities, stale/future clocks, absent market/standings, missing forward projections, and no other owned-team leaks. Inspect successful GitHub Pages commit delivery before calling the feature live.


## Coach presentation refresh — November 9, 2026

The fifth Coach tab now presents evidence-backed lineup, waiver, trade, playoff, and league insights as concise **bullet lists** instead of long paragraphs. Each card retains its existing source reasoning and CTA, and the card's verified sentences are split into individual accessible \`<li>\` elements. The first-screen priority list, QB filter navigation, read-only Yahoo behavior, and all source-identity/freshness gates remain unchanged.

At the end of the Coach tab, a new **Coach’s final assessment** contains exactly three substantial paragraphs: (1) verified season record/standing and points differential; (2) Yahoo-at-capture roster status, QB depth and measured waiver/trade considerations; and (3) the closest saved upcoming matchup and disciplined playoff preparation. The summary is generated deterministically from the same sanitized Brock-only snapshot by \`writeCoachSummary\` in \`coach-engine.mjs\`; it never calls external AI, Yahoo, or another team, and never claims a clinched playoff spot, verified future-player projections, a specific trade value, or continuous live scoring. If source details are missing, the relevant paragraph says they are not verified rather than inventing values.

The update adds responsive list and recap styles to \`coach-v1.css\`, browser checks for the recap's three-paragraph count and placement after the five insight categories, and regression tests for accurate factual details, missing-data behavior, safe bullets, and the unchanged stale-capture refusal to provide actionable advice. For an archived snapshot, the Coach tab now shows only a prominently dated, **historical** three-paragraph recap without any move recommendations; the original current-data archive warning and refresh control remain visible. The dedicated archived browser acceptance confirms that all actionable Coach cards remain hidden. Safari-busting asset versions changed to Coach CSS v2 and app JS v7. The recurring Yahoo task and \`fantasy/data.json\` are not changed by this redesign.
