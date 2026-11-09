# Yahoo/Flaim private schema-v3 bridge — Brock Hard only

This module is a read-only, testable **Brock Hard & Tee Baggin** data mapper for the released, Brock-only Fantasy HQ v2 site (owner-merged PR #183). It makes **no network calls, OAuth requests, file writes, or roster transactions**. It contains no Yahoo credentials. It is not a background sync.

## Owner-authorized input

Only Brock's 2026 Yahoo football league and team is selected. Collect five owner-authorized read-only provider results for this league: league info including lineup slots and current week, current own-team roster, current-week matchups, standings, and a bounded league available-player list. Every result must be a success:true, data:{...} envelope.

Call buildPrivateV3 with an ephemeral input object containing seasonYear=2026, capturedAtIso as the actual capture timestamp, teamMap with only a brock key specifying the exact leagueKey and teamId, and teams.brock containing the league, roster, matchups, standings and freeAgents responses. Use buildPrivateV3(input, {previous, nowIso}), or inject the authorized function readLeague into refreshWithReader({readLeague,teamMap,previous,clock}). No readLeague implementation is shipped.

Only when ok:true should the owner write JSON.stringify(result.snapshot) to an owner-private JSON file and use the dashboard's private JSON import control. Never commit private Yahoo snapshots, source envelopes, tokens or secrets to public GitHub or CI artifacts.

## Safety guarantees

- Only teams.brock is emitted, even if a caller provides extra teams. A multi-team previous snapshot is pruned on any failure path.
- Wrong league/team keys, incomplete roster, mismatched current weeks, failed reads, 401/403 authorization, expired credentials, stale or future timestamps, and non-advancing captures reject replacement, retaining the last verified Brock-only snapshot.
- Projection coverage remains none and all future player projections null. Provider-reported scored points are not future player projections; optimization and waiver ranking remain gated.
- Test-only fixtures require explicit opt-in, are stamped as archived, and say SYNTHETIC TEST FIXTURE - NOT LIVE.
- The module never changes lineups, trades, claims or rosters.

## Genuine Yahoo authentication (separate approval)

Yahoo Fantasy API access currently requires application review and OAuth 2.0 and is read-only. Server-side authorization-code flow, registered exact redirect URI, CSRF state and PKCE protection, protected credential storage and refresh-token rotation, owner-only access and no-store responses are prerequisites. There is currently **no enabled Yahoo OAuth backend**.

Run node --test fantasy/tests/flaim-adapter.test.mjs for fictional, no-network tests.
