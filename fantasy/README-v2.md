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


## Predictive Edge / AI competitive advantage (November 9, 2026)

**Why this is different from Yahoo's scoreboard.** The fifth Coach tab now includes an Edge Intelligence Lab that joins Brock Hard's verified Yahoo 2026 league/team roster and 25 saved available players with FantasyBot's explicit **Week 10** 2026 PPR player projections, recent scoring logs, trends and eight-club power ratings, plus the NFL's verified 2026 bye schedule. A dedicated pure-JS evaluator solves exact league-slot lineup assignments for cautious/balanced/upside risk modes; estimates the gain compared with the captured starters; computes *illustrative* uncertainty scenarios from short scored history; matches future-projected free agents only against players listed as available in this exact Yahoo league; evaluates hypothetical bench-add/drop one-week starting output; and detects scheduling weaknesses weeks in advance.

Source components are deliberately separated:
- \`fantasy/data.json\` — owner-authorized Yahoo/Flaim **Brock-only** core, owned and updated by the existing hourly ChatGPT task with its four-hour rate-limit governor. THIS FILE IS NOT EDITED BY THE Edge build.
- \`fantasy/edge.json\` — public sanitized forecast *sidecar*: input Week 10 projected PPR points and recent history for verified Brock roster player IDs, separately verified available-player projections and 8-team comparative power ratings, official NFL bye weeks, source timestamps and coverage. It includes no model API credentials or other owned fantasy team snapshots.
- \`fantasy/assets/edge-engine.mjs\` — deterministic, transparent decision math. The model is *FantasyBot's provider forecasts*, not a hidden OpenAI API call from GitHub Pages. Decisions compare the **actual saved Yahoo roster and legal slot eligibility** against projected one-week player points; 36-hour model TTL and Yahoo snapshot freshness protect the results.
- \`fantasy/assets/edge-view.mjs\` and \`edge-v1.css\` — mobile-first War Room UI, with independent identity validation, three risk toggles, quantified lineup options, Yahoo-confirmed acquisition hypotheses, opponent power ranks, future bye threats, trade leverage considerations and three-paragraph forecast assessment. Public site only fetches published static files; the controls never submit waiver claims, trades or lineup edits.

**Important predictions:** Official Week 10 Denver bye means a saved RB starter Jonah Coleman must be replaced; the exact slot optimizer may move an existing Flex RB into the RB position and substitute a WR into Flex, not necessarily a 1:1 RB swap. Both Brock Bowers (Raiders) and Mark Andrews (Ravens) are on official **Week 13** bye, leaving no rostered eligible TE unless another is acquired. Week 11 Rhamondre Stevenson (NE) is also on bye. FantasyBot rates Brock #1/8 while Jersey Junkyard is #3/8 in roster power even though Yahoo standings are a different ranking. These are evidence-backed strategic signals, not guessed point scores.

**Uncertainty/constraints:** FantasyBot projections are explicitly PPR, not verified adjustments for Yahoo custom bonuses. The model's volatility bands and any disclosed win-likelihood normal approximation are **uncalibrated scenario estimates** based on limited recent scoring history and an assumed opponent variance; not independently validated odds, wagering advice, Yahoo probabilities, guaranteed point gains or championship predictions. The exact hypothetical waiver uplift is a one-week substitution experiment, not a legality, future value or roster-transaction guarantee. Actual Yahoo player locks, future injuries, pending claim order and opponent full rosters are unknown. The public site and published predictions are visible to other managers: do not use public Edge if hiding strategy is a hard requirement; a private authenticated redesign would require separately authorized hosting/authentication.

**Refresh:** A separate, enabled ChatGPT task \`Brock Hard | Predictive Edge\` was created to update ONLY \`fantasy/edge.json\` after a fully revalidated FantasyBot 2026/Week N model read. It performs no new Yahoo/Flaim calls and does not modify the existing Yahoo task. If a provider is throttled, the identity/roster changes, or model data is incomplete, it preserves the last verified sidecar. The *static* webpage does not execute a GPT-6 LLM at runtime, live-read Yahoo, or generate new projections on each visit; only a new ChatGPT task run can publish a new model observation. Explicit \`edge.json\` source times, calendar dates and fail-closed model validation make staleness visible. The one-time Week 10 example must not be treated as permanently current.

**CI and security:** \`node --test fantasy/tests/*.test.mjs\` covers strict Brock Yahoo identity, player-ID and slot matches, no duplicated IDs, official bye forecasts, 2026 exact future week, 3 experimental risk modes, source-joined waiver candidates, invalid/stale/future clocks, missing projections, XSS escaping, private info exclusions, and zero Yahoo write paths. The existing premium mobile-browser fixture must additionally prove a working Coach Edge hero and risk toggles, Week 10 and Week 13 bye alerts, verified power/waiver displays and preserved historical Coach fallback. Before production: exact-head fantasy checks + site quality, same-PR merge, exact commit Pages build and a live public iPhone screen check.


## 2026 Future HUD and four-tab strategy

**Scope:** Brock Hard only. GitHub Pages hosts a public read-only five-tab fantasy interface. The existing hourly Yahoo publisher still writes only \`fantasy/data.json\`, and the separate daily Predictive Edge publisher still writes only \`fantasy/edge.json\`; neither scheduler is changed by this release.

**Source-backed additions:**
- \`fantasy/intelligence.json\` contains Yahoo 2026 league stat modifiers, eight standings teams, 32 finished head-to-head matchups (Weeks 1–8; 64 actual/projected team-score observations), four unresolved Week 9 matchups with Yahoo provider odds, and the complete eight-team weekly schedule for Weeks 10–14 (20 matchups). It deliberately excludes league-owner names, owner IDs, emails, raw envelopes, tokens and other personal fantasy teams.
- Verified player PPR scoring has 1 point per reception, standard offensive points and no reported offensive bonus thresholds. Yahoo K/DST special scoring rules are preserved, but the independent forecast feed doesn't expose each predicted FG, defensive yardage/points allowed bucket or special event, so these differences remain labeled uncalibrated rather than guessed.
- \`strategy-engine.mjs\` independently computes Yahoo preseason-score residuals: 18.8 mean absolute team-score points, 23.0 RMSE and 18/32 correct projected matchup winners. It bootstraps whole historical matchup error pairs rather than independently simulating each team from invented standard deviations. The conditional playoff scenarios simulate Week 9's undecided games using Yahoo estimated probabilities plus Weeks 10–14 team forecasts, testing both 4- and 6-team playoff fields under a hypothetical Week 14 regular-season end with wins then points-for tiebreak. Because Yahoo playoff field size, tie rules and true finish dates have not been verified, these are **conditional scenarios, not actual playoff qualification probabilities**.
- The Home tab prioritizes an actionable intelligence queue; Lineup leads with independent Week 10 PPR exact-slot assignment forecasts and real RB/FLEX movement, with score-first, minimum-change tie breaking; Players highlights actual roster-fit, source-verified available players and the shared Week 13 tight-end bye; League shows conditional playoff paths, contrasting Yahoo standings with FantasyBot power strength and five upcoming opponents. The prior provider details and all five navigation tabs remain accessible. The new evidence-source JSON remains read-only, and the page does not perform Yahoo OAuth, provider mutation, transactions, trade submissions or messages.
- The \`future-v1.css\` layer transforms **all five tabs** into a coherent lightweight midnight-blue futuristic HUD: restrained cyan/violet neon glows, tech-grid, compact data metrics, numbered priorities, translucent cards, full-color club crests, iPhone safe-area navigation and accessible reduced-motion support, with no remote fonts or trackers. Old CSS remains as a fallback.

**Integrity / longevity:** Dashboard analytics fail closed if source IDs, season or week no longer match, data is malformed, or critical source coverage is missing. Historical prediction reliability remains readable, but waiver action recommendations are withheld if Yahoo availability is more than six hours old. The league-intelligence artifact is a separately published evidence record and **does not automatically refresh just because the Yahoo roster task updates**. Future updates must refresh and verify the league-intelligence sidecar for new weeks, records, fixtures and trade inputs before claiming current playoff predictions.

**QA:** Unit/data QA covers 32 completed matchups, official stat modifiers, eight-team privacy, no guessed playoff settings, full roster identity, with ~five-minute browser acceptance for all five tabs, the exact mandatory flex-to-RB positional cascade, future HUD styles, 390px horizontal overflow, safe stale-data behaviors, and Chromium/WebKit website checks. Release only after exact-head checks, GitHub PR merge, exact-commit Pages success and independent public page observation.


## Genius Lab upgrade — November 10, 2026

This read-only upgrade adds two independently inspectable client-side modules:
- \`fantasy/assets/genius-engine.mjs\`: deterministic, bounded research calculations from the existing Brock Yahoo \`data.json\`, independent FantasyBot \`edge.json\`, and league-level \`intelligence.json\`.
- \`fantasy/assets/genius-widgets.mjs\` + \`genius-v1.css\`: user-facing decision cards and an interactive, explicitly hypothetical scenario lab in all five Fantasy HQ tabs.

**Historical measures** from Weeks 1–8: Every team is compared against all seven rivals each week (56 theoretical all-play games), allowing all-play win rates, average opponent scores, point-production volatility, rolling three-versus-five-week production, and "luck wins" = actual W–L wins minus all-play expected wins (descriptive, not causal). Uses only the 32 source-linked final Yahoo matchups; all eight team IDs must appear exactly once weekly. The sample has 64 verified Yahoo projected-versus-actual team-score observations.

**Walk-forward calibration**: For each held-out matchup in Weeks 4–8, train solely on earlier completed Yahoo weeks, using historical home-away forecast residual pairs and their reversals; smooth the forecast frequency by a 0.5-count correction. Report 20 genuinely held-out games, Brier score against 0.25 coinflip baseline, historical forecast mean absolute error, empirical margin deciles, and support counts. Small sample / paired matchups mean that these are not calibrated future probabilities, not claims of statistically proven forecasting advantage.

**Opponent exploitation / risk**: The Week 10 opponent-scouting view compares Yahoo team forecasts with prior observed team forecast errors, league-wide all-play strength, scoring volatility, and recent scoring biases. Yahoo team-total error and FantasyBot individual player predictions are kept separately labeled; the new engine does not claim they are directly exchangeable. Per-player risk signals use only modeled history, sourced matchup labels, Yahoo injury flags and independently verified NFL bye weeks, never guessed locks.

**Decision scenarios**: Coach now offers five explicit gain-realization assumptions (0%,25%,50%,75%,100%) and hypothetical playoff fields of 4 or 6. A deterministic, paired-error bootstrap uses the verified eight-team Week 9 undecided provider win probabilities, W10–14 source schedule and historical Yahoo forecast errors; simulations are matched on the same random draws between baseline and scenario and apply user-specified expected lineup improvement *only* to Week 10. The actual playoff field, season end, tiebreak and odds are not verified. The UI labels these conditional scenarios, not true playoff qualification forecasts. The model refuses invalid season, league, data grain, week or duplicate roster identities.

**Actionable roster protection**: Player/waiver views explicitly flag both rostered TE bye weeks in Week 13 and show only candidates appearing in Yahoo's own at-capture league-available pool. Named Woody Marks–Travis Kelce trade research is the user's supplied source-backed trade comparison plus source-verified counterpart need/surplus; market ratios are exploratory negotiation signals, never an acceptance guarantee or a trade transaction. Stale Yahoo captures turn off actionable recommendations but preserve historical research.

**Operational limits**: This is an evidence-driven on-device calculation layer and *does not* run an unrestricted LLM inside static GitHub Pages. It cannot guarantee a winning season, independently determine NFL injuries/live waiver legality, or calibrate multi-season statistical probabilities from 20 held-out games. The existing Yahoo and FantasyBot scheduled publisher scopes, timestamps, branches and automated task state are untouched; \`genius-engine.mjs\` and \`genius-widgets.mjs\` make no direct provider API requests. The previously published \`intelligence.json\` is itself a historical data source and needs a separately authorized verified refresh when the season week progresses; it never silently rolls forward.

**QA**: Dedicated pure tests verify out-of-sample training chronology, 8×8 all-play coverage, playoff field/realized-gain what-ifs, trade and bye evidence, malformed-source failures and the absence of private user-team leakage. Headless 390px browser acceptance clicks all five tabs, including every scenario control, and verifies key widgets, 20 held-out game labels, 8 crests, the original source-gated Coach panel, and no horizontal overflow. Reduced-motion styling and 44px targets are preserved. Release via exact-head tested PR and independent public GitHub Pages readback only.


## Focus-first UX cleanup — November 10, 2026

**Problem:** Successive model releases kept appending an entire new layer of Home/Lineup/Players/League/Coach panels without removing the prior versions. The same bye, waiver, strength and odds observations appeared multiple times. The main app also retained unused legacy renderers.

**New single-purpose information architecture:**
- **Home:** one ranked next decision and the Yahoo-captured matchup scoreboard. No duplicate all-play power table, lineup optimizer, and waiver panels.
- **Lineup:** exact legal-slot recommended changes, retained three Cautious/Balanced/Upside modes; saved starters and bench appear only in optional details. Private user-imported *complete* projection files still run the exact optimizer and are clearly labeled as private estimates.
- **Players:** the most important actual roster coverage gap, at most one sourced trade thought, and a collapsible Yahoo player pool with working position filters that stay expanded after selection. No parallel "top market owned," "on the radar" and duplicate waiver research cards.
- **League:** the only visible eight-team all-play/power comparison, with upcoming opponents and the 20-game walk-forward accuracy evidence. No repeated playoff simulation on this tab.
- **Coach:** one interactive conditional scenario with 0/25/50/75/100% modeled gain and a four- or six-team hypothetical field, followed by one three-paragraph coach assessment. The previous full-length Edge Lab, source-only Coach, five-card Genius and recapped Waivers sections are no longer stacked beneath it.

**Implementation:** \`focused-experience.mjs\` and \`focus-v1.css\` are the single presentation layer. The tested analytic engines and three independently sourced JSON files remain unchanged. \`app-v2.mjs\` was reduced from 46 KB to about 24 KB by dropping obsolete rendering functions. The iPhone script version is \`v=12\`; both canonical paths include focus CSS v1. The five-tab navigation, original eight crests, live-checked published snapshots, public/private import safety and read-only Yahoo policy remain intact.

**Safety:** All five tabs now enforce the same archived-data fallback when the published Yahoo capture is too old, even if an independent model was more recently verified. Historic performance evidence remains available as a clearly dated archive. No current waiver, transaction or start/sit action is inferred from old Yahoo data. Position filtering preserves its expanded player pool; all untrusted strings are escaped.

**Acceptance:** An iPhone 390px browser test requires exactly one primary intelligence panel per tab, no legacy stacked analytic panels, an actionable Home CTA, legal RB/FLEX sequence, three actual risk modes, 25 Yahoo-listed player entries and persistent filters, eight unique team crests, 20 held-out model samples, functioning conditional scenarios, three final coach paragraphs, zero other owned teams, and no horizontal overflow. A separate five-tab archived-source browser test enforces the no-current-recommendation gate. Existing snapshot import, automatic refresh, and engine tests remain mandatory.

## Four-job decision console (November 10, 2026)

The production interface now has four distinct jobs: **Today, Lineup, Market and League**. The prior Coach tab was removed from navigation because it repeated the same lineup, waiver and season evidence in prose. Its pure evidence engines remain in the repository for historical tests and future source-aligned use; no provider or roster mutation was added.

Today no longer repeats the stale Week 10 scoreboard. It selects the highest-priority source-backed item available from either the source-checked league model or the newer Week 11 Edge model, then shows only verified record/rank/point differential and collapsible future team matchups. With the currently published artifacts, that correctly surfaces the verified Week 11 Rhamondre Stevenson bye instead of suppressing it merely because the older league-intelligence sidecar is from another week.

When the advanced all-play artifact does not match the current data week, League falls back to the separately captured Yahoo standings and team-level upcoming forecasts and labels the unavailable historical comparison. It does not upgrade those team totals into player projections, win probabilities or lineup advice. Lineup optimization still fails closed when individual coverage is incomplete.

Focused acceptance covers the current production artifacts at 390px and 1280px, all four navigation destinations, no horizontal overflow, no browser errors, the current priority, and the verified League fallback.

The test evidence is now deliberately separated. `npm run test:historical` from `fantasy/` runs deterministic engine tests against the frozen, internally coherent Week 9 Yahoo / Week 10 model bundle from commit `2dc063e`; those fixtures are never publication inputs. `npm run test:publication` reads today's actual `data.json`, `edge.json`, and `intelligence.json` and requires their truthful mixed-week contract: the Week 11 Rhamondre Stevenson bye remains visible, exact lineup optimization is unavailable without complete eligible-player projections, and the older league intelligence is rejected rather than relabeled current. `npm test` remains the complete regression suite.
