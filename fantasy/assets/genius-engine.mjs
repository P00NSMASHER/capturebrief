/* BROCK HARD GENIUS LAB — source-limited strategic intelligence
 * Uses only three existing public, validated artifacts. No internet access,
 * credentials, invented transactions, browser AI claims, or roster mutations.
 * Statistical estimates are research scenarios, not calibrated true odds.
 */
import {analyzeEdge} from './edge-engine.mjs';
const good=x=>typeof x==='number'&&Number.isFinite(x);
const bounded=x=>good(x)&&x>=0&&x<=650;
const round=(x,d=1)=>Math.round((x+Number.EPSILON)*10**d)/10**d;
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null;
const sd=a=>a.length>1?Math.sqrt(a.reduce((s,x)=>s+(x-avg(a))**2,0)/(a.length-1)):null;
const quantile=(arr,t)=>{
 if(!arr.length)return null;
 const x=[...arr].sort((a,b)=>a-b),index=(x.length-1)*t,k=Math.floor(index);
 return x[k]+(x[Math.ceil(index)]-x[k])*(index-k);
};
const normalize=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'');
const rngSeed=n=>{let x=n>>>0||97531;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296}};
const names={'1':'BEEFS GAY','2':'Brock Hard & Tee Baggin','3':'Frenchville HornHog',
 '4':'Chasing Greatness','5':'Jersey junkyard','6':'Josh ❤️creampies','7':'Elmira Express','8':'Hazleton Coal Mine'};
const ids=Object.keys(names);
const cold=why=>({ready:false,reason:why,headline:'Source verification needed',sourceGrade:'unavailable',
 performance:[],opponents:[],robustness:null,reliability:null,waivers:[],trades:[],priorities:[]});
