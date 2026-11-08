/* Fantasy HQ v2 analytical core — no I/O, credential access or roster mutation. */
export const VERSION = 3;
export const TEAM_IDS = Object.freeze(['brock', 'quick', 'highlight']);
const FLEX = new Set(['FLEX','W/R/T','WR/RB/TE','RB/WR/TE']);
const SUPER = new Set(['SUPERFLEX','SUPER_FLEX','OP','Q/W/R/T']);
const DEFENSE = new Set(['DEF','DST','D/ST']);

const finite = value => typeof value === 'number' && Number.isFinite(value);
export const round = (n,places=1) => Math.round((n+Number.EPSILON)*10**places)/10**places;
export const teamPath = id => '/capturebrief/fantasy/' + (TEAM_IDS.includes(id)?id:'') + '/';
export const normalizePosition = pos => {
  const p=String(pos||'').toUpperCase().trim();
  return DEFENSE.has(p)?'DEF':p==='PK'?'K':p;
};
export function getFreshness(value, now=Date.now()) {
  const ms=Date.parse(value||'');
  if (!Number.isFinite(ms)) return {state:'unknown',ageHours:null,label:'Unknown data age',actionable:false};
  const hours=Math.max(0,(now-ms)/3_600_000);
  if (hours>24) return {state:'stale',ageHours:round(hours),label:'Archived snapshot',actionable:false};
  if (hours>6) return {state:'aging',ageHours:round(hours),label:'Check before acting',actionable:false};
  return {state:'fresh',ageHours:round(hours),label:'Recently synced',actionable:true};
}
function fromLegacy(id,t) {
  const s=t.snapshot||{};
  return {
    id, name:t.full||t.short||id, short:t.short||id, accent:t.accent||'cyan',
    leagueId:String(s.leagueId||''), teamId:String(s.teamId||''),
    leagueUrl:t.leagueUrl||'', provider:'yahoo', record:t.record||'—',
    rank:t.rank||'—', waiver:t.waiver||'—', score:t.score||'—',
    scoreState:t.scoreState||'', health:t.health||'—',
    nextMove:t.nextMove||'', nextDetail:t.nextDetail||'',
    weekNote:t.weekNote||'', confidence:t.confidence||'',
    alerts:Array.isArray(t.alerts)?t.alerts:[],
    waivers:Array.isArray(t.waivers)?t.waivers:[],
    transactions:Array.isArray(t.recentTransactions)?t.recentTransactions:[],
    strategy:t.strategy||null,
    matchup:s.matchup||null,
    roster:(Array.isArray(s.roster)?s.roster:[]).map((p,i)=>({
      id:String(p.id||p.playerId||p.name||i),name:p.name||'Unknown',
      position:normalizePosition(p.position||p.slot),slot:normalizePosition(p.slot),
      eligiblePositions:(p.eligiblePositions||[p.position]).map(normalizePosition),
      nflTeam:p.team||'',injury:p.status||null,projection:null,locked:false
    })),
    availablePlayers:Array.isArray(s.availablePlayers)?s.availablePlayers:[],
    lineupSlots:null,
    projectionCoverage:'none',
    rawLegacy:true
  };
}
function fromVersion3(id,t) {
  return {
    id,name:String(t.name||t.full||id),short:String(t.short||t.name||id),
    accent:String(t.accent||'cyan'),leagueId:String(t.leagueId||''),
    teamId:String(t.teamId||''),leagueUrl:t.leagueUrl||'',
    provider:String(t.provider||'yahoo'),record:t.record||'—',rank:t.rank||'—',
    waiver:t.waiver||'—',score:t.score||'—',scoreState:t.scoreState||'',
    health:t.health||'—',nextMove:t.nextMove||'',nextDetail:t.nextDetail||'',
    weekNote:t.weekNote||'',confidence:t.confidence||'',
    alerts:Array.isArray(t.alerts)?t.alerts:[],
    waivers:Array.isArray(t.waivers)?t.waivers:[],
    transactions:Array.isArray(t.transactions)?t.transactions:[],
    strategy:t.strategy||null,matchup:t.matchup||null,
    roster:(Array.isArray(t.roster)?t.roster:[]).map((p,i)=>({
      id:String(p.id||p.name||i),name:String(p.name||'Unknown'),
      position:normalizePosition(p.position),slot:normalizePosition(p.slot),
      eligiblePositions:(Array.isArray(p.eligiblePositions)&&p.eligiblePositions.length?p.eligiblePositions:[p.position]).map(normalizePosition),
      nflTeam:String(p.nflTeam||p.team||''),injury:p.injury||null,
      projection:finite(p.projection)&&p.projection>=0?p.projection:null,
      locked:!!p.locked
    })),
    availablePlayers:Array.isArray(t.availablePlayers)?t.availablePlayers:[],
    lineupSlots:t.lineupSlots&&typeof t.lineupSlots==='object'?t.lineupSlots:null,
    projectionCoverage:t.projectionCoverage||'unknown',rawLegacy:false
  };
}
export function normalizeSnapshot(raw) {
  if (!raw||typeof raw!=='object'||!raw.teams||typeof raw.teams!=='object') throw new Error('Invalid fantasy snapshot: missing teams');
  const version=raw.schemaVersion===VERSION?VERSION:1;
  const teams={};
  for (const id of TEAM_IDS) if (raw.teams[id]) teams[id]=version===VERSION?fromVersion3(id,raw.teams[id]):fromLegacy(id,raw.teams[id]);
  if (Object.keys(teams).length===0) throw new Error('No supported fantasy teams found');
  return {schemaVersion:version,provider:raw.provider||'Yahoo',season:raw.season||2026,
    week:Number(raw.week)||null,syncedAtIso:raw.syncedAtIso||raw.updatedAt||null,
    syncedAt:raw.syncedAt||raw.updatedAtEt||'Unknown',
    teams,refreshPrompt:raw.refreshPrompt||'',source:raw.source||'published-snapshot'};
}
export function rosterBuckets(roster) {
  const starters=[],bench=[],reserve=[];
  for (const p of Array.isArray(roster)?roster:[]) {
    if (['BN','BE','BENCH'].includes(p.slot)) bench.push(p);
    else if (['IR','IR+','NA','TAXI'].includes(p.slot)) reserve.push(p);
    else starters.push(p);
  }
  return {starters,bench,reserve};
}
function canFill(player,slot) {
  const ss=normalizePosition(slot);
  const eligible=new Set((player.eligiblePositions||[player.position]).map(normalizePosition));
  if (eligible.has(ss)) return true;
  if (FLEX.has(ss)) return ['RB','WR','TE'].some(p=>eligible.has(p));
  if (SUPER.has(ss)) return ['QB','RB','WR','TE'].some(p=>eligible.has(p));
  return false;
}
export function slotsFromRoster(roster) {
  const slots={};
  for (const p of Array.isArray(roster)?roster:[]) {
    const s=normalizePosition(p.slot);
    if (['BN','BE','BENCH','IR','IR+','NA','TAXI',''].includes(s)) continue;
    slots[s]=(slots[s]||0)+1;
  }
  return slots;
}
function expandedSlots(counts) {
  const a=[];
  for (const [k,v] of Object.entries(counts||{})) {
    if (!Number.isInteger(v)||v<0||v>15) return null;
    for(let i=0;i<v;i++) a.push(normalizePosition(k));
  }
  return a.length<=14?a:null;
}
/* Exact maximum-weight bipartite assignment: O(players * slots * 2^slots).
   Never guess absent projections, use an injured-out player, or count a player twice. */
