/* Private schema-v3 bridge for manually captured, authorized Flaim/Yahoo data.
   This module performs no network requests, OAuth, disk writes, or transactions.
   Never commit real response packets or output JSON to this public repository. */
export const TEAM_IDS = Object.freeze(['brock', 'quick', 'highlight']);
const RESERVE = new Set(['BN','BE','BENCH','IR','IR+','NA','TAXI']);
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const str = value => typeof value === 'string' ? value : '';
const validDate = value => typeof value === 'string' && Number.isFinite(Date.parse(value));
const idOf = value => String(value ?? '');
const noProjection = () => null;

function fail(message) { throw new Error(message); }
function safeError(error) {
  const code = String(error?.code || error?.error?.code || '').toLowerCase();
  const status = Number(error?.status ?? error?.error?.status);
  if (status === 401 || /expired|invalid_token|unauthorized/.test(code))
    return 'Yahoo authorization expired or disconnected; no new snapshot was accepted';
  if (status === 403 || /forbidden|access_denied/.test(code))
    return 'Yahoo read access denied; no new snapshot was accepted';
  return 'Provider read failed or incomplete; last verified snapshot retained';
}
function unwrap(packet, label) {
  if (!isObject(packet)) fail(label + ' missing provider result');
  if (packet.success !== true) {
    const message = safeError(packet);
    fail(message);
  }
  if (!isObject(packet.data)) fail(label + ' missing provider data');
  return packet.data;
}
function sameLeague(data, expected, label) {
  if (data.leagueKey !== expected) fail(label + ' league identity mismatch');
}
function validTarget(target) {
  if (!isObject(target) || !/^[0-9]+\.l\.[0-9]+$/.test(str(target.leagueKey)) ||
      !/^[0-9]+$/.test(idOf(target.teamId))) fail('Missing or invalid private team mapping');
  return {leagueKey:target.leagueKey,teamId:idOf(target.teamId),
    teamKey:target.leagueKey + '.t.' + idOf(target.teamId)};
}
function mapRoster(players) {
  if (!Array.isArray(players) || players.length === 0 || players.length > 60)
    fail('Current roster missing or invalid');
  const seen = new Set();
  return players.map(p => {
    if (!isObject(p) || !idOf(p.playerId) || !str(p.name) || !str(p.position) || !str(p.selectedPosition))
      fail('Incomplete Yahoo roster player');
    const playerId = idOf(p.playerId);
    if (seen.has(playerId)) fail('Duplicate Yahoo roster player');
    seen.add(playerId);
    const position = p.position.toUpperCase();
    const slot = p.selectedPosition.toUpperCase();
    return {
      id:playerId,name:p.name,position,slot,
      eligiblePositions:Array.isArray(p.eligiblePositions) && p.eligiblePositions.length ?
        p.eligiblePositions.filter(x => typeof x === 'string').map(x => x.toUpperCase()) : [position],
      nflTeam:str(p.team),injury:str(p.status) || null,
      projection:noProjection(),actualPoints:numeric(p.points) && p.points >= 0 ? p.points : null,
      cantCut:p.isUndroppable === true,editable:p.isEditable === true,
      locked:false
    };
  });
}
function slotsFromSettings(positions) {
  if (!Array.isArray(positions) || !positions.length) fail('Missing league roster rules');
  const slots={};
  for(const row of positions) {
    const slot=str(row?.position).toUpperCase();
    if (!slot || !Number.isInteger(row.count) || row.count < 0 || row.count > 15)
      fail('Malformed league roster rule');
    if (!RESERVE.has(slot)) slots[slot]=(slots[slot]||0)+row.count;
  }
  if (!Object.keys(slots).length) fail('No active league lineup slots');
  return slots;
}
function mapAvailable(list) {
  if (!Array.isArray(list) || list.length > 100) fail('Missing or oversized league availability response');
  return list.map(p => {
    if (!isObject(p) || !str(p.name) || !str(p.position) || !idOf(p.playerId || p.id))
      fail('Malformed available-player identity');
    return {
      id:idOf(p.playerId || p.id),name:p.name,position:p.position.toUpperCase(),
      eligiblePositions:Array.isArray(p.eligiblePositions) ? p.eligiblePositions : [p.position],
      team:str(p.team),acquisitionState:['free_agent','waivers'].includes(p.acquisitionState) ?
        p.acquisitionState : null,
      waiverDate:/^\d{4}-\d{2}-\d{2}$/.test(str(p.waiverDate)) ? p.waiverDate : null,
      percentOwned:numeric(p.percentOwned) ? p.percentOwned : null,
      projection:null
    };
  });
}
function mapMatchup(matches, teamKey) {
  if (!Array.isArray(matches)) fail('Missing Yahoo scoreboard');
  const found=matches.filter(m=>m?.home?.teamKey===teamKey || m?.away?.teamKey===teamKey);
  if (found.length > 1) fail('Ambiguous current-week matchup');
  if (!found.length) return null;
  const m=found[0];
  const side = p => ({
    teamKey:str(p.teamKey),teamId:idOf(p.teamId),teamName:str(p.teamName),
    points:numeric(p.points)?p.points:null,
    projectedPoints:numeric(p.projectedPoints)?p.projectedPoints:null,
    liveProjectedPoints:numeric(p.liveProjectedPoints)?p.liveProjectedPoints:null,
    winProbability:numeric(p.winProbability) && p.winProbability>=0 && p.winProbability<=1 ?
      p.winProbability:null
  });
  return {status:str(m.status),home:side(m.home),away:side(m.away)};
}
function mapOne(id, target, bundle) {
  if (!isObject(bundle)) fail(id + ' missing source packet');
  const identity=validTarget(target);
  const league=unwrap(bundle.league,id + ' league');
  const roster=unwrap(bundle.roster,id + ' roster');
  const standings=unwrap(bundle.standings,id + ' standings');
  const matchups=unwrap(bundle.matchups,id + ' matchups');
  const free=unwrap(bundle.freeAgents,id + ' available players');
  for (const [name,data] of [['league',league],['standings',standings],
                             ['matchups',matchups],['freeAgents',free]])
    sameLeague(data,identity.leagueKey,id + ' ' + name);
  if (roster.teamKey !== identity.teamKey || roster.snapshot?.type !== 'current')
    fail(id + ' team identity or roster recency mismatch');
  if (free.seasonYear !== 2026 || !Number.isInteger(league.currentWeek) ||
      league.currentWeek < 1 || league.currentWeek > 25)
    fail(id + ' missing current season/week identity');
  if (matchups.currentWeek !== league.currentWeek ||
      matchups.matchupWeek !== league.currentWeek)
    fail(id + ' scoreboard week mismatch');
  if (!Array.isArray(standings.standings)) fail(id + ' missing standings');
  const rank=standings.standings.find(x=>x?.teamKey===identity.teamKey);
  if (!rank) fail(id + ' own-team standings missing');
  const players=mapRoster(roster.players);
  const teamName=str(roster.teamName);
  if (!teamName) fail(id + ' missing own-team name');
  const wins=Number(rank.wins),losses=Number(rank.losses);
  const record=Number.isInteger(wins) && Number.isInteger(losses) ?
    String(wins)+'-'+String(losses)+(Number(rank.ties)>0?'-'+String(rank.ties):'') : '—';
  return {name:teamName,short:teamName,provider:'yahoo',
    leagueId:identity.leagueKey,teamId:identity.teamId,
    leagueUrl:'',record,rank:rank.rank || '—',
    waiver:Number.isInteger(rank.waiverPriority)?'#'+rank.waiverPriority:'—',
    roster:players,lineupSlots:slotsFromSettings(league.rosterPositions),
    projectionCoverage:'none',availablePlayers:mapAvailable(free.freeAgents),
    matchup:mapMatchup(matchups.matchups,identity.teamKey),
    source:'Flaim Fantasy / Yahoo; manual read-only capture',
    transactions:[],transactionsCoverage:{limited:true}};
}
function priorOrNull(previous) {
  return isObject(previous) && previous.schemaVersion === 3 &&
    isObject(previous.teams) && validDate(previous.syncedAtIso) ? previous : null;
}
/* All-or-nothing: a failing provider call, mismatched identity or stale clock never
   replaces the last verified snapshot. Returned snapshots are never persisted here. */
