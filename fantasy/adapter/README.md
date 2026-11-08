# Private Yahoo snapshot adapter (prototype, NOT an automatic sync)

This is a standalone, testable read-only bridge for Fantasy HQ v2 PR #183. It is not loaded by the public site, is not deployed, and contains no authentication implementation, credentials, Yahoo API requests, or private responses. It never executes waiver transactions or lineup moves.

## Preferred no-new-OAuth path

The owner already has an authorized Flaim Fantasy connection that can read the three requested 2026 Yahoo teams. This path requires no newly deployed service. Flaim is accessible through ChatGPT, not as a live API endpoint on GitHub Pages. The adapter accepts privately assembled response envelopes and produces a schemaVersion 3 object for the existing browser-local 2 MB importer. This is a MANUAL, provider-backed snapshot, not continuous background refresh.

Collect these five read-only responses for each team via the already authorized connector: league settings, current own-team roster, current-week matchups, standings, and a bounded league-specific available-player list. Use the season and league/team keys provided by the current authenticated session. Each packet is an object with league, roster, matchups, standings, freeAgents properties. Each property must hold the connector result envelope with success:true and data. Do not extract OAuth credentials.

The private input object contains seasonYear:2026, capturedAtIso (UTC time after the last provider response), and two maps keyed brock, quick, highlight:
- teamMap: for each ID, the owner-authorized target leagueKey and teamId.
- teams: for each ID, its five read-only source packets.

Call buildPrivateV3(input, {previous, nowIso}) after a capture, or refreshWithReader({readLeague,teamMap,previous,clock}) with an injected authorized provider reader. The latter only coordinates reads; NO provider implementation is included. Only when ok:true should the caller save JSON.stringify(result.snapshot) to an OWNER-PRIVATE file outside the public repository. Import that file using "Import private JSON" in Fantasy HQ v2 once it is explicitly published after owner approval. Do not persist a failed response; the function returns the unchanged prior verified snapshot.

Provider-reported points are actual scored points, not future projections. The adapter deliberately sets projectionCoverage:none, all roster and free-agent projections to null, and never fabricates a projection model. Thus lineup optimization, projected waiver gains and playoff scenarios remain unavailable until independently justified evidence exists. Yahoo pregame projected MATCHUP totals and win probabilities, if present, remain labelled as provider evidence, not per-player optimizer projections. Yahoo-wide owned percentages are not league-specific ownership. Waiver dates are dates, not exact clearance instants.

Team identification is by full provider league/team keys in a private map, not display-name guesses; three distinct target keys are required. A failed source response, 401/403, a non-current roster, missing league rules, a mismatched team, an invalid capture timestamp, an earlier snapshot, or a failed reader all retain the previous verified snapshot. No partial "successful" refresh is emitted.

Synthetic fixtures require an explicit test opt-in, are labelled SYNTHETIC TEST FIXTURE and stamped with an archived 2020 date. They must not be presented to users as live Yahoo synchronization.

## What is required for truly automatic Yahoo refresh

Obtain owner approval FIRST for Yahoo application review/OAuth scope, any Cloudflare Worker deployment, credential storage, site changes or expenses. Yahoo currently reviews Fantasy Sports API applications; approval is not guaranteed. A future implementation would need a private owner-authenticated, server-side OAuth authorization-code callback with anti-CSRF state, registered exact HTTPS redirect URL, read-only Fantasy Sports scope, encrypted refresh-token storage, token rotation and revocation handling, and an owner-only GET snapshot route (no public league data or OAuth tokens). Responses must be no-store and preserve last good verified snapshot on error.

A Cloudflare Worker is a candidate low-cost host, subject to current free-plan quotas and account availability. Do NOT use a public GitHub Actions log/artifact, GitHub Pages JSON, or repo secrets to distribute private rosters. GitHub Pages itself cannot protect a private Yahoo token. There is no approved backend deployment in this PR.

## Tests

Run: node --test fantasy/tests/flaim-adapter.test.mjs

Tests are entirely fictional, require no network, and cover three-team identity, incomplete projections, real zero points/probabilities, unauthorized/expired/denied reads, missing responses, roster/scoreboard age, timestamp monotonicity, fixture labeling and retaining the last verified snapshot. Existing Fantasy HQ engine and safety checks remain unchanged.

Never commit actual owner snapshots or source response packets to this public repo.