function validate(y,e,i,now){
 if(y?.schemaVersion!==3||y?.season!==2026||!y.teams||Object.keys(y.teams).join(',')!=='brock')
  return 'Only the authorized 2026 Brock Yahoo snapshot is supported';
 const t=y.teams.brock;
 if(String(t?.teamId)!=='2'||t.leagueId!=='470.l.290846'||!Array.isArray(t.roster)||
    !t.roster.length||t.roster.some(p=>!p?.id)||new Set(t.roster.map(p=>String(p.id))).size!==t.roster.length)
  return 'League/team/roster identities are not verified';
 if(i?.schemaVersion!==1||i?.kind!=='brock-league-intelligence'||i.season!==2026||
   i.leagueId!=='470.l.290846'||String(i.teamId)!=='2'||i.baselineWeek!==y.week||
   i.modelWeek!==y.week+1)return 'League intelligence belongs to a different season or week';
 if(!Array.isArray(i.teams)||i.teams.length!==8||new Set(i.teams.map(t=>String(t.id))).size!==8||
   i.teams.some(t=>!ids.includes(String(t.id))||normalize(t.name)!==normalize(names[t.id])||
    !Number.isInteger(t.wins)||!Number.isInteger(t.losses)||!good(t.pointsFor)||!good(t.pointsAgainst)))
  return 'Eight-team source coverage is incomplete';
 if(!Array.isArray(i.history)||i.history.length!==32)return 'The 32 completed source matchups are missing';
 for(const g of i.history){
  if(!Number.isInteger(g.week)||g.week<1||g.week>8||!ids.includes(String(g.home))||
    !ids.includes(String(g.away))||String(g.home)===String(g.away)||
    !bounded(g.homePoints)||!bounded(g.awayPoints)||!bounded(g.homeProjected)||!bounded(g.awayProjected))
   return 'Historical score/projection observations are invalid';
 }
 for(let week=1;week<=8;week++){
  const weekly=i.history.filter(g=>g.week===week);
  if(weekly.length!==4||new Set(weekly.flatMap(g=>[String(g.home),String(g.away)])).size!==8)
   return 'Historical game-week team coverage is not complete';
 }
 if(!Array.isArray(i.futureSchedule)||i.futureSchedule.length<4)return 'Upcoming eight-team fixtures are absent';
 const future=i.futureSchedule.filter(g=>g.week===y.week+1);
 if(future.length!==4||new Set(future.flatMap(g=>[String(g.home),String(g.away)])).size!==8)return 'Next-week schedule is incomplete';
 const timestamps=[y.syncedAtIso,i.capturedAtIso].map(x=>Date.parse(x||''));
 if(timestamps.some(x=>!Number.isFinite(x)||x>now+300000))return 'Invalid source timestamps';
 if(e&&(e.kind!=='brock-hard-prediction-inputs'||e.leagueId!=='470.l.290846'||
  String(e.teamId)!=='2'||e.season!==2026||e.week!==y.week+1))
  return 'Incompatible player-model week or league';
 return null;
}
/* Seven fictional all-play opponents per week. Actual W-L is historical only. */
function allPlay(i){
 const weeks=[],totals=new Map(ids.map(id=>[id,{teamId:id,name:names[id],wins:0,losses:0,
  allPlayWins:0,allPlayMatches:0,weekScores:[],projections:[],margins:[],opponents:[]}]));
 for(let week=1;week<=8;week++){
  const fixtures=i.history.filter(x=>x.week===week),results=new Map();
  for(const g of fixtures){
   results.set(String(g.home),{id:String(g.home),points:g.homePoints,projection:g.homeProjected,opponent:String(g.away),win:g.homePoints>g.awayPoints});
   results.set(String(g.away),{id:String(g.away),points:g.awayPoints,projection:g.awayProjected,opponent:String(g.home),win:g.awayPoints>g.homePoints});
  }
  const values=[...results.values()];
  for(const v of values){
   const row=totals.get(v.id),opp=results.get(v.opponent);
   row.wins+=v.win?1:0;row.losses+=v.win?0:1;
   row.weekScores.push(v.points);row.projections.push(v.projection);
   row.margins.push(v.points-v.projection);row.opponents.push(opp.points);
   row.allPlayWins+=values.reduce((s,b)=>s+(b.id===v.id?0:v.points>b.points?1:v.points===b.points?.5:0),0);
   row.allPlayMatches+=7;
  }
  weeks.push({week,scores:values.map(v=>({id:v.id,points:v.points,projection:v.projection}))});
 }
 const teams=[...totals.values()].map(t=>{
  const expectedWins=t.allPlayWins/7,allPlayPct=t.allPlayWins/t.allPlayMatches*100;
  const last3=avg(t.weekScores.slice(-3)),first5=avg(t.weekScores.slice(0,5));
  return {...t,allPlayWins:round(t.allPlayWins,1),allPlayPct:round(allPlayPct,1),
   expectedWins:round(expectedWins,2),luckWins:round(t.wins-expectedWins,2),
   scoredPerWeek:round(avg(t.weekScores),1),forecastBias:round(avg(t.margins),1),
   scoringVolatility:round(sd(t.weekScores),1),momentum:round(last3-first5,1),
   opponentPointsPerWeek:round(avg(t.opponents),1),
   weekScores:t.weekScores.map(x=>round(x,2))};
 }).sort((a,b)=>b.allPlayPct-a.allPlayPct||b.scoredPerWeek-a.scoredPerWeek);
 return {teams,weeks,brock:teams.find(x=>x.teamId==='2'),
  labels:{allPlay:'Theoretical W-L had every team played all other seven teams each completed week',
   luck:'Actual first-eight-week wins minus historical all-play expected wins; descriptive, not causal proof',
   momentum:'Average of most recent three completed weeks minus first five; not a future projection'}};
}
function reliability(history){
 const errors=history.flatMap(g=>[g.homePoints-g.homeProjected,g.awayPoints-g.awayProjected]);
 const paired=history.map(g=>({home:g.homePoints-g.homeProjected,away:g.awayPoints-g.awayProjected}));
 const predictions=[];
 for(let week=4;week<=8;week++){
  const training=history.filter(g=>g.week<week).map(g=>({
   marginError:(g.homePoints-g.awayPoints)-(g.homeProjected-g.awayProjected)
  }));
  if(training.length<8)continue;
  // Leave-future-out. Only earlier weeks train the forecast for this week.
  const marginal=training.flatMap(x=>[x.marginError,-x.marginError]);
  for(const g of history.filter(x=>x.week===week)){
   const margin=g.homeProjected-g.awayProjected;
   const hits=marginal.filter(e=>margin+e>0).length;
   const p=(hits+.5)/(marginal.length+1); // Jeffreys-like smoothing; avoid 0 and 1.
   const outcome=g.homePoints>g.awayPoints?1:0;
   predictions.push({week,prob:p,outcome,correct:(p>=.5)===Boolean(outcome),
    predictedMargin:margin,actualMargin:g.homePoints-g.awayPoints});
  }
 }
 const brier=predictions.length?avg(predictions.map(x=>(x.prob-x.outcome)**2)):null;
 const winnerAccuracy=predictions.length?avg(predictions.map(x=>x.correct?1:0))*100:null;
 const grouped=[{label:'Favorites 50–65%',low:.5,high:.65},{label:'Favorites 65–80%',low:.65,high:.8},
  {label:'Favorites above 80%',low:.8,high:1.001}].map(group=>{
   const cases=predictions.map(x=>({...x,confidence:Math.max(x.prob,1-x.prob),
    correctFavorite:x.prob>=.5?x.outcome:1-x.outcome})).filter(x=>x.confidence>=group.low&&x.confidence<group.high);
   return {name:group.label,cases:cases.length,hitRate:cases.length?round(avg(cases.map(x=>x.correctFavorite))*100,1):null};
  });
 return {matchups:history.length,scoreObservations:errors.length,
  forecastMAE:round(avg(errors.map(Math.abs)),1),
  forecastRMSE:round(Math.sqrt(avg(errors.map(x=>x*x))),1),
  absoluteMiss80:round(quantile(errors.map(Math.abs),.8),1),
  rollingTestGames:predictions.length,rollingBrier:brier===null?null:round(brier,3),
  naiveCoinflipBrier:.25,
  rollingAccuracy:winnerAccuracy===null?null:round(winnerAccuracy,1),
  empiricalScoreMiss80:round(quantile(errors.map(Math.abs),.8),1),
  paired,grouped,
  method:'Walk-forward tests on Weeks 4–8 using only earlier weeks (20 held-out games); historical Yahoo forecast errors, no hindsight fitting on test weeks',
  caveat:'Small-sample, correlated, pregame Yahoo projection calibration only. Not validated true real-world win probabilities.'
 };
}
function matchupEdge(i,performance,reliability){
 const team=i.teams.find(x=>String(x.id)==='2');
 const teams=performance.teams,week=i.modelWeek;
 const g=i.futureSchedule.find(x=>x.week===week&&(String(x.home)==='2'||String(x.away)==='2'));
 if(!g)return null;
 const home=String(g.home)==='2',opp=String(home?g.away:g.home),opponent=teams.find(t=>t.teamId===opp);
 const own=home?g.homeProjected:g.awayProjected,rival=home?g.awayProjected:g.homeProjected;
 const margin=own-rival, marginErrors=reliability.paired.flatMap(x=>[
   home?x.home-x.away:x.away-x.home,
   home?x.away-x.home:x.home-x.away
 ]);
 const projectedMargins=marginErrors.map(x=>margin+x);
 const smoothed=(projectedMargins.filter(x=>x>0).length+.5)/(projectedMargins.length+1);
 const our=performance.brock;
 const last3Bias=avg(our.margins.slice(-3)),last3Rival=opponent?avg(opponent.margins.slice(-3)):null;
 return {week,opponentId:opp,opponentName:names[opp],
  yahooMargin:round(margin,2),yahooProjected:own,opponentYahooProjected:rival,
  historicalWinScenario:round(smoothed*100,1),
  marginBand:{low:round(quantile(projectedMargins,.1),1),
   median:round(quantile(projectedMargins,.5),1),high:round(quantile(projectedMargins,.9),1)},
  opponentAllPlayPct:opponent?.allPlayPct??null,
  opponentVolatility:opponent?.scoringVolatility??null,
  teamRecentForecastBias:round(last3Bias,1),opponentRecentForecastBias:last3Rival===null?null:round(last3Rival,1),
  source:'Yahoo W1–8 paired score forecast error bootstrapping (64 oriented historical pairs), Week '+week+' Yahoo team forecast',
  caveat:'Historical scenario frequency, not a calibrated win probability. Recent small-sample biases are diagnostic, not additive adjustments.'};
}
function playoffSensitivity(i,rel,{gain=0,field=4,iterations=700}={}){
 if(![4,6].includes(field)||!Number.isFinite(gain)||gain<0||gain>30||
   !Number.isInteger(iterations)||iterations<100||iterations>5000)return null;
 const history=rel.paired,states0=new Map(i.teams.map(x=>[String(x.id),x]));
 const score=()=>({win:0,make:0,first:0,totalWins:0});
 const trials=score(),base=score();
 const sourceWin={};
 const end=i.postseason?.scenarioRegularSeasonEndWeek;
 if(end!==14||!Array.isArray(i.week9)||i.week9.length!==4||
 i.futureSchedule.filter(x=>x.week>=10&&x.week<=14).length!==20)return null;
 const run=(increment,rng,result)=>{
  const states=new Map([...states0.entries()].map(([id,x])=>[id,{id,wins:x.wins,losses:x.losses,pf:x.pointsFor}]));
  for(const fixture of i.week9){
   const h=states.get(String(fixture.home)),a=states.get(String(fixture.away));
   if(!h||!a||typeof fixture.homeWinProbability!=='number')return false;
   const homeWin=rng()<fixture.homeWinProbability;
   if(homeWin){h.wins++;a.losses++}else{a.wins++;h.losses++}
   h.pf+=Math.max(fixture.homePoints,fixture.homeProjected);
   a.pf+=Math.max(fixture.awayPoints,fixture.awayProjected);
  }
  for(const g of i.futureSchedule){
   if(g.week<10||g.week>14)continue;
   const h=states.get(String(g.home)),a=states.get(String(g.away));
   const e=history[Math.min(history.length-1,Math.floor(rng()*history.length))];
   if(!h||!a||!e)return false;
   let hs=Math.max(0,g.homeProjected+e.home+(increment&&g.week===10&&h.id==='2'?gain:0));
   let as=Math.max(0,g.awayProjected+e.away+(increment&&g.week===10&&a.id==='2'?gain:0));
   if(hs===as){if(rng()<.5)hs+=.01;else as+=.01}
   if(hs>as){h.wins++;a.losses++;if(g.week===10&&h.id==='2')result.win++}
   else{a.wins++;h.losses++;if(g.week===10&&a.id==='2')result.win++}
   h.pf+=hs;a.pf+=as;
  }
  const sorted=[...states.values()].sort((a,b)=>b.wins-a.wins||b.pf-a.pf||a.id.localeCompare(b.id));
  const rank=sorted.findIndex(x=>x.id==='2'),brock=states.get('2');
  if(rank<field)result.make++;
  if(rank===0)result.first++;
  result.totalWins+=brock.wins;
  return true;
 };
 for(let j=0;j<iterations;j++){
  const seed=(0xC0FFEE+(j+1)*9919487)>>>0;
  run(false,rngSeed(seed),base);
  run(true,rngSeed(seed),trials);
 }
 const outcome=o=>({playoffField:field,madeFieldPercent:round(o.make/iterations*100,1),
  topSeedPercent:round(o.first/iterations*100,1),
  week10WinPercent:round(o.win/iterations*100,1),
  expectedFinalWins:round(o.totalWins/iterations,2)});
 const origin=outcome(base),altered=outcome(trials);
 return {baseline:origin,scenario:altered,delta:{
  field:round(altered.madeFieldPercent-origin.madeFieldPercent,1),
  nextGame:round(altered.week10WinPercent-origin.week10WinPercent,1),
  firstSeed:round(altered.topSeedPercent-origin.topSeedPercent,1)},
  appliedWeeklyGain:round(gain,1),simulations:iterations,playoffField:field,
  notes:['HYPOTHETICAL field size '+field+', regular season ends Week 14 and wins/points-for tiebreak.',
   'Real Yahoo playoff settings were not verified. Do not present this as a true playoff probability.',
   'Forecast gain is applied ONLY for Week 10 and may not materialize.',
   'Yahoo Week 9 results remain undecided and are sampled using Yahoo provider win chances.',
   'Resamples 32 observed Yahoo paired-game errors from Weeks 1–8; these scenarios are not independently outcome-calibrated.']};
}
function rosterResearch(y,edge,i,performance){
 const lineup=y.teams.brock.roster;
 const calendar=edge?.teamByeWeeks||{};
 const aliases={Den:'DEN',Dal:'DAL',Jax:'JAX',Cin:'CIN',Min:'MIN',Bal:'BAL',NE:'NE',KC:'KC',NO:'NO',Ten:'TEN',
  NYJ:'NYJ',Hou:'HOU',Phi:'PHI',LV:'LV'};
 const convert=s=>aliases[s]||String(s||'').toUpperCase();
 const weeks=[i.modelWeek,i.modelWeek+1,i.modelWeek+2,13,14].filter((w,k,a)=>w>=i.modelWeek&&a.indexOf(w)===k).sort((a,b)=>a-b);
 const bye=weeks.map(week=>{
  const off=(calendar?.[String(week)]||[]).map(x=>String(x).toUpperCase());
  const blocked=lineup.filter(p=>off.includes(convert(p.nflTeam)));
  const active=pos=>lineup.filter(p=>p.position===pos&&!['IR','NA'].includes(p.slot)&&!off.includes(convert(p.nflTeam)));
  return {week,players:blocked.map(p=>({name:p.name,slot:p.slot,position:p.position})),
   teAvailable:active('TE').length,qbAvailable:active('QB').length,
   rbAvailable:active('RB').length,wrAvailable:active('WR').length,
   teShortage:active('TE').length===0,qbShortage:active('QB').length===0};
 });
 const gap=bye.find(x=>x.teShortage),market=y.teams.brock.availablePlayers||[];
 const teMarket=market.filter(p=>p.position==='TE'&&p.id&&p.name)
  .map(p=>({id:String(p.id),name:p.name,status:p.acquisitionState,
    team:p.team||p.nflTeam||null,
    week13Bye:edge?.teamByeWeeks?.['13']?.includes(convert(p.team||p.nflTeam))??null}))
  .filter(p=>p.week13Bye===false);
 const trade=(i.tradeResearch?.prospects||[]).map(x=>({
  id:normalize(x.outgoing)+'-'+normalize(x.target),
  give:x.outgoing,receive:x.target,toTeam:x.team,
  marketGive:x.modelValueOutgoing,marketReceive:x.modelValueIncoming,
  isSupported:x.supported===true,
  opponentNeed:x.needs?.includes(x.outgoingPosition),
  opponentSurplus:x.surplus?.includes(x.inboundPosition),
  label:x.supported&&x.needs?.includes(x.outgoingPosition)&&x.surplus?.includes(x.inboundPosition)?
   'Investigate trade fit':'Insufficient negotiation value',
  caution:'Named trade is hypothetical; manager acceptance, roster legality and ROS values are not verified.'
 }));
 return {byes:bye,urgentTe:gap,teMarket,trade,
  captureAt:y.syncedAtIso,source:'Brock Yahoo player roster, Yahoo league-available candidates, verified 2026 NFL byes + FantasyBot direct comparisons'};
}
function priorities({performance,headToHead,roster,sourceFresh,edgeReady,edge,model,notes}) {
 const out=[];
 const nextBye=roster.byes.find(x=>x.week===headToHead?.week&&x.players.some(p=>p.slot==='RB'));
 if(nextBye)out.push({id:'upcoming-bye',grade:'critical',title:'Do not leave a bye-week starter active',
  body:'The captured roster includes a Week '+nextBye.week+' running-back bye. Confirm a legal RB-to-flex reshuffle before lock.',
  source:'NFL schedule + Yahoo starting slots',tab:'lineup'});
 if(roster.urgentTe)out.push({id:'te-gap',grade:'critical',title:'Eliminate the Week '+roster.urgentTe.week+' TE zero',
  body:'No active rostered tight end is projected to have an NFL game that week. Investigate a compatible TE ahead of the rush.',
  source:'NFL schedule + exact Yahoo roster',tab:'waivers'});
 if(headToHead&&sourceFresh&&edgeReady&&model?.lineups?.balanced?.available)
  out.push({id:'model-reallocation',grade:'priority',
   title:'Investigate '+round(model.lineups.balanced.gain,1)+' modeled Week '+headToHead.week+' points',
   body:'A high-impact lineup adjustment exists, but the whole projected gain is uncertain. Apply the legal-slot plan only after confirming locks and injury news.',
   source:'FantasyBot Week '+headToHead.week+' forecasts + Yahoo legal lineup slots',tab:'lineup'});
 if(performance.brock&&headToHead){
  const adversary=performance.teams.find(x=>x.teamId===headToHead.opponentId);
  out.push({id:'rival-scout',grade:'insight',
   title:'Scout '+headToHead.opponentName+' beyond its record',
   body:'Rival historical all-play strength: '+round(adversary?.allPlayPct||0,1)+'% of league-wide matchups; record alone hides roster variance.',
   source:'Eight completed Yahoo weeks; descriptive only',tab:'lab'});
 }
 return out.slice(0,5).map((p,j)=>({...p,rank:j+1,actionsEnabled:sourceFresh}));
}
export function buildGeniusLab(y,edge,intel,{now=Date.now(),field=4,realization=.5,simulations=900}={}){
 const error=validate(y,edge,intel,now);
 if(error)return cold(error);
 const perf=allPlay(intel),rel=reliability(intel.history);
 const head=matchupEdge(intel,perf,rel),roster=rosterResearch(y,edge,intel,perf);
 const ya=Date.parse(y.syncedAtIso),ma=Date.parse(edge?.observedAtIso||'');
 const yAge=(now-ya)/3600000,modelAge=Number.isFinite(ma)?(now-ma)/3600000:null;
 const fresh=yAge>=0&&yAge<=6;
 let model=null;
 if(edge)model=analyzeEdge(y,edge,{now,mode:'balanced'});
 const ready=!!model?.ready&&!!model?.lineups?.balanced?.available&&fresh;
 const projectedGain=ready?Math.max(0,Math.min(30,model.lineups.balanced.gain||0)):0;
 const portion=Math.max(0,Math.min(1,good(realization)?realization:.5));
 const playoff=playoffSensitivity(intel,rel,{gain:projectedGain*portion,field,iterations:simulations});
 const recommendations=priorities({performance:perf,headToHead:head,roster,sourceFresh:fresh,edgeReady:ready,model});
 const ymod=y.teams.brock;
 const ranked=perf.teams.map(p=>({
  teamId:p.teamId,name:p.name,
  yahooStanding:intel.teams.find(t=>String(t.id)===p.teamId)?.rank??null,
  historicalAllPlayPct:p.allPlayPct,historicalExpectedWins:p.expectedWins,
  luckWins:p.luckWins,weeklyVolatility:p.scoringVolatility,
  lastThreeVsFirstFive:p.momentum,
  powerRank:edge?.leaguePower?.find(k=>normalize(k.teamName)===normalize(p.name))?.rank??null
 })).sort((a,b)=>b.historicalAllPlayPct-a.historicalAllPlayPct);
 const tradeSafe=roster.trade.filter(t=>t.isSupported&&t.opponentNeed&&t.opponentSurplus);
 const nextActions=fresh?recommendations.filter(p=>p.actionsEnabled):[];
 return {ready:true,sourceGrade:ready?'source-checked-model':fresh?'partial-projections':'historical-only',
  reviewedAtIso:intel.capturedAtIso,yahooAtIso:y.syncedAtIso,modelAtIso:edge?.observedAtIso||null,
  ageHours:{yahoo:round(yAge,1),model:modelAge===null?null:round(modelAge,1)},
  allPlay:perf,reliability:rel,matchup:head,playoff,roster,rankings:ranked,
  tradeCandidates:tradeSafe,
  priorities:recommendations,actionablePriorities:nextActions,
  forecast:{modelReady:ready,nextWeek:intel.modelWeek,baseProjectionGain:projectedGain,
   sensitivityFraction:portion,appliedGain:round(projectedGain*portion,1),
   caveat:'One-week FantasyBot PPR projected uplift; historical Yahoo team-error bootstrap shows sensitivity but cannot guarantee benefit.'},
  model,
  status:ready?'MODELED · SOURCE-CHECKED':fresh?'PARTIAL MODEL':'HISTORICAL · DO NOT ACT',
  notes:['Never submit a lineup change, waiver claim or trade automatically.',
   'Opponent strength, forecast error and all-play performance are source-derived; risk estimates are exploratory and not outcome-calibrated.',
   'Current acquisition/lineup legality must be confirmed in Yahoo immediately before any move.',
   'The NFL calendar and player values change; a historical capture is not a live feed.']};
}
