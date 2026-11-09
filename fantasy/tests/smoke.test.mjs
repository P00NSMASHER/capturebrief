import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {TEAM_IDS,normalizeSnapshot,getFreshness,compareScoredLineup,rosterStatusAlerts} from '../assets/engine.mjs';
const file=p=>readFileSync(p,'utf8');
test('Brock is the only navigable personal team; legacy links redirect without fetching other teams',()=>{
 assert.deepEqual(TEAM_IDS,['brock']);
 for(const p of ['fantasy/index.html','fantasy/brock/index.html']){
  const html=file(p);assert.match(html,/id="root"/);assert.match(html,/app-v2\.mjs/);assert.match(html,/manifest\.webmanifest/);
 }
 for(const id of ['quick','highlight']){
  const html=file('fantasy/'+id+'/index.html');
  assert.match(html,/location\.replace\("\/capturebrief\/fantasy\/brock\/"\)/);
  assert.doesNotMatch(html,/app-v2\.mjs/);
 }
 const app=file('fantasy/assets/app-v2.mjs');
 assert.doesNotMatch(app,/THREE LEAGUES|Compare all three|All teams|function homeView\(|function teamCard\(/);
 assert.match(app,/function onlyBrockRaw/);
});
test('published data archives only Brock and never invents future projections',()=>{
 const raw=JSON.parse(file('fantasy/data.json'));
 assert.deepEqual(Object.keys(raw.teams),['brock']);
 const snap=normalizeSnapshot(raw);
 assert.deepEqual(Object.keys(snap.teams),['brock']);
 assert.ok(!Number.isNaN(Date.parse(snap.syncedAtIso)));
 assert.equal(snap.teams.brock.projectionCoverage,'none');
 assert.ok(snap.teams.brock.roster.length>0);
 assert.ok(snap.teams.brock.roster.every(p=>p.projection===null));
 assert.equal(getFreshness('2026-09-30T14:10:03Z').actionable,false);
});
test('multi-team private import and prior browser storage are sanitized to Brock',()=>{
 const raw=JSON.parse(file('fantasy/tests/fixtures/private-v3.sample.json'));
 const mixed={...raw,teams:{...raw.teams,quick:{name:'PRIVATE QUICK'},highlight:{name:'PRIVATE HIGHLIGHT'}}};
 assert.deepEqual(Object.keys(normalizeSnapshot(mixed).teams),['brock']);
 assert.equal(normalizeSnapshot(mixed).teams.brock.projectionCoverage,'complete');
 const app=file('fantasy/assets/app-v2.mjs');
 assert.match(app,/const brockOnly=preparePrivateImport\(raw/);
 assert.match(app,/localStorage\.setItem\(PRIVATE_KEY,JSON\.stringify\(brockOnly\)\)/);
 assert.match(app,/const safe=onlyBrockRaw\(JSON\.parse\(stored\)\)/);
});
test('PWA and refresh retain Brock-only scope',()=>{
 const m=JSON.parse(file('fantasy/manifest.webmanifest'));
 assert.equal(m.scope,'/capturebrief/fantasy/');
 assert.equal(m.display,'standalone');
 assert.match(file('fantasy/assets/app-v2.mjs'),/cache:'no-store'/);
});

test('current Brock Yahoo data produces real roster alerts and scored-lineup context',()=>{
 const raw=JSON.parse(file('fantasy/data.json'));
 const snap=normalizeSnapshot(raw),team=snap.teams.brock;
 const alerts=rosterStatusAlerts(team.roster);
 assert.equal(alerts.length,4);
 assert.ok(alerts.some(a=>a.name==='Rhamondre Stevenson'&&a.status==='Q'));
 const scored=compareScoredLineup(team.roster,team.lineupSlots);
 assert.equal(scored.available,true);
 assert.equal(scored.current,148.58);
 assert.equal(scored.best,160.28);
 assert.equal(scored.gap,11.7);
 const app=file('fantasy/assets/app-v2.mjs');
 assert.match(app,/Highest-scoring lineup so far/);
 assert.match(app,/Playoff race/);
 assert.match(app,/Trade preparation/);
 assert.doesNotMatch(app,/No saved alerts|Full-season simulation not rated|Opponent roster valuation unavailable/);
});
