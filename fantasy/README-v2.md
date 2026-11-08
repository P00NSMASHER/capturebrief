# Fantasy HQ v2

A read-only, mobile-first fantasy football command center in the original \`/capturebrief/fantasy/\` URL family. Published from the capturebrief \`gh-pages\` branch only after owner review. This feature branch/PR is **not** a production deploy.

## Implemented
- Three existing Yahoo team URLs continue working: /fantasy/brock/, /fantasy/quick/, /fantasy/highlight/.
- Site shell, iPhone-friendly layout, Home Screen manifest, team switching and four functional analysis tabs.
- Exact position-/FLEX-aware lineup assignment; rejects incomplete projections, invalid slots and locked players.
- Waiver add/drop comparison requires a complete league-specific projection set and candidate acquisition states.
- Matchup probability estimate requires both projected totals and standard deviations; playoff Monte Carlo requires schedule/standings/odds evidence.
- A clear archived notice for snapshots older than 24h; no stale waiver action is presented as current.
- Recheck the published snapshot with no-store fetching and fallback to last successful public snapshot; local JSON import never uploads private data.

## Important limits
**No Yahoo OAuth/session tokens are embedded or sent to GitHub.** On GitHub Pages, "Check snapshot" re-reads an existing JSON file and **is not a live Yahoo API sync**. True automatic Yahoo sync needs a separately hosted, authenticated adapter with owner-controlled Yahoo OAuth and server-side refresh token storage. No lineup moves, waiver claims, or trades are executed. No private personal league data is committed by this change. ESPN/Sleeper adapters are future integration points, not shipped integrations.

## Data contract
The app loads existing /fantasy/data.json (\`schemaVersion=1\`) without modifying it. A user may explicitly import a private JSON object with \`schemaVersion: 3\`; the importer rejects >2MB and only retains the three known teams. \`fantasy/tests/fixtures/private-v3.sample.json\` is **fully fictional test data**.

Use fields:
- top level: \`schemaVersion: 3\`, \`syncedAtIso\` (ISO UTC), \`season\`, \`week\`, \`teams\`.
- team keys: \`brock\`, \`quick\`, \`highlight\`.
- team: \`name\`, \`short\`, \`leagueId\`, \`teamId\`, \`roster\`, \`lineupSlots\`, \`projectionCoverage\`, optional \`availablePlayers\`, \`matchup\` and \`matchupModel\`.
- player: \`id\`, \`name\`, \`position\`, \`eligiblePositions\`, \`slot\`, \`projection\` (number or null), \`injury\`, \`locked\`.
- waiver player: \`acquisitionState\` must be \`free_agent\` or \`waivers\` plus numeric \`projection\`; optimization considers bench drops only, never submits.
- matchup model: \`myProjected\`, \`oppProjected\`, \`mySigma\`, \`oppSigma\` as positive numeric estimates.

A complete \`projectionCoverage\` assertion is only trustworthy after upstream league settings, player IDs and projections have been reconciled. Missing projections must remain null, not 0.

## Verification
Run: \`node --check fantasy/assets/engine.mjs\`, \`node --check fantasy/assets/app-v2.mjs\`, \`node --test fantasy/tests/*.test.mjs\` from repository root.
CI workflow: \`.github/workflows/fantasy-hq-v2.yml\`. GitHub Pages runtime and authenticated Yahoo connectivity are separate from source tests.

## Reuse / attribution
Architecture and feature reference: [lfrocharod/fantasy-dashboard](https://github.com/lfrocharod/fantasy-dashboard) (MIT). Other researched adapters: [whatadewitt/yahoo-fantasy-sports-api](https://github.com/whatadewitt/yahoo-fantasy-sports-api) (MIT), [cwendt94/espn-api](https://github.com/cwendt94/espn-api) (MIT), [nflverse/nflreadpy](https://github.com/nflverse/nflreadpy) (MIT, dataset terms vary). Core engine here is an original browser-side implementation; third-party packages are not yet vendored or deployed.