export function optimizeLineup(roster, counts, options={}) {
  const slots=expandedSlots(counts);
  if (!slots||slots.length===0) return {available:false,reason:'Missing or invalid league lineup rules'};
  const players=(Array.isArray(roster)?roster:[]).filter(p=>p&&!['IR','IR+','NA','TAXI'].includes(normalizePosition(p.slot)));
  if (players.some(p=>p.locked===true)) return {available:false,reason:'Lineup includes locked players; submission-safe optimization unavailable'};
  const eligible=players.filter(p=>slots.some(s=>canFill(p,s)) && !['OUT','IR','PUP','SUSPENDED'].includes(String(p.injury||'').toUpperCase()));
  if (eligible.some(p=>!finite(p.projection)||p.projection<0)) return {available:false,reason:'Missing current projections for eligible players'};
  const dp=new Map([[0,{score:0,picks:[]}]]);
  for(const p of eligible) {
    const previous=Array.from(dp.entries());
    for(const [mask,row] of previous) for(let j=0;j<slots.length;j++){
      const bit=1<<j;
      if ((mask&bit)||!canFill(p,slots[j])) continue;
      const next=mask|bit,score=row.score+p.projection,old=dp.get(next);
      if (!old||score>old.score+1e-9) dp.set(next,{score,picks:[...row.picks,{slot:slots[j],player:p}]});
    }
  }
  const best=dp.get((1<<slots.length)-1);
  if(!best) return {available:false,reason:'Not enough eligible, projected players to fill the lineup'};
  const current=roster.filter(p=>slotsFromRoster([p])[normalizePosition(p.slot)]&&finite(p.projection)).reduce((s,p)=>s+p.projection,0);
  const currentComplete=roster.filter(p=>slotsFromRoster([p])[normalizePosition(p.slot)]).length===slots.length
    && roster.filter(p=>slotsFromRoster([p])[normalizePosition(p.slot)]).every(p=>finite(p.projection));
  return {available:true,score:round(best.score,2),currentScore:currentComplete?round(current,2):null,
    gain:currentComplete?round(best.score-current,2):null,assignments:best.picks,
    projectedOnly:true,method:'exact-slot-assignment'};
}
export function rankWaiverTargets(team) {
  if(!team||team.projectionCoverage!=='complete'||!Array.isArray(team.availablePlayers))
    return {available:false,reason:'Live, league-specific waiver projections are not available'};
  const roster=team.roster||[],slots=team.lineupSlots||slotsFromRoster(roster),baseline=optimizeLineup(roster,slots);
  if(!baseline.available) return {available:false,reason:baseline.reason};
  const results=[];
  for(const fa of team.availablePlayers) {
    if(fa.acquisitionState!=='free_agent'&&fa.acquisitionState!=='waivers') continue;
    if(!finite(fa.projection)||fa.projection<0) continue;
    const add={...fa,slot:'BN',position:normalizePosition(fa.position),eligiblePositions:fa.eligiblePositions||[fa.position]};
    for(const drop of roster) {
      if(drop.locked||drop.cantCut||!['BN','BE','BENCH'].includes(normalizePosition(drop.slot))) continue;
      const result=optimizeLineup([...roster.filter(p=>p!==drop),add],slots);
      if(result.available)results.push({add:add.name,drop:drop.name,improvement:round(result.score-baseline.score,2),status:fa.acquisitionState});
    }
  }
  results.sort((a,b)=>b.improvement-a.improvement);
  return {available:true,baseline:baseline.score,recommendations:results.filter(r=>r.improvement>0).slice(0,8),
    note:'Projected lineup uplift only. Roster limits, waiver cost, lock times and scoring settings require provider verification.'};
}
function erf(x){const sign=x<0?-1:1,z=Math.abs(x),t=1/(1+.3275911*z);
  const y=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-z*z);
  return sign*y;
}
export function estimateWinChance(myMean,opponentMean,mySigma,opponentSigma){
  if (![myMean,opponentMean,mySigma,opponentSigma].every(finite)||mySigma<=0||opponentSigma<=0)return null;
  const z=(myMean-opponentMean)/Math.sqrt(mySigma**2+opponentSigma**2);
  return round((.5*(1+erf(z/Math.SQRT2)))*100,1);
}
function rng(seed){let x=(seed>>>0)||1;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296}}
/* Optional Monte Carlo. Requires all season schedule, standings and matchup probabilities.
   No odds are displayed from partial schedules or a roster-only snapshot. */
