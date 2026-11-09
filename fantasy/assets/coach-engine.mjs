/* Brock Hard Coach: explainable, deterministic snapshot analysis.
   No network, credentials, predictions without evidence, trades or roster mutations. */
import {getFreshness, normalizePosition, compareScoredLineup, rosterStatusAlerts, positionDepth} from './engine.mjs';

const finite=n=>typeof n==='number'&&Number.isFinite(n);
const bench=new Set(['BN','BE','BENCH']);
const reserve=new Set(['IR','IR+','NA','TAXI']);
const nonStarter=s=>bench.has(s)||reserve.has(s);
const number=n=>finite(n)?n:(typeof n==='string'&&n.trim()!==''&&Number.isFinite(Number(n))?Number(n):null);
const signed=n=>(n>=0?'+':'')+n.toFixed(1);

const card=(id,title,detail,evidence,{tone='neutral',actionTab=null,actionLabel=null,filter=null}={})=>({
 id,title,detail,evidence,tone,actionTab,actionLabel,filter
});
function matchFor(team){
 const m=team?.matchup;
 if(!m?.home||!m.away)return null;
 const home=String(m.home.teamId||''),away=String(m.away.teamId||'');
 if(home!=='2'&&away!=='2')return null;
 return home==='2'?{mine:m.home,opp:m.away}:{mine:m.away,opp:m.home};
}
function availableByPosition(team,pos){
 const seen=new Set();
 return (Array.isArray(team.availablePlayers)?team.availablePlayers:[])
  .filter(p=>String(p?.position||'').toUpperCase()===pos&&p.id&&p.name&&
    ['free_agent','waivers'].includes(p.acquisitionState)&&
    finite(p.percentOwned)&&p.percentOwned>=0&&p.percentOwned<=100&&
    !seen.has(String(p.id))&&(seen.add(String(p.id)),true))
  .sort((a,b)=>b.percentOwned-a.percentOwned||String(a.name).localeCompare(String(b.name)));
}
function readyResponse(status,label){
 return {ready:false,status,headline:label,subtitle:'The verified Brock Hard capture is required before showing move recommendations.',
  metrics:[],priorities:[],sections:{},captureAt:null};
}
/** No “AI live manager” claim. Each output is traceable to Brock-only Yahoo fields. */
export function buildCoachPlan(snapshot,{now=Date.now()}={}){
 if(!snapshot||snapshot.schemaVersion!==3||snapshot.season!==2026||
   !snapshot.teams||Object.keys(snapshot.teams).join(',')!=='brock')
   return readyResponse('unverified','Brock-only 2026 data unavailable');
 const team=snapshot.teams.brock;
 if(String(team?.leagueId)!=='470.l.290846'||String(team?.teamId)!=='2'||
    !Array.isArray(team.roster)||team.roster.length===0)
   return readyResponse('unverified','Team identity or roster unavailable');
 const ids=team.roster.map(p=>String(p?.id||''));
 if(ids.some(id=>!id)||new Set(ids).size!==ids.length)
   return readyResponse('unverified','Player identity could not be verified');
 const fresh=getFreshness(snapshot.syncedAtIso,now);
 if(!fresh.actionable)
   return {...readyResponse('archived','The Yahoo capture needs updating'),
      captureAt:snapshot.syncedAtIso,
      subtitle:'The last saved data is too old for actionable coach advice. Check the published snapshot or Yahoo first.'};
 const roster=team.roster;
 const flagged=rosterStatusAlerts(roster);
 const flaggedStarters=flagged.filter(a=>{
   const player=roster.find(p=>String(p.id)===String(a.id));
   return player&&!nonStarter(normalizePosition(player.slot));
 }).sort((a,b)=>(a.level==='urgent'?-1:0)-(b.level==='urgent'?-1:0));
 const flaggedReserves=flagged.filter(a=>!flaggedStarters.some(s=>s.id===a.id));
 const depths=positionDepth(roster);
 const countAt=pos=>depths.find(d=>d.position===pos)?.active||0;
 const qbs=availableByPosition(team,'QB');
 const scored=compareScoredLineup(roster,team.lineupSlots);
 const slots=team.lineupSlots||{};
 const starters=roster.filter(p=>!nonStarter(normalizePosition(p.slot)));
 const lineup=[];
 if(flaggedStarters.length){
   const p=flaggedStarters[0],label=p.slot==='W/R/T'?'flex':'starting '+p.slot;
   lineup.push(card('starter-status','Recheck '+p.name+' before your next lineup decision',
      'Yahoo listed '+p.status+' in the '+label+' spot at capture. Check his current designation and whether the slot is still editable before choosing a replacement.',
      'Brock roster · '+p.slot+' · '+p.status+' at capture',
      {tone:'attention',actionTab:'lineup',actionLabel:'Review starters'}));
 }else{
   lineup.push(card('starter-status','Review current starters before kickoff',
      'No starter injury flag was included in this capture. Check Yahoo for changes, byes and lock status before making a move.',
      'Saved starter slots, not live health',{actionTab:'lineup',actionLabel:'View lineup'}));
 }
 if(scored.available){
   const delta=scored.gap;
   lineup.push(card('lineup-hindsight','Use this week as a film review',
     'Your starters have '+scored.current.toFixed(2)+' points at capture; the highest-scoring combination using points already scored was '+
     scored.best.toFixed(2)+(delta>0?' ('+signed(delta)+' difference).':' (no difference).')+
     ' This is hindsight, not a next-week start/sit recommendation.',
     'Week '+snapshot.week+' scored points only',{actionTab:'lineup',actionLabel:'See week review'}));
 }else{
   lineup.push(card('lineup-unrated','Do not force an unverified lineup swap',
     'Future player-level forecasts and complete lock information are not confirmed. A named start/sit swap cannot be justified from this snapshot.',
     'No verified player-level future projection set',{actionTab:'lineup',actionLabel:'View roster'}));
 }
 const waiver=[];
 const qbDepth=countAt('QB');
 if(slots.QB===1&&qbDepth===1){
   if(qbs.length){
     const first=qbs[0],other=qbs.find(p=>p.acquisitionState==='free_agent');
     const kind=first.acquisitionState==='waivers'?'on waivers':'a free agent';
     waiver.push(card('qb-insurance','Scout quarterback insurance before spending a waiver claim',
       'You roster one active QB. '+first.name+' was listed '+kind+' at capture; '+
       (other&&other.id!==first.id?other.name+' was also listed as a free agent. ':'')+
       'Compare current availability, bye coverage, and Yahoo roster rules before adding or dropping anyone.',
       '1 rostered QB · Yahoo-wide '+first.percentOwned.toFixed(0)+'% roster rate is NOT a performance projection',
       {tone:'priority',actionTab:'waivers',actionLabel:'View available QBs',filter:'QB'}));
   }else{
     waiver.push(card('qb-insurance','Check for quarterback cover',
       'You have one active QB and this saved availability list contains no verified QB acquisition option. Check Yahoo before making a roster move.',
       '1 rostered QB · available QB evidence missing',{tone:'attention',actionTab:'waivers',actionLabel:'View players',filter:'QB'}));
   }
 }else{
   waiver.push(card('market-scout','Scout available players against actual roster needs',
     'Use the captured free-agent pool and position filters. Yahoo-wide roster percentages indicate market interest, not player projections or waiver impact.',
     'Yahoo league availability · '+(team.availablePlayers?.length||0)+' captured players',
     {actionTab:'waivers',actionLabel:'View player pool'}));
 }
 const otherFlags=flaggedReserves.length;
 if(otherFlags)waiver.push(card('injury-depth','Check depth behind your flagged players',
   otherFlags+' bench or reserve player'+(otherFlags===1?' has':'s have')+
   ' Yahoo status flags at capture. Confirm your active replacement options before prioritizing another skill position.',
   'Brock roster status flags · no current injury news implied',{actionTab:'lineup',actionLabel:'Review bench'}));
 const trades=[];
 if(qbDepth===1&&qbs.length){
   trades.push(card('trade-patience','Explore waivers before paying for a backup QB',
     'A QB depth need is visible, but the saved league list contains a possible acquisition route. Avoid assuming a WR-for-QB offer is fair without rest-of-season values and the other manager’s needs.',
     '1 rostered QB · league-available QB candidates',{actionTab:'waivers',actionLabel:'Check QB market',filter:'QB'}));
 }else{
   trades.push(card('trade-market','Define your target before proposing a trade',
     'Check your positional depth and the other manager’s roster and needs first. A trade package needs comparable future-value evidence, not last week’s points.',
     'Brock roster counts only · opponent roster values unavailable',{actionTab:'lab',actionLabel:'See league'}));
 }
 trades.push(card('trade-gate','No defensible player-for-player trade yet',
   'This public Brock-only snapshot has no verified opponent roster valuations or complete forward projections. Do not send a named offer based on invented values.',
   'Trade recommendation withheld until complete source evidence'));
 const rank=number(team.standings?.rank)??number(String(team.rank||'').match(/^\d+/)?.[0]);
 const wins=number(team.standings?.wins),losses=number(team.standings?.losses);
 const pointsFor=number(team.standings?.pointsFor),pointsAgainst=number(team.standings?.pointsAgainst);
 const leagueSize=number(team.standings?.leagueSize)||8;
 const differential=pointsFor!==null&&pointsAgainst!==null?Math.round((pointsFor-pointsAgainst)*100)/100:null;
 const league=[];
 if(rank!==null&&wins!==null&&losses!==null){
   league.push(card('standing','Rank '+rank+' of '+leagueSize+' · '+wins+'–'+losses,
     'You are currently '+(rank===1?'first in the saved standings':'ranked '+rank+' in the saved standings')+
     (differential!==null?'. Your points-for minus points-against differential is '+(differential>=0?'+':'')+differential.toFixed(2)+'.':'.')+
     ' A current league rank does not confirm a playoff berth or championship.',
     'Yahoo standings at '+String(team.standings?.asOfIso||snapshot.syncedAtIso),
     {actionTab:'lab',actionLabel:'See league'}));
 }else{
   league.push(card('league-unrated','Standings details are incomplete',
     'League-wide position and scoring comparisons need verified Yahoo standings data. They are not estimated from the matchup score.',
     'Missing verified standings fields',{actionTab:'lab',actionLabel:'See league'}));
 }
 const future=(Array.isArray(team.upcomingMatchups)?team.upcomingMatchups:[])
  .filter(g=>Number.isInteger(g?.week)&&g.week>snapshot.week&&g.opponent&&finite(g.myProjected)&&finite(g.opponentProjected)&&
    g.myProjected>=0&&g.opponentProjected>=0)
  .map(g=>({...g,margin:Math.round((g.myProjected-g.opponentProjected)*100)/100}))
  .sort((a,b)=>a.week-b.week).slice(0,3);
 const playoffs=[];
 if(future.length){
   const closest=[...future].sort((a,b)=>Math.abs(a.margin)-Math.abs(b.margin)||a.week-b.week)[0];
   playoffs.push(card('closest-matchup','Prepare depth for Week '+closest.week+' vs '+closest.opponent,
     'Of your saved next '+future.length+' matchups, Week '+closest.week+' has the smallest Yahoo team-level pregame gap ('+
     (closest.margin>=0?'+':'')+closest.margin.toFixed(1)+' Brock points). Audit your bye-week and injury coverage in Yahoo before that week.',
     'Yahoo team pregame forecast · not a win prediction',
     {tone:'attention',actionTab:'lab',actionLabel:'View schedule'}));
 }else{
   playoffs.push(card('schedule-missing','Check the remaining schedule in Yahoo',
     'This Brock-only capture lacks verified future opponents and league playoff rules. Do not rely on estimated playoff odds.',
     'Remaining matchup evidence unavailable',{actionTab:'lab',actionLabel:'Open league tab'}));
 }
 playoffs.push(card('playoff-prep','Protect your bench and waiver flexibility',
   'Review '+roster.filter(p=>reserve.has(normalizePosition(p.slot))).length+' reserve assignment(s), '+
   flagged.length+' roster status flag(s), and your position coverage. Check playoff dates, byes, trade deadline and any claim limits directly in Yahoo.',
   'Current roster flags · playoff rules and remaining schedule not fully captured',
   {actionTab:'lineup',actionLabel:'Audit roster'}));
 const priorities=[lineup[0],waiver[0],playoffs[0]];
 const first=priorities[0];
 const metrics=[
   {label:'LEAGUE POSITION',value:rank!==null?rank+' / '+leagueSize:'—'},
   {label:'RECORD',value:wins!==null&&losses!==null?wins+'–'+losses:String(team.record||'—')},
   {label:'YAHOO FLAGS',value:String(flagged.length)}
 ];
 return {ready:true,status:'snapshot',captureAt:snapshot.syncedAtIso,
  headline:first?.title||'Review your Brock Hard roster',
  subtitle:'Prioritized checks from the last verified Yahoo snapshot—not live predictions or submitted roster moves.',
  metrics,priorities,sections:{lineup,waivers:waiver,trades,playoffs,league},
  facts:{rank,leagueSize,wins,losses,differential,qbDepth,flaggedStarters:flaggedStarters.length,
   scoredGap:scored.available?scored.gap:null,nextMatchups:future.length},
  projectionCoverage:team.projectionCoverage||'unknown'};
}
