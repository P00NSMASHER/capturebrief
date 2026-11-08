import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalizeSnapshot,getFreshness,TEAM_IDS} from '../assets/engine.mjs';

const file=path=>readFileSync(path,'utf8');
test('all existing public page URLs remain backed by executable v2 shells',()=>{
 for(const id of ['',...TEAM_IDS]){
   const path=id?'fantasy/'+id+'/index.html':'fantasy/index.html';
   const html=file(path);
   assert.match(html,/id="root"/);
   assert.match(html,/type="module"/);
   assert.match(html,/app-v2\.mjs/);
   assert.match(html,/manifest\.webmanifest/);
   if(id)assert.match(html,new RegExp('data-team="'+id+'"'));
 }
});
test('checked-in legacy snapshot remains readable without inventing projections',()=>{
 const raw=JSON.parse(file('fantasy/data.json'));
 const snap=normalizeSnapshot(raw);
 assert.deepEqual(Object.keys(snap.teams),TEAM_IDS);
 assert.equal(getFreshness(snap.syncedAtIso).actionable,false);
 for(const t of Object.values(snap.teams)){
   assert.equal(t.projectionCoverage,'none');
   assert.ok(t.roster.length>0);
   assert.ok(t.roster.every(p=>p.projection===null));
 }
});
test('manifest retains GitHub Pages base prefix and standalone mode',()=>{
 const m=JSON.parse(file('fantasy/manifest.webmanifest'));
 assert.equal(m.scope,'/capturebrief/fantasy/');
 assert.equal(m.display,'standalone');
 assert.match(file('fantasy/assets/app-v2.mjs'),/cache:'no-store'/);
});
test('valid v3 private sample activates strict projections and cross-league isolation',()=>{
 const raw=JSON.parse(file('fantasy/tests/fixtures/private-v3.sample.json'));
 const normalized=normalizeSnapshot(raw);
 assert.equal(normalized.schemaVersion,3);
 assert.equal(normalized.teams.brock.projectionCoverage,'complete');
 assert.ok(!('taco' in normalized.teams));
});