export function buildPrivateV3(bundle,{previous=null,nowIso=''}={}) {
  const fallback=priorOrNull(previous);
  try {
    if (!isObject(bundle) || !isObject(bundle.teams) || !isObject(bundle.teamMap) ||
        bundle.seasonYear !== 2026) fail('Missing source context or incorrect season');
    if (!validDate(bundle.capturedAtIso) || !validDate(nowIso))
      fail('Verified capture timestamp required');
    const capture=Date.parse(bundle.capturedAtIso),now=Date.parse(nowIso);
    if (capture > now + 300000 || now - capture > 30*60000)
      fail('Capture timestamp outside the accepted verification window');
    if (fallback && capture <= Date.parse(fallback.syncedAtIso))
      fail('New capture does not advance the last verified snapshot');
    const identities=new Set(),teams={};
    for(const id of TEAM_IDS) {
      const target=validTarget(bundle.teamMap[id]);
      if(identities.has(target.teamKey)) fail('Duplicate or ambiguous team mapping');
      identities.add(target.teamKey);
      teams[id]=mapOne(id,target,bundle.teams[id]);
    }
    const weeks=TEAM_IDS.map(id=>unwrap(bundle.teams[id].league,id+' league').currentWeek);
    if (!weeks.every(w=>w===weeks[0])) fail('League snapshots disagree on current week');
    const fixture=bundle.fixture === true;
    if (fixture && bundle.allowFixtures !== true)
      fail('Synthetic fixture explicitly requires test-only opt-in');
    const snapshot={
      schemaVersion:3,provider:'Yahoo',season:2026,week:weeks[0],
      syncedAtIso:fixture?'2020-01-01T00:00:00.000Z':bundle.capturedAtIso,
      source:fixture?'SYNTHETIC TEST FIXTURE - NOT LIVE':
        'Flaim Fantasy / Yahoo (manually captured, read-only)',
      captureType:fixture?'synthetic-fixture':'manual-provider-read',
      teams
    };
    if (JSON.stringify(snapshot).length > 2_000_000)
      fail('Private import exceeds the browser 2 MB limit');
    return {ok:true,snapshot,liveSync:false,fixture};
  } catch(error) {
    return {ok:false,snapshot:fallback,liveSync:false,error:safeError(error),
      reason:error.message && !/token|secret|credential/i.test(error.message)?error.message:undefined};
  }
}
/* Integrator injects a user-authorized provider reader, not credentials.
   No provider reader is bundled in the public repository. */
export async function refreshWithReader({readLeague,teamMap,previous=null,clock}={}) {
  const fallback=priorOrNull(previous);
  if(typeof readLeague!=='function' || typeof clock!=='function')
    return {ok:false,snapshot:fallback,liveSync:false,error:'No authorized provider reader connected'};
  try {
    const teams={};
    for(const id of TEAM_IDS) {
      validTarget(teamMap?.[id]);
      teams[id]=await readLeague(id,teamMap[id]);
    }
    const capturedAtIso=clock();
    return buildPrivateV3({teams,teamMap,seasonYear:2026,capturedAtIso},
      {previous:fallback,nowIso:capturedAtIso});
  }catch(error) {
    return {ok:false,snapshot:fallback,liveSync:false,error:safeError(error)};
  }
}
