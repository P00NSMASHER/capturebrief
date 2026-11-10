import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {analyzeEdge} from '../assets/edge-engine.mjs';
const source=()=>JSON.parse(readFileSync('fantasy/tests/fixtures/historical-week10/data.json','utf8'));
const inputs=()=>JSON.parse(readFileSync('fantasy/tests/fixtures/historical-week10/edge.json','utf8'));
// A scheduled Yahoo capture can legitimately advance after the independent model read.
// Keep tests anchored AFTER both sources, not to a stale hard-coded capture time.
const at=edge=>Math.max(Date.parse(edge.observedAtIso),Date.parse(source().syncedAtIso))+10*60000;
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
 const src=readFileSync('fantasy/tests/fixtures/historical-week10/edge.json','utf8');
 const d=JSON.parse(src);
 assert.equal(d.kind,'brock-hard-prediction-inputs');
 assert.deepEqual(Object.keys(source().teams),['brock']);
 assert.equal(d.week,source().week+1);
 assert.doesNotMatch(src,/ownerId|ownerEmail|refreshToken|accessToken|clientSecret|privateKey|cookie/i);
 const engine=readFileSync('fantasy/assets/edge-engine.mjs','utf8');
 assert.doesNotMatch(engine,/fetch\(|XMLHttpRequest|WebSocket|submitTrade|submitWaiver|claimPlayer/);
 assert.equal(d.sources.length,2);
});


test('Independently rechecked FantasyBot roster enables research-only predictions after Yahoo passes six hours',()=>{
 const yy=source(),ee=inputs();
 const now=Math.max(Date.parse(ee.observedAtIso)+9*3600000,Date.parse(yy.syncedAtIso)+7*3600000);
 const model=analyzeEdge(yy,ee,{now});
 assert.equal(model.ready,true,JSON.stringify(model));
 assert.equal(model.quality.yahooFresh,false);
 assert.ok(model.quality.yahooAgeHours>6);
 assert.equal(model.lineups.balanced.available,true);
 assert.ok(model.priorities.some(x=>x.id==='bye-replacement'));
 assert.equal(model.waivers.positive.length,0);
 assert.equal(model.waivers.watches.length,0);
 const unverified=structuredClone(ee);delete unverified.rosterVerifiedAtIso;
 assert.equal(analyzeEdge(yy,unverified,{now}).ready,false);
 const staleRoster=structuredClone(ee);staleRoster.rosterVerifiedAtIso=
   new Date(Date.parse(ee.observedAtIso)-26*3600000).toISOString();
 assert.equal(analyzeEdge(yy,staleRoster,{now}).ready,false);
});

test('A Yahoo snapshot older than the model source baseline cannot be silently paired with newer model observations',()=>{
 const yy=source(),ee=inputs();
 const now=Date.parse(ee.observedAtIso)+3600000;
 yy.syncedAtIso=new Date(Date.parse(ee.yahooCapturedAtIso)-5*60000).toISOString();
 assert.equal(analyzeEdge(yy,ee,{now}).ready,false);
});

test('Yahoo opponent forecasts above 100 points survive independent-source validation',()=>{
 const y=source(),edge=inputs();
 const model=analyzeEdge(y,edge,{now:at(edge)});
 assert.equal(model.ready,true,JSON.stringify(model));
 const next=model.opponents.find(x=>x.week===10);
 assert.equal(next.teamName,'Josh ❤️creampies');
 const nextYahoo=y.teams.brock.upcomingMatchups.find(x=>x.week===10);
 assert.equal(next.yahooMyProjected,nextYahoo.myProjected);
 assert.equal(next.yahooOppProjected,nextYahoo.opponentProjected);
 assert.ok(next.yahooMyProjected>100&&next.yahooOppProjected>100);
 const week12=model.opponents.find(x=>x.week===12);
 const week12Yahoo=y.teams.brock.upcomingMatchups.find(x=>x.week===12);
 assert.equal(week12.yahooMyProjected,week12Yahoo.myProjected);
 assert.equal(week12.yahooOppProjected,week12Yahoo.opponentProjected);
 assert.ok(model.illustrativeChance===null||model.illustrativeChance.value>0);
 const bad=structuredClone(y);
 bad.teams.brock.upcomingMatchups[0].opponentProjected=9000;
 const changed=analyzeEdge(bad,edge,{now:at(edge)});
 assert.equal(changed.ready,true);
 assert.equal(changed.opponents.find(x=>x.week===10).yahooOppProjected,null);
});
test('Week 10 bye priority explains a valid multi-slot replacement instead of implying WR fills RB',()=>{
 const m=analyze();
 assert.equal(m.ready,true);
 const bye=m.priorities.find(x=>x.id==='bye-replacement');
 assert.ok(bye);
 assert.match(bye.detail,/Move Jonah Coleman out/);
 assert.match(bye.detail,/Slide Rhamondre Stevenson into RB/);
 assert.match(bye.detail,/Zay Flowers into W\/R\/T/);
 assert.match(bye.detail,/Yahoo locks/);
 const assigned=m.lineup.assignments.find(x=>x.name==='Rhamondre Stevenson');
 assert.equal(assigned?.slot,'RB');
 const promoted=m.lineup.assignments.find(x=>x.name==='Zay Flowers');
 assert.equal(promoted?.slot,'W/R/T');
});
