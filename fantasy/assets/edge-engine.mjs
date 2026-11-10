/* Brock Hard Intelligence Lab — explainable forecast decisions.
   Sources are separately verified Yahoo+FantasyBot+NFL schedule. No network or user actions. */
import {optimizeLineup,getFreshness,normalizePosition,round,estimateWinChance} from './engine.mjs';
const n=x=>typeof x==='number'&&Number.isFinite(x);
const npos=x=>n(x)&&x>=0&&x<=100;
const teamPoints=x=>n(x)&&x>=0&&x<=600; // Yahoo team totals can exceed 100 fantasy points.
const bench=new Set(['BN','BE','BENCH']),reserve=new Set(['IR','IR+','NA','TAXI']);
const starter=p=>!bench.has(normalizePosition(p?.slot))&&!reserve.has(normalizePosition(p?.slot));
const active=p=>!reserve.has(normalizePosition(p?.slot));
const pos=s=>normalizePosition(s);
const name=s=>String(s||'').trim().toLowerCase().replace(/[^a-z0-9]+/g,'');
const codes={JAX:'JAX',Jax:'JAX',DAL:'DAL',Dal:'DAL',DEN:'DEN',Den:'DEN',CIN:'CIN',Cin:'CIN',
 MIN:'MIN',Min:'MIN',LV:'LV',NE:'NE',BAL:'BAL',Bal:'BAL',HOU:'HOU',Hou:'HOU',KC:'KC',NYJ:'NYJ',
 TEN:'TEN',Ten:'TEN',PHI:'PHI',Phi:'PHI',NO:'NO',NOE:'NO',CAR:'CAR',CHI:'CHI',
 IND:'IND',ARI:'ARI',LA:'LAR',LAR:'LAR',SF:'SF',SEA:'SEA',TB:'TB',GB:'GB',
 WAS:'WAS',NYG:'NYG',PIT:'PIT',MIA:'MIA',ATL:'ATL',BUF:'BUF',LAC:'LAC',DET:'DET',CLE:'CLE'};
