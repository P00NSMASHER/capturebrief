import test from 'node:test';
import assert from 'node:assert/strict';
import {getFreshness,normalizeSnapshot,rosterBuckets,optimizeLineup,estimateWinChance,rankWaiverTargets,simulatePlayoffs,isSafeUrl,slotsFromRoster,rosterStatusAlerts,compareScoredLineup,marketWatchlist,positionDepth} from '../assets/engine.mjs';

const at=Date.parse('2026-11-08T20:00:00Z');
test('archive threshold and future timestamps never imply freshness of old data',()=>{
  assert.equal(getFreshness('2026-09-30T14:10:03Z',at).state,'stale');
  assert.equal(getFreshness('2026-11-08T18:00:00Z',at).state,'fresh');
  assert.equal(getFreshness('not a date',at).actionable,false);
  assert.equal(getFreshness('2026-11-09T20:00:00Z',at).state,'unknown');
});
test('preserves only Brock Hard when a legacy snapshot contains other personal teams',()=>{
  const raw={syncedAtIso:'2026-09-30T14:10:03Z',week:4,teams:{
    brock:{short:'Brock',full:'Brock Hard',lineup:[{slot:'QB',name:'X'}],snapshot:{roster:[{name:'X',slot:'QB',position:'QB'}]}},
    quick:{short:'Quick'},highlight:{short:'Highlight'},taco:{short:'Excluded'}}};
  const out=normalizeSnapshot(raw);
  assert.deepEqual(Object.keys(out.teams),['brock']);
  assert.equal(out.teams.quick,undefined);
  assert.equal(out.teams.highlight,undefined);
  assert.equal(out.teams.brock.roster[0].projection,null);
  assert.equal(out.teams.brock.rawLegacy,true);
});
test('exact optimizer beats greedy flex selection with no double-counting',()=>{
  const r=[
    {name:'A',position:'RB',slot:'RB',projection:18,eligiblePositions:['RB']},
    {name:'B',position:'RB',slot:'BN',projection:17,eligiblePositions:['RB']},
    {name:'C',position:'WR',slot:'WR',projection:16,eligiblePositions:['WR']},
    {name:'D',position:'WR',slot:'BN',projection:25,eligiblePositions:['WR']}
  ];
  const o=optimizeLineup(r,{RB:1,WR:1,FLEX:1});
  assert.equal(o.available,true);
  assert.equal(o.score,60); // 18 + 17 + 25 (other WR can sit)
  assert.equal(o.assignments.length,3);
  assert.equal(new Set(o.assignments.map(p=>p.player.name)).size,3);
});
test('does not invent projections, overrule locks, or use IR players',()=>{
  const base=[{name:'X',position:'QB',slot:'QB',projection:null,eligiblePositions:['QB']}];
  assert.equal(optimizeLineup(base,{QB:1}).available,false);
  assert.equal(optimizeLineup([{...base[0],projection:22,locked:true}],{QB:1}).available,false);
  assert.equal(optimizeLineup([{...base[0],projection:22,injury:'OUT'}],{QB:1}).available,false);
});
test('Flaim v3 preserves actual points, zero probability and roster flags without fabricating projections',()=>{
 const x=normalizeSnapshot({schemaVersion:3,source:'Flaim Fantasy',syncedAtIso:'2026-11-08T23:34:00Z',teams:{brock:{name:'Fictional',roster:[{id:'1',name:'Test RB',position:'RB',slot:'RB',actualPoints:0,projection:null,editable:false,cantCut:true}],projectionCoverage:'none',matchup:{home:{teamId:'2',winProbability:0},away:{teamId:'3',winProbability:1}}}}});
 assert.equal(x.teams.brock.roster[0].actualPoints,0);
 assert.equal(x.teams.brock.roster[0].projection,null);
 assert.equal(x.teams.brock.roster[0].cantCut,true);
 assert.equal(x.teams.brock.matchup.home.winProbability,0);
});
test('waivers fail closed without complete league projections',()=>{
  assert.equal(rankWaiverTargets({projectionCoverage:'none',availablePlayers:[]}).available,false);
});
test('matchup chance is a model only when both variance inputs exist',()=>{
  assert.equal(estimateWinChance(100,100,15,15),50);
  assert.ok(estimateWinChance(120,100,15,15)>70);
  assert.equal(estimateWinChance(120,100,null,15),null);
});
test('playoff simulation deterministic and requires full fixture evidence',()=>{
  const t=[{id:'a',wins:5,losses:1,pointsFor:600},{id:'b',wins:1,losses:5,pointsFor:400}];
  const opts={teams:t,schedule:[{home:'a',away:'b',homeWinChance:.85}],playoffSpots:1,iterations:300,seed:99};
  assert.deepEqual(simulatePlayoffs(opts),{a:100,b:0});
});
test('links only to expected Yahoo fantasy host',()=>{
  assert.equal(isSafeUrl('https://football.fantasysports.yahoo.com/f1/290846'),true);
  assert.equal(isSafeUrl('https://evil.example/yahoo'),false);
});
test('bench and reserve classification is explicit',()=>{
  const r=[{slot:'QB'},{slot:'BN'},{slot:'IR'}];
  assert.equal(rosterBuckets(r).starters.length,1);
  assert.equal(rosterBuckets(r).bench.length,1);
  assert.equal(rosterBuckets(r).reserve.length,1);
  assert.deepEqual(slotsFromRoster(r),{QB:1});
});

