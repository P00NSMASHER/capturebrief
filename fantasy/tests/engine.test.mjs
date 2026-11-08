import test from 'node:test';
import assert from 'node:assert/strict';
import {getFreshness,normalizeSnapshot,rosterBuckets,optimizeLineup,estimateWinChance,rankWaiverTargets,simulatePlayoffs,isSafeUrl,slotsFromRoster} from '../assets/engine.mjs';

const at=Date.parse('2026-11-08T20:00:00Z');
test('archive threshold and future timestamps never imply freshness of old data',()=>{
  assert.equal(getFreshness('2026-09-30T14:10:03Z',at).state,'stale');
  assert.equal(getFreshness('2026-11-08T18:00:00Z',at).state,'fresh');
  assert.equal(getFreshness('not a date',at).actionable,false);
  assert.equal(getFreshness('2026-11-09T20:00:00Z',at).state,'unknown');
});
test('preserves exactly the three requested teams from a legacy snapshot',()=>{
  const raw={syncedAtIso:'2026-09-30T14:10:03Z',week:4,teams:{
    brock:{short:'Brock',full:'Brock Hard',lineup:[{slot:'QB',name:'X'}],snapshot:{roster:[{name:'X',slot:'QB',position:'QB'}]}},
    quick:{short:'Quick'},highlight:{short:'Highlight'},taco:{short:'Excluded'}}};
  const out=normalizeSnapshot(raw);
  assert.deepEqual(Object.keys(out.teams),['brock','quick','highlight']);
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