const code=s=>codes[String(s||'').trim()]||String(s||'').trim().toUpperCase();
const diff=(a,b)=>round(a-b,2);
const fallbackSigma=Object.freeze({QB:6.5,RB:6.7,WR:7,TE:5.5,K:4.5,DEF:5.5});
const sampleSigma=(log,mean,position)=>{
 if(mean===0)return 0;
 const points=(Array.isArray(log)?log:[]).map(x=>x?.points).filter(npos);
 const fallback=fallbackSigma[position]||6;
 if(points.length<3)return round(Math.max(3,Math.min(fallback,mean*0.75)),2);
 const avg=points.reduce((s,x)=>s+x,0)/points.length;
 const variance=points.reduce((s,x)=>s+(x-avg)**2,0)/(points.length-1);
 const sd=Math.sqrt(variance);
 return round(Math.min(24,Math.max(2.5,Math.sqrt(0.65*sd**2+0.35*fallback**2))),2);
};
function fail(reason,details=''){
 return {ready:false,status:'unavailable',reason,details,modelWeek:null,headline:'AI forecasts need verification',
  priorities:[],lineups:{},waivers:[],opponents:[],byes:[]};
}
function rankForPower(power,value){
 const v=name(value);
 return power.find(x=>name(x.teamName)===v)||null;
}
function sourceDate(x){const t=Date.parse(x||'');return Number.isFinite(t)?t:null}
function scoreOf(p,risk){
 const mean=p.forecast;
 if(!n(mean))return null;
 const factor=risk==='safe'?-0.35:risk==='upside'?0.35:0;
 return round(Math.max(0,mean+p.sigma*factor),2);
}
const licensed=mode=>['safe','balanced','upside'].includes(mode)?mode:'balanced';
const unique=xs=>new Set(xs).size===xs.length;
function lineupModel(players,slots,mode){
 const list=players.map(p=>({...p,projection:scoreOf(p,mode),locked:false}));
 // This code is advisory; no lock-state guarantee. Source is modeled, not Yahoo projected data.
 const result=optimizeLineup(list,slots);
 if(!result.available)return {available:false,reason:result.reason,mode};
 const chosen=new Set(result.assignments.map(x=>String(x.player.id)));
 const starters=players.filter(starter);
 const before=new Set(starters.map(x=>String(x.id)));
 const inPlayers=result.assignments.filter(x=>!before.has(String(x.player.id))).map(x=>({
  id:x.player.id,name:x.player.name,slot:x.slot,position:x.player.position,
  modelPoints:x.player.forecast,sigma:x.player.sigma,injury:x.player.injury||null
 }));
 const outPlayers=starters.filter(x=>!chosen.has(String(x.id))).map(x=>({
  id:x.id,name:x.name,slot:x.slot,position:x.position,modelPoints:x.forecast,bye:x.bye||false
 }));
 const assigned=result.assignments.map(x=>({id:x.player.id,name:x.player.name,position:x.player.position,
  slot:x.slot,forecast:x.player.forecast,adjusted:scoreOf(x.player,mode),sigma:x.player.sigma,bye:x.player.bye||false}));
 const mu=round(assigned.reduce((s,p)=>s+p.forecast,0),2);
 const totalSigma=round(Math.sqrt(assigned.reduce((s,p)=>s+p.sigma**2,0)),2);
 return {available:true,mode,score:result.score,currentScore:result.currentScore,gain:result.gain,
  mean:mu,estimatedSigma:totalSigma,illustrativeLow:round(Math.max(0,mu-totalSigma),1),
  illustrativeHigh:round(mu+totalSigma,1),inPlayers,outPlayers,assignments:assigned,
  note:'Model-based and illustrative: no calibrated prediction interval, covariance or league-specific bonus adjustment.'};
}
function evaluateWaivers(players,yahoo,edge,slots,baseline){
 const old=new Set(yahoo.availablePlayers?.map(x=>String(x.id))||[]);
 const provider=new Map((edge.availableProjections||[]).map(p=>[String(p.id),p]));
 const pool=(yahoo.availablePlayers||[]).filter(p=>old.has(String(p.id))&&provider.has(String(p.id))&&
  ['free_agent','waivers'].includes(p.acquisitionState)).map(p=>{
  const raw=provider.get(String(p.id));
  if(raw.name!==p.name||pos(raw.position)!==pos(p.position)||!npos(raw.projection))return null;
  return {...p,forecast:raw.projection,rank:raw.rank,ppg:raw.ppg,
    sigma:sampleSigma([],raw.projection,pos(p.position)),bye:false};
 }).filter(Boolean);
 const droppable=players.filter(p=>bench.has(pos(p.slot))&&!p.cantCut&&!p.locked);
 let pairs=[];
 if(baseline.available){
  for(const q of pool){
   for(const d of droppable){
    const trial=players.filter(p=>p.id!==d.id).concat([{
      id:q.id,name:q.name,position:q.position,slot:'BN',eligiblePositions:q.eligiblePositions||[q.position],
      forecast:q.forecast,sigma:q.sigma,injury:null,locked:false,projection:q.forecast
    }]);
    const alt=lineupModel(trial,slots,'balanced');
    if(alt.available&&n(alt.mean)&&n(baseline.mean)){
      pairs.push({add:{id:q.id,name:q.name,position:q.position,points:q.forecast},
        drop:{id:d.id,name:d.name,position:d.position,points:d.forecast},
        projectedWeeklyUplift:diff(alt.mean,baseline.mean),
        availability:q.acquisitionState,marketPercent:q.percentOwned??null,
        forecastSource:'FantasyBot Week '+edge.week+' PPR; Yahoo available at '+yahoo._capture});
    }
   }
  }
 }
 pairs.sort((a,b)=>b.projectedWeeklyUplift-a.projectedWeeklyUplift||b.add.points-a.add.points);
 const positive=pairs.filter(x=>x.projectedWeeklyUplift>=0.75).slice(0,8);
 const watches=pool.sort((a,b)=>b.forecast-a.forecast||a.name.localeCompare(b.name)).slice(0,12)
  .map(q=>({id:q.id,name:q.name,position:q.position,forecast:q.forecast,rank:q.rank,
    availability:q.acquisitionState,marketPercent:q.percentOwned??null}));
 return {positive,watches,covered:pool.length,total:yahoo.availablePlayers?.length||0,
  description:'Projected one-week lineup uplift only; roster/claim rules, future depth and lock times remain unverified.'};
}
function investigateByes(roster,week,calendar){
 const weeks=[week,week+1,week+2,week+3,week+4,13,14]
  .filter((x,i,a)=>x>=week&&x<=17&&a.indexOf(x)===i).sort((a,b)=>a-b);
 return weeks.map(w=>{
  const teams=(calendar?.[String(w)]||[]).map(code);
  const players=roster.filter(p=>teams.includes(code(p.nflTeam))).map(p=>({
    id:p.id,name:p.name,position:p.position,slot:p.slot,starting:starter(p)
  }));
  const shortage=[];
  for(const group of ['QB','RB','WR','TE','K','DEF']){
    const required=group==='QB'?1:group==='RB'?2:group==='WR'?2:group==='TE'?1:group==='K'?1:1;
    const eligible=roster.filter(p=>pos(p.position)===group&&!reserve.has(pos(p.slot))&&
      !teams.includes(code(p.nflTeam))&&!['O','OUT','NA','IR','SUSP'].includes(String(p.injury||'').toUpperCase()));
    if(eligible.length<required)shortage.push({position:group,required,available:eligible.length});
  }
  return {week:w,players,startingCount:players.filter(p=>p.starting).length,shortages:shortage,
    priority:shortage.length?'critical':players.some(p=>p.starting)?'attention':'watch'};
 }).filter(x=>x.players.length||x.shortages.length);
}
function choosePriorities(model){
 const list=[];
 const week10=model.byes.find(x=>x.week===model.modelWeek);
 const needsBye=week10?.players.find(x=>x.starting);
 if(needsBye){
  const best=model.lineups.balanced;
  list.push({id:'bye-replacement',severity:'critical',
    title:'Replace '+needsBye.name+' — Week '+model.modelWeek+' bye',
    detail:best?.available&&best.inPlayers.length?
      (()=>{
        const original=model.roster;
        const replacement=best.assignments.find(a=>a.slot===needsBye.slot&&
          !original.some(p=>String(p.id)===String(a.id)&&p.slot===needsBye.slot));
        const promoted=best.inPlayers.map(p=>p.name+' into '+p.slot).join('; ');
        return 'Move '+needsBye.name+' out of the Week '+model.modelWeek+' lineup. '+
          (replacement?'Slide '+replacement.name+' into '+needsBye.slot+'; ':'')+
          'start '+promoted+'. Confirm slot eligibility and Yahoo locks before making the changes.';
      })():
      'This NFL club is on a verified bye; confirm an eligible, active substitute before kickoff.',
    evidence:'Official NFL bye schedule, plus exact roster slot assignment'});
 }
 const soon=model.byes.find(x=>x.shortages.some(s=>s.position==='TE'&&s.available===0));
 if(soon){
  list.push({id:'te-coverage',severity:'critical',title:'Week '+soon.week+' — no available rostered TE',
    detail:soon.players.filter(p=>p.position==='TE').map(p=>p.name).join(' and ')+
      ' are on bye together. Source a TE option before the waiver market tightens.',
    evidence:'Verified NFL byes + Brock Hard roster eligibility'});
 }
 if(model.lineups.balanced?.available&&model.lineups.balanced.gain>2&&model.lineups.balanced.inPlayers.length){
  list.push({id:'lineup-edge',severity:'priority',title:'Model sees '+model.lineups.balanced.gain.toFixed(1)+' projected points on the bench',
    detail:'Compare '+model.lineups.balanced.inPlayers.map(x=>x.name).join(', ')+
      ' against '+model.lineups.balanced.outPlayers.map(x=>x.name).join(', ')+'. '+
      'This is a one-week estimate, not a guaranteed gain.',
    evidence:'FantasyBot Week '+model.modelWeek+' PPR forecasts; exact Yahoo lineup slots'});
 }
 const opp=model.opponents.find(x=>x.week===model.modelWeek);
 if(opp){
  list.push({id:'opponent-intel',severity:'watch',
    title:'Scout '+opp.teamName+' — AI power rank #'+opp.rank,
    detail:'Opponent quality reflects FantasyBot roster ratings; the Yahoo team projections are a separate source.',
    evidence:'FantasyBot eight-club power ranking and Yahoo scheduled opponent'});
 }
 return list.slice(0,5);
}
export function analyzeEdge(snapshot,edge,{now=Date.now(),mode='balanced'}={}){
 try{
 if(snapshot?.schemaVersion!==3||snapshot?.season!==2026||!snapshot.teams||
  Object.keys(snapshot.teams).join(',')!=='brock')return fail('This is not the authorized Brock-only Yahoo snapshot.');
 const team=snapshot.teams.brock;
 if(String(team?.leagueId)!=='470.l.290846'||String(team?.teamId)!=='2'||!Array.isArray(team.roster))return fail('Wrong league or roster identity.');
 if(!edge||edge.schemaVersion!==1||edge.kind!=='brock-hard-prediction-inputs'||edge.season!==2026||
  String(edge.leagueId)!=='470.l.290846'||String(edge.teamId)!=='2'||edge.scoring!=='ppr')
   return fail('Verified model predictions have not yet been published.');
 if(!Number.isInteger(edge.week)||edge.week<snapshot.week||edge.week>snapshot.week+1)
  return fail('The AI predictions apply to a different fantasy week.');
 const capture=sourceDate(snapshot.syncedAtIso),observed=sourceDate(edge.observedAtIso),based=sourceDate(edge.yahooCapturedAtIso);
 if(capture===null||observed===null||based===null||capture<based||capture>now+300_000||observed>now+300_000)
  return fail('A verified capture timestamp is missing or invalid.');
 if((now-observed)/3600000>36||observed<based||Math.abs(observed-based)>72*3600000)
  return fail('AI predictions are older than the accepted 36-hour decision window.');
 const f=getFreshness(snapshot.syncedAtIso,now);
 const independentRosterRead=sourceDate(edge.rosterVerifiedAtIso);
 const independentlyCovered=independentRosterRead!==null&&independentRosterRead<=now+300000&&
  independentRosterRead>=based&&now-independentRosterRead<=24*3600000&&
  Number.isInteger(edge.rosterCrossCheckCount)&&edge.rosterCrossCheckCount>=15&&
  edge.rosterCrossCheckCount<=team.roster.length;
 const yahooAgeHours=Math.max(0,(now-capture)/3600000);
 if(!f.actionable&&(!independentlyCovered||yahooAgeHours>72))
  return fail('No recent matching FantasyBot roster verification is available for this older Yahoo capture.');
 const yahooFresh=f.actionable;
 if(!Array.isArray(edge.rosterProjections)||edge.rosterProjections.length!==team.roster.length)
  return fail('AI roster is not synchronized to Yahoo. No lineup recommendation will be made.');
 const yids=team.roster.map(p=>String(p.id)),mids=edge.rosterProjections.map(p=>String(p.id));
 if(!unique(yids)||!unique(mids)||!mids.every(id=>yids.includes(id)))return fail('Player identities do not match the current Yahoo capture.');
 const byId=new Map(edge.rosterProjections.map(p=>[String(p.id),p]));
 let players=[];
 for(const p of team.roster){
  const q=byId.get(String(p.id));
  if(!q||name(q.name)!==name(p.name)||pos(q.position)!==pos(p.position)||
     (q.projection!==null&&!npos(q.projection)))return fail('A model player failed Yahoo identity or projection validation.');
  const forecast=npos(q.projection)?q.projection:null;
  const historical=(Array.isArray(q.history)?q.history:[]).filter(x=>Number.isInteger(x.week)&&x.week<edge.week&&npos(x.points)).slice(0,8);
  players.push({...p,forecast,sigma:forecast===null?null:sampleSigma(historical,forecast,pos(p.position)),
   bye:q.byeWeek===edge.week,history:historical,modelRank:q.rank,modelOpponent:q.modelOpponent,
   modelInjury:q.modelInjury,modelTrend:q.trend,modeled:true});
 }
 const modelWeek=edge.week,slots=team.lineupSlots||{};
 const lineups={safe:lineupModel(players,slots,'safe'),
  balanced:lineupModel(players,slots,'balanced'),upside:lineupModel(players,slots,'upside')};
 const calendar=edge.teamByeWeeks||{};
 const byes=investigateByes(team.roster,modelWeek,calendar);
 const sourceTeam={...team,_capture:snapshot.syncedAtIso};
 const waiver=yahooFresh?evaluateWaivers(players,sourceTeam,edge,slots,lineups.balanced):
  {positive:[],watches:[],covered:0,total:team.availablePlayers?.length||0,
   description:'Yahoo available-player inventory is older than six hours. No acquisition recommendation is made.'};
 const opp=(team.upcomingMatchups||[]).filter(x=>Number.isInteger(x.week)&&x.week>=snapshot.week&&x.week<=modelWeek+4&&typeof x.opponent==='string')
 .map(x=>{
  const power=rankForPower(edge.leaguePower||[],x.opponent);
  return {week:x.week,teamName:x.opponent,rank:power?.rank??null,rating:power?.rating??null,
   yahooMyProjected:teamPoints(x.myProjected)?x.myProjected:null,
   yahooOppProjected:teamPoints(x.opponentProjected)?x.opponentProjected:null};
 });
 const lineup=lineups[licensed(mode)];
 const chance=lineup?.available&&opp.some(x=>x.week===modelWeek&&x.yahooOppProjected!==null)?
 (()=>{const target=opp.find(x=>x.week===modelWeek);
  const value=estimateWinChance(lineup.mean,target.yahooOppProjected,
    Math.max(6,lineup.estimatedSigma),25);
  return value===null?null:{value,opponent:target.teamName,
   assumptions:'Illustrative uncalibrated Normal model, independent player variance and 25-point opponent SD. Mixed FantasyBot PPR and Yahoo team projections; NOT a bookmaker or Yahoo win probability.'};
 })():null;
 const currentPower=rankForPower(edge.leaguePower||[],team.name);
 const model={ready:true,status:'experimental',scoring:'ppr',modelWeek,mode:licensed(mode),
  modelCapturedAtIso:edge.observedAtIso,yahooCapturedAtIso:snapshot.syncedAtIso,modelAgeHours:round(Math.max(0,(now-observed)/3600000),1),
  lineup, lineups,roster:players,waivers:waiver,byes,opponents:opp,illustrativeChance:chance,
  powerRank:currentPower?.rank??null,powerRating:currentPower?.rating??null,
  coverage:{all:players.length,projected:players.filter(p=>p.forecast!==null).length,
    eligible:players.filter(active).length,eligibleCovered:players.filter(p=>active(p)&&p.forecast!==null).length,
    available:waiver.covered,availableTotal:waiver.total},
  quality:{yahooFresh,yahooAgeHours:round(yahooAgeHours,1),independentRosterAt:edge.rosterVerifiedAtIso||null,
    label:lineups.balanced.available?'Complete non-IR Week '+modelWeek+' projection coverage':'Partial projection coverage',
    notes:['FantasyBot PPR predictions, not official Yahoo league-bonus-adjusted numbers.',
      'One-week projection errors can be large; ranges are model illustrations, not validated percentiles.',
      'Player, waiver, lock and injury statuses require live Yahoo checks.',
      'Power ratings are FantasyBot relative strengths, NOT playoff odds.']},
  sources:[...(edge.sources||[]).map(x=>({label:x.label,date:x.date})),
   ...(edge.scheduleSource?[{label:'NFL schedule',url:edge.scheduleSource.url,date:edge.scheduleSource.checkedAtIso}]:[])]};
 model.priorities=choosePriorities(model);
 return model;
 }catch(err){return fail('Prediction engine could not safely reconcile the provider sources.',String(err?.message||err))}
}
