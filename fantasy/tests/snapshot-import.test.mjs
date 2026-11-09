import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {preparePrivateImport} from '../assets/snapshot-import.mjs';
import {normalizeSnapshot,getFreshness,rankWaiverTargets} from '../assets/engine.mjs';
function fixture(){
 const raw=JSON.parse(readFileSync('fantasy/tests/fixtures/private-v3.sample.json','utf8'));
 raw.source='SYNTHETIC TEST FIXTURE - NOT LIVE';
 raw.teams.brock.leagueId='470.l.290846';
 raw.teams.brock.teamId='2';
 raw.syncedAtIso='2026-11-09T14:50:54.990Z';
 return raw;
}
const now=Date.parse('2026-11-09T14:52:00Z');
test('only Brock Hard team survives an imported three-team capture',()=>{
 const raw=fixture();raw.teams.quick={name:'OTHER PRIVATE TEAM'};
 raw.teams.highlight={name:'ANOTHER PRIVATE TEAM'};
 const out=preparePrivateImport(raw,{now});
 assert.deepEqual(Object.keys(out.teams),['brock']);
 assert.equal(out.teams.brock.teamId,'2');
 assert.equal(out.teams.brock.leagueId,'470.l.290846');
 assert.ok(!JSON.stringify(out).includes('OTHER PRIVATE TEAM'));
 assert.equal(out.teams.brock.projectionCoverage,'none');
 assert.ok(out.teams.brock.roster.every(p=>p.projection===null));
 assert.equal(rankWaiverTargets(normalizeSnapshot(out).teams.brock).available,false);
 assert.equal(getFreshness(out.syncedAtIso,now).actionable,true);
});
test('wrong or missing owner identity cannot become a Brock snapshot',()=>{
 for(const [field,value] of [['leagueId','470.l.999'],['teamId','5'],['leagueId','']]){
  const raw=fixture();raw.teams.brock[field]=value;
  assert.throws(()=>preparePrivateImport(raw,{now}),/not for Brock Hard/);
 }
});
test('newer current local capture is never replaced by older/equal imports',()=>{
 const raw=fixture();
 for(const time of [raw.syncedAtIso,'2026-11-09T14:50:53Z']){
  assert.throws(()=>preparePrivateImport(raw,{now,previousIso:time}),/not newer/);
 }
});
test('future, missing and malformed clocks fail safely',()=>{
 const raw=fixture();raw.syncedAtIso='2026-11-09T15:03:00Z';
 assert.throws(()=>preparePrivateImport(raw,{now}),/timestamp/);
 raw.syncedAtIso='definitely-not-a-date';
 assert.throws(()=>preparePrivateImport(raw,{now}),/timestamp/);
});
test('malformed and duplicate roster records fail closed',()=>{
 const raw=fixture();raw.teams.brock.roster.push({...raw.teams.brock.roster[0]});
 assert.throws(()=>preparePrivateImport(raw,{now}),/duplicated/);
 raw.teams.brock.roster=[];
 assert.throws(()=>preparePrivateImport(raw,{now}),/roster/);
});
test('unknown credential-like source fields are not saved',()=>{
 const raw=fixture();raw.teams.brock.oauth_refresh_token='SECRET';
 raw.teams.brock.roster[0].refreshToken='SECRET';
 raw.teams.brock.matchup={status:'upcoming',apiKey:'SECRET',home:{points:0,secret:'SECRET'},away:{points:0}};
 raw.clientSecret='SECRET';
 const sanitized=JSON.stringify(preparePrivateImport(raw,{now}));
 assert.ok(!sanitized.includes('SECRET'));
});
test('imported Flaim scored points are never mistaken for future player projections',()=>{
 const raw=fixture();
 raw.teams.brock.projectionCoverage='complete';
 const out=preparePrivateImport(raw,{now});
 assert.equal(out.teams.brock.projectionCoverage,'none');
 assert.ok(out.teams.brock.roster.every(p=>p.projection===null));
});
test('source remains read-only, browser tab duplication removed, and archive is not presented as current',()=>{
 const app=readFileSync('fantasy/assets/app-v2.mjs','utf8');
 assert.match(app,/function archivedView\(/);
 assert.match(app,/source==='published'&&!freshness\(\)\.actionable\?archivedView\(\)/);
 assert.match(app,/data-action="import"/);
 assert.doesNotMatch(app,/data-action="refresh" '+/);
 assert.doesNotMatch(app,/tabbar\(\)\+'<div id="tabPanel"/);
 assert.match(app,/preparePrivateImport\(raw/);
 assert.match(app,/localStorage\.setItem\(PRIVATE_KEY,JSON\.stringify\(brockOnly\)\)/);
});