test('roster health badges are derived from Yahoo flags, not absent manual alerts',()=>{
 const alerts=rosterStatusAlerts([{id:'1',name:'A',injury:'Q',slot:'W/R/T'},{id:'2',name:'B',injury:'O',slot:'IR'},
   {id:'3',name:'C',injury:'NA',slot:'IR'},{id:'4',name:'D',injury:null,slot:'WR'}]);
 assert.equal(alerts.length,3);
 assert.equal(alerts[0].status,'Q');
 assert.equal(alerts[1].level,'urgent');
 assert.ok(alerts[2].text.includes('NA'));
});
test('week-to-date best lineup is scored-point hindsight, never forecast or advice',()=>{
 const roster=[
  {id:'1',name:'Quarterback',position:'QB',slot:'QB',eligiblePositions:['QB'],actualPoints:10,locked:true},
  {id:'2',name:'Starter',position:'WR',slot:'WR',eligiblePositions:['WR'],actualPoints:0},
  {id:'3',name:'Bench',position:'WR',slot:'BN',eligiblePositions:['WR'],actualPoints:7},
  {id:'4',name:'Kicker',position:'K',slot:'K',eligiblePositions:['K'],actualPoints:3},
  {id:'5',name:'Reserve',position:'WR',slot:'IR',eligiblePositions:['WR','IR'],actualPoints:100}
 ];
 const r=compareScoredLineup(roster,{QB:1,WR:1,K:1});
 assert.equal(r.available,true);
 assert.equal(r.current,13);
 assert.equal(r.best,20);
 assert.equal(r.gap,7);
 assert.deepEqual(r.in,['Bench']);
 assert.deepEqual(r.out,['Starter']);
 assert.match(r.note,/not a lineup recommendation/i);
 assert.equal(compareScoredLineup(roster.map(p=>p.id==='3'?{...p,actualPoints:null}:p),{QB:1,WR:1,K:1}).available,false);
 assert.equal(compareScoredLineup([...roster,{...roster[0]}],{QB:1,WR:1,K:1}).available,false);
});
test('scouting sorts only verified Yahoo-wide roster rates, not fabricated uplift',()=>{
 const rows=[{id:'a',name:'A',percentOwned:61,acquisitionState:'waivers'},
  {id:'b',name:'B',percentOwned:90,acquisitionState:'free_agent'},
  {id:'c',name:'C',percentOwned:null,acquisitionState:'waivers'},
  {id:'x',name:'X',percentOwned:100,acquisitionState:null}];
 assert.deepEqual(marketWatchlist(rows).map(x=>x.name),['B','A']);
 assert.deepEqual(positionDepth([{id:'a',name:'Receiver A',position:'WR',slot:'WR',injury:'Q'},{id:'b',name:'Receiver B',position:'WR',slot:'IR',injury:'O'}]),[
   {position:'WR',total:2,active:1,flagged:2}]);
});

test('forecast optimizer preserves existing slot assignments when identical point scores allow it',()=>{
 const roster=[
  {id:'w1',name:'Receiver One',position:'WR',slot:'WR',eligiblePositions:['WR','W/R/T'],projection:17,locked:false},
  {id:'w2',name:'Receiver Two',position:'WR',slot:'W/R/T',eligiblePositions:['WR','W/R/T'],projection:16,locked:false},
  {id:'r1',name:'Runner',position:'RB',slot:'RB',eligiblePositions:['RB','W/R/T'],projection:15,locked:false}
 ];
 const best=optimizeLineup(roster,{RB:1,WR:1,'W/R/T':1});
 assert.equal(best.available,true);
 assert.equal(best.gain,0);
 assert.equal(best.assignments.find(x=>x.player.id==='w1').slot,'WR');
 assert.equal(best.assignments.find(x=>x.player.id==='w2').slot,'W/R/T');
 assert.equal(best.assignments.find(x=>x.player.id==='r1').slot,'RB');
});
test('forecast optimizer only changes RB/FLEX positions required for a real bye replacement',()=>{
 const roster=[
  {id:'bye',name:'Bye RB',position:'RB',slot:'RB',eligiblePositions:['RB','W/R/T'],projection:0,locked:false},
  {id:'flexRB',name:'Flex RB',position:'RB',slot:'W/R/T',eligiblePositions:['RB','W/R/T'],projection:12,locked:false},
  {id:'wr1',name:'WR One',position:'WR',slot:'WR',eligiblePositions:['WR','W/R/T'],projection:20,locked:false},
  {id:'wr2',name:'Bench WR',position:'WR',slot:'BN',eligiblePositions:['WR','W/R/T'],projection:17,locked:false}
 ];
 const best=optimizeLineup(roster,{RB:1,WR:1,'W/R/T':1});
 assert.equal(best.available,true);
 assert.equal(best.gain,17);
 assert.equal(best.assignments.find(x=>x.player.name==='Flex RB').slot,'RB');
 assert.equal(best.assignments.find(x=>x.player.name==='WR One').slot,'WR');
 assert.equal(best.assignments.find(x=>x.player.name==='Bench WR').slot,'W/R/T');
});
