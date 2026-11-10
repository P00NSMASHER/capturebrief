/* Brock Hard Strategy Engine — inspectable, no network, no user mutations.
 * Yahoo historical team-score forecast residuals backtest future scenarios.
 * Hypothetical playoff field size and regular-season end week remain explicit.
 * Model predictions are NOT validated calibrated probabilities of true outcomes.
 */
import {analyzeEdge} from './edge-engine.mjs';
const ok=n=>typeof n==='number'&&Number.isFinite(n);
const prob=n=>ok(n)&&n>=0&&n<=1;
const safe=n=>ok(n)&&n>=0&&n<=600;
const round=(n,d=1)=>Math.round((n+Number.EPSILON)*10**d)/10**d;
const pct=(n,d=1)=>round(n*100,d);
const seedRandom=x=>{let a=x>>>0||1;return()=>{a^=a<<13;a^=a>>>17;a^=a<<5;return(a>>>0)/4294967296}};
const canon=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]/g,'');
const isStarter=p=>p&&!['BN','BE','BENCH','IR','IR+','NA','TAXI'].includes(String(p.slot).toUpperCase());
const qs=(arr,q)=>{const a=[...arr].sort((x,y)=>x-y);if(!a.length)return null;const i=(a.length-1)*q,j=Math.floor(i);return a[j]+(a[Math.ceil(i)]-a[j])*(i-j)};
const unavailable=reason=>({ready:false,reason,coverage:'unverified',lineup:null,league:null,calibration:null,trade:[],players:null,home:null});
function validateSource(y,edge,intel,now){
 if(!y||y.schemaVersion!==3||y.season!==2026||!y.teams||Object.keys(y.teams).join(',')!=='brock')return 'Brock-only 2026 snapshot required';
 const t=y.teams.brock;
 if(String(t?.leagueId)!=='470.l.290846'||String(t?.teamId)!=='2'||!Array.isArray(t.roster)||t.roster.length<1)return 'Unexpected Yahoo team identity';
 if(!intel||intel.schemaVersion!==1||intel.kind!=='brock-league-intelligence'||intel.season!==2026||
    intel.leagueId!=='470.l.290846'||String(intel.teamId)!=='2')return 'League intelligence not verified';
 if(intel.baselineWeek!==y.week||!Number.isInteger(intel.modelWeek)||intel.modelWeek!==y.week+1)return 'League intelligence belongs to a different week';
 if(!intel.leagueScoring?.ppr||!Array.isArray(intel.leagueScoring?.statModifiers)||intel.leagueScoring.statModifiers.length<30)
   return 'Verified Yahoo scoring settings missing';
 if(!Array.isArray(intel.teams)||intel.teams.length!==8||!Array.isArray(intel.history)||intel.history.length!==32||
 !Array.isArray(intel.week9)||intel.week9.length!==4||!Array.isArray(intel.futureSchedule)||intel.futureSchedule.length!==20)
   return 'The full league evidence set is missing';
 const expected=['1','2','3','4','5','6','7','8'];
 if(intel.teams.some(t=>!expected.includes(String(t.id))||!Number.isInteger(t.wins)||!Number.isInteger(t.losses)||!safe(t.pointsFor)||!safe(t.pointsAgainst)&&t.pointsAgainst<0)||
 new Set(intel.teams.map(t=>String(t.id))).size!==8)return 'League standings invalid';
 if(!intel.teams.some(x=>String(x.id)==='2'&&x.wins+'-'+x.losses===String(t.record).replace('–','-')))return 'League data conflicts with Brock record';
 for(const [arr,needsActual] of [[intel.history,true],[intel.week9,true],[intel.futureSchedule,false]]){
  for(const g of arr){
   if(!Number.isInteger(g.week)||!expected.includes(String(g.home))||!expected.includes(String(g.away))||
      g.home===g.away||!safe(g.homeProjected)||!safe(g.awayProjected)||
      (needsActual&&(!safe(g.homePoints)||!safe(g.awayPoints))))return 'Malformed league matchup';
   if(arr===intel.week9&&!prob(g.homeWinProbability))return 'Provider week-nine odds unavailable';
  }
 }
 for(let w=1;w<=8;w++)if(intel.history.filter(g=>g.week===w).length!==4)return 'Historical Yahoo evidence incomplete';
 for(let w=10;w<=14;w++)if(intel.futureSchedule.filter(g=>g.week===w).length!==4)return 'Future Yahoo league schedule incomplete';
 const d=Date.parse(intel.capturedAtIso||'');
 if(!Number.isFinite(d)||d>now+300000)return 'Invalid league capture timestamp';
 if(edge&&edge.kind==='brock-hard-prediction-inputs'&&
    (edge.season!==2026||edge.leagueId!=='470.l.290846'||String(edge.teamId)!=='2'))return 'Invalid independent player source identity';
 return null;
}
function calibrate(history){
 const teamErrors=[],marginErrors=[],outcomes=[];
 for(const g of history){
  const eh=g.homePoints-g.homeProjected,ea=g.awayPoints-g.awayProjected;
  teamErrors.push(eh,ea);marginErrors.push(eh-ea);
  const p=g.homeProjected-g.awayProjected,o=g.homePoints-g.awayPoints;
  if(p!==0&&o!==0)outcomes.push(Math.sign(p)===Math.sign(o)?1:0);
 }
 const size=teamErrors.length;
 return {
  teamObservations:size,matchups:history.length,
  bias:round(teamErrors.reduce((s,v)=>s+v,0)/size,2),
  mae:round(teamErrors.reduce((s,v)=>s+Math.abs(v),0)/size,2),
  rmse:round(Math.sqrt(teamErrors.reduce((s,v)=>s+v*v,0)/size),2),
  absoluteError80:round(qs(teamErrors.map(Math.abs),.8),1),
  absoluteError90:round(qs(teamErrors.map(Math.abs),.9),1),
  winnerAccuracy:round(outcomes.reduce((a,b)=>a+b,0)/outcomes.length*100,1),
  winnerCorrect:outcomes.reduce((a,b)=>a+b,0),
  winnerTested:outcomes.length,
  marginError80:round(qs(marginErrors.map(Math.abs),.8),1),
  pairedErrors:history.map(g=>({home:g.homePoints-g.homeProjected,away:g.awayPoints-g.awayProjected})),
  note:'Empirical Yahoo pregame forecast errors, Weeks 1–8; 32 league games / 64 team-scores. Retrospective performance, not a validated future model calibration.'
 };
}
function chooseSamples(cal,iterations=4500,shift=0){
 const rng=seedRandom(21430261),teamsBase=new Map();
 return {rng,shift};
}
function simulate(intel,cal,edgeGain=0,simulations=4000){
 const spots=intel.postseason?.scenarioPlayoffTeamCounts||[4,6],end=intel.postseason?.scenarioRegularSeasonEndWeek;
 if(end!==14||!Array.isArray(spots)||spots.join(',')!=='4,6')return null;
 const counts={baseline:{four:0,six:0,first:0,wins:0,w10:0},
  optimized:{four:0,six:0,first:0,wins:0,w10:0}};
 const errors=cal.pairedErrors,teamIds=intel.teams.map(t=>String(t.id));
 const getSample=rng=>errors[Math.floor(rng()*errors.length)];
 for(let iter=0;iter<simulations;iter++){
  // Identical random streams allow comparing only the hypothetical lineup change.
  for(const scenario of ['baseline','optimized']){
   const rng=seedRandom((iter+1)*174763+39);
   const states=new Map(intel.teams.map(t=>[String(t.id),{id:String(t.id),wins:t.wins,losses:t.losses,pf:t.pointsFor}]));
   for(const g of intel.week9){
    const h=states.get(String(g.home)),a=states.get(String(g.away)),e=getSample(rng);
    if(!h||!a)continue;
    const homeWins=rng()<g.homeWinProbability;
    if(homeWins){h.wins++;a.losses++}else{a.wins++;h.losses++}
    h.pf+=Math.max(g.homePoints,g.homeProjected+e.home,0);
    a.pf+=Math.max(g.awayPoints,g.awayProjected+e.away,0);
   }
   for(const g of intel.futureSchedule){
    if(g.week>end)continue;
    const h=states.get(String(g.home)),a=states.get(String(g.away)),e=getSample(rng);
    if(!h||!a)continue;
    let hPoints=Math.max(0,g.homeProjected+e.home);
    let aPoints=Math.max(0,g.awayProjected+e.away);
    if(scenario==='optimized'&&g.week===10&&edgeGain>0){
     if(h.id==='2')hPoints+=edgeGain;
     if(a.id==='2')aPoints+=edgeGain;
    }
    if(hPoints===aPoints){if(rng()<.5)hPoints+=.01;else aPoints+=.01}
    if(hPoints>aPoints){h.wins++;a.losses++;if(g.week===10&&h.id==='2')counts[scenario].w10++}
    else{a.wins++;h.losses++;if(g.week===10&&a.id==='2')counts[scenario].w10++}
    h.pf+=hPoints;a.pf+=aPoints;
   }
   const ranks=[...states.values()].sort((a,b)=>b.wins-a.wins||b.pf-a.pf||a.id.localeCompare(b.id));
   const place=ranks.findIndex(x=>x.id==='2'),brock=states.get('2');
   counts[scenario].wins+=brock.wins;
   if(place===0)counts[scenario].first++;
   if(place<4)counts[scenario].four++;
   if(place<6)counts[scenario].six++;
  }
 }
 const map=q=>({top4:pct(counts[q].four/simulations),top6:pct(counts[q].six/simulations),
  firstSeed:pct(counts[q].first/simulations),week10Win:pct(counts[q].w10/simulations),
  expectedWins:round(counts[q].wins/simulations,2)});
 const base=map('baseline'),opt=map('optimized');
 return {baseline:base,optimized:opt,delta:{
  top4:round(opt.top4-base.top4,1),top6:round(opt.top6-base.top6,1),week10Win:round(opt.week10Win-base.week10Win,1)},
  simulations,optimizedModelGain:edgeGain,
  source:'Yahoo W1–8 paired projection errors + provider Week 9 probabilities + Yahoo W10–14 projected scores',
  assumptions:['Scenario ends regular season after Week 14; actual playoff timing not verified.',
   'Shows both 4-team and 6-team playoff fields; actual field size not verified.',
   'Tie-breaker modeled by wins, then total points for; actual league playoff rules not verified.',
   'Week 9 uses Yahoo estimated outcome probabilities, not final results.',
   'Optimized scenario assumes the full independent one-week projected lineup gain is realized in Week 10; lineup is never changed automatically.',
   'Historical error bootstrapping assumes future scoring errors resemble Weeks 1–8 and repeats 32 observed paired errors. These are conditional scenarios, not calibrated true probabilities.']};
}
function findBye(edge,week,team){
 const list=edge?.teamByeWeeks?.[String(week)]||[];
 const abbr=String(team||'').toUpperCase();
 return list.includes(abbr);
}
function computeTradeIntel(intel,edge){
 const byeSource=edge?.teamByeWeeks;
 return (intel.tradeResearch?.prospects||[]).map(p=>{
  const bye=byeSource?findBye(edge,13,p.target==='Travis Kelce'?'KC':p.target==='T.J. Hockenson'?'MIN':p.target==='Colston Loveland'?'CHI':'') : null;
  const fit=p.needs?.includes(p.outgoingPosition)&&p.surplus?.includes(p.inboundPosition);
  return {...p,fit,notOnByeWeek13:bye===null?null:!bye,
   recommendation:p.supported&&fit&&bye===false?'investigate':'do-not-propose',
   confidence:p.supported&&fit&&bye===false?'source-backed candidate':'insufficient'};
 });
}
function leagueRanking(intel,edge){
 return intel.teams.map(t=>{
  const power=(edge?.leaguePower||[]).find(p=>canon(p.teamName)===canon(t.name));
  return {...t,powerRank:power?.rank??null,powerRating:power?.rating??null,
   rankDislocation:power?.rank?round(t.rank-power.rank,0):null,scoreDifferential:round(t.pointsFor-t.pointsAgainst,2)};
 }).sort((a,b)=>a.rank-b.rank);
}
function positionIssue(y,edge){
 const te=y.teams.brock.roster.filter(p=>p.position==='TE');
 const sameBye=te.length>0&&te.every(p=>findBye(edge,13,p.nflTeam));
 const market=y.teams.brock.availablePlayers.filter(p=>p.position==='TE').map(p=>({
   name:p.name,id:p.id,team:p.team||p.nflTeam||'',state:p.acquisitionState,
   availabilityAt:y.syncedAtIso,notWeek13Bye:edge?.teamByeWeeks?
    !findBye(edge,13,String(p.team||p.nflTeam||'').toUpperCase()):null}));
 return {te13Shortage:sameBye,rosteredTightEnds:te.map(p=>p.name),market,
  note:'Yahoo availability was captured, not queried live. NFL bye-week compatibility does not establish injury health or roster eligibility.'};
}
export function buildStrategicReport(y,edge,intel,{now=Date.now(),simulations=4000}={}){
 const error=validateSource(y,edge,intel,now);
 if(error)return unavailable(error);
 const calibration=calibrate(intel.history);
 const model=edge?analyzeEdge(y,edge,{now,mode:'balanced'}):null;
 const permitted=model?.ready===true;
 const shift=permitted&&model.lineups?.balanced?.available?Math.max(0,model.lineups.balanced.gain):0;
 const odds=simulate(intel,calibration,shift,simulations);
 const ranking=leagueRanking(intel,edge),upcoming=intel.futureSchedule
  .filter(g=>String(g.home)==='2'||String(g.away)==='2')
  .map(g=>{
   const home=String(g.home)==='2',opp=home?String(g.away):String(g.home);
   const other=ranking.find(x=>x.id===opp);
   return {week:g.week,opponent:other?.name||'Unknown',opponentRank:other?.rank??null,
    opponentPowerRank:other?.powerRank??null,opponentPowerRating:other?.powerRating??null,
    brockProjected:home?g.homeProjected:g.awayProjected,
    opponentProjected:home?g.awayProjected:g.homeProjected,
    projectedMargin:round((home?g.homeProjected-g.awayProjected:g.awayProjected-g.homeProjected),2)};
  });
 const next=upcoming[0],trust=getSourceAge(y,edge,intel,now);
 const urgent=positionIssue(y,edge);
 const trades=computeTradeIntel(intel,edge);
 const needsWeek13=urgent.te13Shortage;
 const priorities=[];
 if(permitted&&model.priorities)priorities.push(...model.priorities.filter(x=>x.severity==='critical').slice(0,2)
  .map(x=>({id:x.id,title:x.title,detail:x.detail,severity:x.severity,tab:x.id==='bye-replacement'?'lineup':'waivers'})));
 if(needsWeek13)priorities.push({id:'week13-te',title:'Week 13: tight-end replacement required',
  detail:'Both rostered TEs share a Week 13 bye. Scout Dallas Goedert on waivers or explore a fair trade for Travis Kelce.',
  severity:'critical',tab:'waivers'});
 if(permitted&&model.lineups?.balanced?.available&&shift>0)priorities.push({id:'lineup-upside',
  title:round(shift,1)+' modeled Week 10 points at stake',detail:'Compare the optimizer’s exact RB/FLEX reshuffle. The gain is a forecast, not a guarantee.',
  severity:'priority',tab:'lineup'});
 if(next)priorities.push({id:'next-opponent',title:'Week '+next.week+' vs '+next.opponent,
  detail:'Yahoo pregame gap '+(next.projectedMargin>=0?'+':'')+next.projectedMargin.toFixed(1)+
  '; historical matchup forecasts chose only '+calibration.winnerCorrect+' of '+calibration.winnerTested+' winners.',
  severity:'watch',tab:'lab'});
 const ma=trust.yahooAgeHours<=6;
 const rankedAvailable=model?.waivers?.watches||[];
 const waiverPriorities=ma?
   [...urgent.market.filter(p=>p.name==='Dallas Goedert').map(p=>({...p,reason:'Week 13 TE shortage; Week 10 bye not an issue by Week 13',priority:1,week10Projection:null})),
   ...rankedAvailable.filter(p=>p.position!=='TE').slice(0,5).map(p=>({id:p.id,name:p.name,position:p.position,
    week10Projection:p.forecast||null,reason:'Week 10 FantasyBot PPR projection; compare to a rostered alternative',priority:2}))]
   :[];
 return {ready:true,status:trust.yahooAgeHours<=6?'actionable-forecast':'historical-research',
  verifiedAtIso:intel.capturedAtIso,source:trust,calibration,scoring:{
   verifiedPPR:!!intel.leagueScoring?.ppr&&
    intel.leagueScoring.statModifiers.some(x=>x.id==='11'&&x.value===1),
   offensiveBonusThresholdsAbsent:!!intel.leagueScoring.verifiedNoAdditionalOffensiveBonusThresholds,
   specialTeamsForecastGap:true,note:intel.leagueScoring.notes},
  model,upcoming,rankings:ranking,odds,trade:trades,week13:urgent,waiverPriorities,
  priorities:priorities.slice(0,5),league: {standing:ranking.find(x=>x.id==='2'),powerRank:model?.powerRank??1},
  exposure: {week10:next,matchupError80:calibration.marginError80,topThreats:upcoming.filter(x=>x.opponentPowerRank&&x.opponentPowerRank<=3)},
  limitations:['Historical Yahoo pregame projections are not perfectly calibrated; this is an empirical scenario model.',
  'Official playoff field and regular-season end were unavailable, so field-size scenarios are conditional.',
  'Trade values come from FantasyBot market estimates and manager roster fit; acceptance is not guaranteed.',
  'Specific NFL injury statuses, waivers, and lineup locks must be rechecked in Yahoo.']};
}
function getSourceAge(y,edge,intel,now){
 const yy=Date.parse(y.syncedAtIso),mm=Date.parse(edge?.observedAtIso||''),ii=Date.parse(intel.capturedAtIso);
 return {yahooAgeHours:round(Math.max(0,(now-yy)/3600000),1),
  modelAgeHours:Number.isFinite(mm)?round(Math.max(0,(now-mm)/3600000),1):null,
  leagueAgeHours:round(Math.max(0,(now-ii)/3600000),1),
  isFresh:Math.max(0,(now-yy)/3600000)<=6,independentlyVerified:!!edge};
}
