import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {analyzeEdge} from '../assets/edge-engine.mjs';
import {buildGeniusLab} from '../assets/genius-engine.mjs';
import {buildStrategicReport} from '../assets/strategy-engine.mjs';

const read=path=>JSON.parse(readFileSync(path,'utf8'));
const published=()=>({
 yahoo:read('fantasy/data.json'),
 edge:read('fantasy/edge.json'),
 intelligence:read('fantasy/intelligence.json')
});
const observedNow=({yahoo,edge,intelligence})=>Math.max(
 Date.parse(yahoo.syncedAtIso),
 Date.parse(edge.observedAtIso),
 Date.parse(intelligence.capturedAtIso)
)+120000;

test('today publication contains the expected three Brock-only artifacts',()=>{
 const {yahoo,edge,intelligence}=published();
 assert.equal(yahoo.schemaVersion,3);
 assert.equal(yahoo.season,2026);
 assert.equal(yahoo.week,10);
 assert.equal(yahoo.teams.brock.name,'Brock Hard & Tee Baggin');
 assert.equal(edge.schemaVersion,1);
 assert.equal(edge.season,2026);
 assert.equal(edge.week,11);
 assert.equal(intelligence.schemaVersion,1);
 assert.equal(intelligence.season,2026);
 assert.equal(intelligence.modelWeek,10);
 assert.equal(intelligence.baselineWeek,9);
 assert.deepEqual(Object.keys(yahoo.teams),['brock']);
});

test('current Week 11 edge remains useful while exact lineups fail closed on partial projection coverage',()=>{
 const artifacts=published();
 const model=analyzeEdge(artifacts.yahoo,artifacts.edge,{now:observedNow(artifacts)});
 assert.equal(model.ready,true,model.reason);
 assert.equal(model.modelWeek,11);
 const onBye=model.byes.find(p=>p.week===model.modelWeek)?.players.find(p=>p.starting);
 const byePriority=model.priorities.find(p=>p.id==='bye-replacement');
 assert.equal(Boolean(byePriority),Boolean(onBye),'Week 11 bye alert must follow current roster');
 if(byePriority)assert.ok(byePriority.title.includes(onBye.name),'Bye alert must name a verified starter');
 const teShortage=model.byes.find(p=>p.shortages.some(s=>s.position==='TE'&&s.available===0));
 const tePriority=model.priorities.find(p=>p.id==='te-coverage');
 assert.equal(Boolean(tePriority),Boolean(teShortage),'TE alert must follow validated coverage');
 assert.ok(model.priorities.length>0,'A verified source-backed scouting priority must survive refresh');
 for(const mode of ['safe','balanced','upside']){
  assert.equal(model.lineups[mode].available,false);
  assert.equal(model.lineups[mode].reason,'Missing current projections for eligible players');
 }
});

test('older league intelligence is intentionally rejected instead of being relabeled current',()=>{
 const artifacts=published(),now=observedNow(artifacts);
 const genius=buildGeniusLab(artifacts.yahoo,artifacts.edge,artifacts.intelligence,{now,simulations:50});
 const strategy=buildStrategicReport(artifacts.yahoo,artifacts.edge,artifacts.intelligence,{now,simulations:50});
 assert.equal(genius.ready,false);
 assert.equal(genius.reason,'League intelligence belongs to a different season or week');
 assert.equal(strategy.ready,false);
 assert.equal(strategy.reason,'League intelligence belongs to a different week');
});