export function simulatePlayoffs({teams,schedule,playoffSpots,iterations=3000,seed=2026}={}) {
  if(!Array.isArray(teams)||teams.length<2||!Array.isArray(schedule)||!schedule.length||
     !Number.isInteger(playoffSpots)||playoffSpots<1||playoffSpots>teams.length||
     !Number.isInteger(iterations)||iterations<100||iterations>20000)return null;
  const ids=new Set(teams.map(t=>String(t.id)));
  if(ids.size!==teams.length||teams.some(t=>!finite(t.wins)||!finite(t.losses)||!finite(t.pointsFor)))return null;
  if(schedule.some(g=>!ids.has(String(g.home))||!ids.has(String(g.away))||g.home===g.away||
     !finite(g.homeWinChance)||g.homeWinChance<0||g.homeWinChance>1))return null;
  const random=rng(seed),counts=new Map(teams.map(t=>[String(t.id),0]));
  for(let iter=0;iter<iterations;iter++){
    const ranks=teams.map(t=>({id:String(t.id),wins:t.wins,pointsFor:t.pointsFor}));
    const byId=new Map(ranks.map(t=>[t.id,t]));
    for(const game of schedule){const win=random()<game.homeWinChance?String(game.home):String(game.away);byId.get(win).wins++}
    ranks.sort((a,b)=>b.wins-a.wins||b.pointsFor-a.pointsFor||a.id.localeCompare(b.id));
    for(const team of ranks.slice(0,playoffSpots))counts.set(team.id,counts.get(team.id)+1);
  }
  return Object.fromEntries([...counts].map(([id,wins])=>[id,round(wins*100/iterations,1)]));
}
export function isSafeUrl(url){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname==='football.fantasysports.yahoo.com'}catch{return false}}
