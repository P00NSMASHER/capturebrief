import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {analyzeEdge} from '../assets/edge-engine.mjs';
const source=()=>JSON.parse(readFileSync('fantasy/data.json','utf8'));
const inputs=()=>JSON.parse(readFileSync('fantasy/edge.json','utf8'));
const at=(edge)=>Date.parse(edge.observedAtIso)+10*60000;
const analyze=(risk='balanced')=>{const y=source(),edge=inputs();return analyzeEdge(y,edge,{now:at(edge),mode:risk})};

test('Only matching 2026 Brock Yahoo and explicit Week 10 model input can power the Edge lab',()=>{
 const m=analyze();
 assert.equal(m.ready,true,JSON.stringify(m));
 assert.equal(m.modelWeek,10);
 assert.equal(m.scoring,'ppr');
 assert.equal(m.coverage.all,18);
 assert.equal(m.coverage.eligible,m.coverage.eligibleCovered);
 assert.equal(m.coverage.eligible,16);
 assert.equal(m.roster.filter(x=>x.forecast!==null).length,17);
 assert.equal(m.powerRank,1);
 assert.equal(m.opponents.find(x=>x.teamName==='Jersey junkyard').rank,3);
 assert.equal(m.opponents.find(x=>x.teamName==='Josh ❤️creampies').rank,7);
});

test('A verified Denver bye makes Jonah Coleman a zero and gives a source-backed lineup alternative',()=>{
 const m=analyze();
 assert.equal(m.lineups.balanced.available,true,JSON.stringify(m.lineups.balanced));
 const jonah=m.roster.find(x=>x.name==='Jonah Coleman');
 assert.equal(jonah.forecast,0);
 assert.equal(jonah.bye,true);
 assert.ok(m.lineups.balanced.outPlayers.some(x=>x.name==='Jonah Coleman'));
 assert.ok(m.lineups.balanced.inPlayers.length>=1);
 assert.ok(m.lineups.balanced.assignments.some(x=>x.slot==='RB'&&x.position==='RB'));
 assert.ok(m.lineups.balanced.gain>0);
 assert.ok(m.priorities.find(x=>x.id==='bye-replacement'&&x.severity==='critical'));
});

test('Week 13 official schedule exposes the double-TE bye and Week 11 NE flex bye',()=>{
 const m=analyze();
 const wk13=m.byes.find(x=>x.week===13),wk11=m.byes.find(x=>x.week===11);
 assert.ok(wk13);
 assert.ok(wk13.players.some(x=>x.name==='Brock Bowers'));
 assert.ok(wk13.players.some(x=>x.name==='Mark Andrews'));
 assert.ok(wk13.shortages.some(x=>x.position==='TE'&&x.available===0));
 assert.ok(wk11.players.some(x=>x.name==='Rhamondre Stevenson'));
 assert.ok(m.priorities.some(x=>x.id==='te-coverage'));
});

test('Cautious, balanced and upside modes are real choices with explicit risk assumptions',()=>{
 const a=analyze('safe'),b=analyze('balanced'),c=analyze('upside');
 assert.ok(a.ready&&b.ready&&c.ready);
 assert.equal(a.mode,'safe'); assert.equal(c.mode,'upside');
 assert.ok(a.lineup.available&&b.lineup.available&&c.lineup.available);
 assert.ok(a.lineup.score<=c.lineup.score);
 assert.ok(b.lineup.estimatedSigma>0);
 assert.ok(b.lineup.illustrativeLow<=b.lineup.mean);
 assert.ok(b.lineup.illustrativeHigh>=b.lineup.mean);
 assert.match(b.lineup.note,/no calibrated prediction interval/);
 assert.ok(b.illustrativeChance===null||/uncalibrated/.test(b.illustrativeChance.assumptions));
});

test('Waiver candidates require BOTH Yahoo league availability and explicit Week 10 model projection',()=>{
 const m=analyze();
 assert.equal(m.waivers.covered,16);
 assert.equal(m.waivers.total,25);
 assert.ok(m.waivers.watches.some(x=>x.name==='Bryce Young'));
 assert.ok(!m.waivers.watches.some(x=>x.name==='Lamar Jackson'));
 for(const p of m.waivers.positive){
  assert.ok(source().teams.brock.availablePlayers.some(x=>x.id===p.add.id));
  assert.ok(p.projectedWeeklyUplift>=0.75);
 }
 const tampered=inputs();tampered.availableProjections.push({id:'danger',name:'Unavailable Player',position:'WR',projection:28});
 const e=analyzeEdge(source(),tampered,{now:at(tampered)});
 assert.ok(e.waivers.watches.every(x=>x.name!=='Unavailable Player'));
});

test('Wrong source identity, future timestamps, rollover, stale data, and roster drift fail closed',()=>{
 const y=source(),edge=inputs(),now=at(edge);
 const bad=structuredClone(edge);
 bad.teamId='7';assert.equal(analyzeEdge(y,bad,{now}).ready,false);
 bad.teamId='2';bad.leagueId='another';assert.equal(analyzeEdge(y,bad,{now}).ready,false);
 bad.leagueId='470.l.290846';bad.week=12;assert.equal(analyzeEdge(y,bad,{now}).ready,false);
 bad.week=10;bad.observedAtIso=new Date(now+5*86400000).toISOString();assert.equal(analyzeEdge(y,bad,{now}).ready,false);
 const stale=analyzeEdge(y,edge,{now:now+40*3600000});assert.equal(stale.ready,false);
 const changed=structuredClone(y);changed.teams.brock.roster[0].id='unknown';
 assert.equal(analyzeEdge(changed,edge,{now}).ready,false);
 const mixed=structuredClone(y);mixed.teams.other={name:'other owned team'};
 assert.equal(analyzeEdge(mixed,edge,{now}).ready,false);
});

test('Incomplete forecast coverage withholds lineup optimality, not fabricated number',()=>{
 const e=inputs();e.rosterProjections.find(x=>x.name==='Trevor Lawrence').projection=null;
 const m=analyzeEdge(source(),e,{now:at(e)});
 assert.equal(m.ready,true);
 assert.equal(m.lineups.balanced.available,false);
 assert.ok(!Number.isFinite(m.lineups.balanced.score));
 assert.equal(m.illustrativeChance,null);
});

test('No private identity, tokens, current-week fake forecasts or provider writes appear in the model files',()=>{
 const src=readFileSync('fantasy/edge.json','utf8');
 const d=JSON.parse(src);
 assert.equal(d.kind,'brock-hard-prediction-inputs');
 assert.deepEqual(Object.keys(source().teams),['brock']);
 assert.equal(d.week,source().week+1);
 assert.doesNotMatch(src,/ownerId|ownerEmail|refreshToken|accessToken|clientSecret|privateKey|cookie/i);
 const engine=readFileSync('fantasy/assets/edge-engine.mjs','utf8');
 assert.doesNotMatch(engine,/fetch\(|XMLHttpRequest|WebSocket|submitTrade|submitWaiver|claimPlayer/);
 assert.equal(d.sources.length,2);
});
