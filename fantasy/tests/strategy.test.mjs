import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildStrategicReport} from '../assets/strategy-engine.mjs';
const read=p=>JSON.parse(readFileSync(p,'utf8'));
const yahoo=()=>read('fantasy/data.json');
const edge=()=>read('fantasy/edge.json');
const league=()=>read('fantasy/intelligence.json');
const now=()=>Date.parse(league().capturedAtIso)+2*60000;
const run=(opts={})=>buildStrategicReport(yahoo(),edge(),league(),{now:now(),simulations:900,...opts});
test('Brock-only evidence validates 32 actual league results and all 8 standings and 20 fixtures',()=>{
 const m=run();
 assert.equal(m.ready,true,m.reason);
 assert.equal(m.calibration.matchups,32);
 assert.equal(m.calibration.teamObservations,64);
 assert.equal(m.rankings.length,8);
 assert.equal(m.upcoming.length,5);
 assert.equal(m.calibration.winnerCorrect,18);
 assert.equal(m.calibration.winnerTested,32);
 assert.equal(m.calibration.winnerAccuracy,56.3);
 assert.ok(m.calibration.mae>18&&m.calibration.mae<20);
 assert.ok(m.calibration.rmse>22&&m.calibration.rmse<24);
 assert.equal(m.league.standing.rank,1);
});
test('Official full PPR rules prevent inventing bonus scoring, K/DEF remain component-limited',()=>{
 const m=run();
 assert.ok(m.scoring.verifiedPPR);
 assert.ok(m.scoring.offensiveBonusThresholdsAbsent);
 assert.ok(m.scoring.specialTeamsForecastGap);
 assert.match(m.scoring.note[0],/standard full-PPR/);
 const mod=league().leagueScoring.statModifiers;
 assert.equal(mod.find(x=>x.id==='11').value,1);
 assert.equal(mod.find(x=>x.id==='4').value,.04);
 assert.equal(mod.find(x=>x.id==='22').value,4);
});
test('Conditional playoff simulator shows model assumptions and W9 provisional win outcome',()=>{
 const m=run();
 assert.ok(m.odds);
 for(const s of ['baseline','optimized']){
  const x=m.odds[s];
  for(const field of ['top4','top6','firstSeed','week10Win']){
   assert.ok(x[field]>=0&&x[field]<=100,field+' '+x[field]);
  }
  assert.ok(x.top6>=x.top4);
  assert.ok(x.expectedWins>=6&&x.expectedWins<=14);
 }
 assert.ok(m.odds.delta.top4>=0);
 assert.ok(m.odds.delta.top6>=0);
 assert.ok(m.odds.delta.week10Win>=0);
 assert.equal(m.odds.assumptions.length,6);
 assert.match(m.odds.assumptions.join(' '),/actual playoff timing not verified/);
 assert.match(m.odds.source,/Yahoo W1–8/);
});
test('Week 13 TE crisis and market-target trade are supported by separate sources',()=>{
 const m=run();
 assert.equal(m.week13.te13Shortage,true);
 assert.ok(m.week13.rosteredTightEnds.includes('Brock Bowers'));
 assert.ok(m.week13.rosteredTightEnds.includes('Mark Andrews'));
 const market=m.week13.market.find(p=>p.name==='Dallas Goedert');
 assert.ok(market&&market.notWeek13Bye===true);
 const kelce=m.trade.find(p=>p.target==='Travis Kelce');
 assert.equal(kelce.outgoing,'Woody Marks');
 assert.equal(kelce.fit,true);
 assert.equal(kelce.recommendation,'investigate');
 assert.equal(kelce.notOnByeWeek13,true);
 const overpay=m.trade.find(p=>p.outgoing==='Breece Hall');
 assert.equal(overpay.recommendation,'do-not-propose');
});
test('Records and power ranks distinguish real opponent strength from standings luck',()=>{
 const m=run();
 const jersey=m.rankings.find(t=>t.name==='Jersey junkyard');
 assert.equal(jersey.rank,7);
 assert.equal(jersey.powerRank,3);
 assert.equal(jersey.rankDislocation,4);
 assert.ok(m.exposure.topThreats.some(g=>g.opponent==='Jersey junkyard'));
 assert.ok(m.exposure.topThreats.some(g=>g.opponent==='Hazleton Coal Mine'));
 const rival=m.upcoming.find(x=>x.week===13);
 assert.equal(rival.opponent,'Frenchville HornHog');
 assert.ok(rival.projectedMargin<0);
});
test('Invalid season, source identity, season totals and missing matchups fail shut',()=>{
 const y=yahoo(),e=edge(),i=league();
 const bad1=structuredClone(y);bad1.teams.quick={name:'Another private team'};
 assert.equal(buildStrategicReport(bad1,e,i,{now:now()}).ready,false);
 const bad2=structuredClone(i);bad2.leagueId='470.l.other';
 assert.equal(buildStrategicReport(y,e,bad2,{now:now()}).ready,false);
 const bad3=structuredClone(i);bad3.futureSchedule.pop();
 assert.equal(buildStrategicReport(y,e,bad3,{now:now()}).ready,false);
 const bad4=structuredClone(i);bad4.teams[0].pointsFor=-999;
 assert.equal(buildStrategicReport(y,e,bad4,{now:now()}).ready,false);
 const bad5=structuredClone(i);bad5.history[0].homePoints=9999;
 assert.equal(buildStrategicReport(y,e,bad5,{now:now()}).ready,false);
 const changed=structuredClone(y);changed.week=10;
 assert.equal(buildStrategicReport(changed,e,i,{now:now()}).ready,false);
});
test('Source aging hides actionable available players but preserves labeled historical evidence',()=>{
 const y=yahoo(),e=edge(),i=league();
 const aged=buildStrategicReport(y,e,i,{now:Date.parse(y.syncedAtIso)+8*3600000,simulations:500});
 assert.equal(aged.ready,true,aged.reason);
 assert.equal(aged.status,'historical-research');
 assert.equal(aged.waiverPriorities.length,0);
 assert.ok(aged.calibration.matchups===32);
});
test('Intel sidecar public data excludes sensitive owner metadata and requires exact records',()=>{
 const s=readFileSync('fantasy/intelligence.json','utf8');
 assert.ok(s.length<250000);
 assert.doesNotMatch(s,/ownerId|ownerName|email|clientSecret|accessToken|refreshToken|cookie|password/i);
 const i=league();assert.deepEqual(Object.keys(i.teams.map(x=>x.id).reduce((m,id)=>({...m,[id]:true}),{})).sort(),['1','2','3','4','5','6','7','8']);
 assert.equal(i.tradeResearch.prospects.length,3);
 const m=run();
 assert.equal(m.scoring.verifiedPPR,true);
});
