import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {analyzeEdge} from '../assets/edge-engine.mjs';
import {renderEdgeLab} from '../assets/edge-view.mjs';

const y=()=>JSON.parse(readFileSync('fantasy/tests/fixtures/historical-week10/data.json','utf8'));
const e=()=>JSON.parse(readFileSync('fantasy/tests/fixtures/historical-week10/edge.json','utf8'));
const ready=()=>{const inputs=e(),snapshot=y();return analyzeEdge(snapshot,inputs,{now:Math.max(Date.parse(inputs.observedAtIso),Date.parse(snapshot.syncedAtIso))+3*60000})};
test('Model-driven fifth-tab renders distinct intelligence—not a Yahoo scoreboard recap',()=>{
 const model=ready();assert.equal(model.ready,true);
 const html=renderEdgeLab(model);
 for(const text of ['Win the next decision.','HIGHEST-PRIORITY FINDING','What I would do first',
  'Week 10 lineup lab','Waiver opportunities','Opponent scouting','Beat the bye weeks','Coach’s final read',
  'Cautious','Balanced','Upside','experimental','Jersey junkyard','Brock Bowers','Mark Andrews']){
  assert.ok(html.toLowerCase().includes(text.toLowerCase()),'Missing '+text);
 }
 assert.ok((html.match(/class="edge-rec /g)||[]).length>=2);
 assert.match(html,/data-edge-mode="upside"/);
 assert.match(html,/data-edge-jump="players"/);
 assert.match(html,/class="edge-bye-warning"/);
 assert.match(html,/no available rostered TE/);
 assert.match(html,/This dashboard is public/);
 assert.equal((html.match(/class="edge-brief-paragraphs"/g)||[]).length,1);
});
test('Forecast model renders no league-unavailable player with a waiver projected uplift',()=>{
 const model=ready(),html=renderEdgeLab(model);
 assert.equal(model.waivers.covered,16);
 for(const row of model.waivers.positive){
   assert.ok(y().teams.brock.availablePlayers.some(x=>x.id===row.add.id));
 }
 assert.doesNotMatch(html,/\bUnavailable Player\b/);
 assert.match(html,/not a calibrated probability interval|not validated percentiles/);
});
test('Escaping is complete even if a rival team name or projected player name contains HTML',()=>{
 const m=ready(),r=structuredClone(m);
 r.opponents[0].teamName='<img src=x onerror=alert(1)>';
 r.waivers.watches[0].name='<script>alert(1)</script>';
 r.priorities[0].detail='On <svg/onload=evil> bye';
 const html=renderEdgeLab(r);
 assert.doesNotMatch(html,/<img src=x|<script>alert|<svg\/onload/);
 assert.match(html,/&lt;img/);
 assert.match(html,/&lt;script/);
 assert.match(html,/&lt;svg\/onload/);
 assert.doesNotMatch(html,/accessToken|refreshToken|email@|cookie=/);
});
test('Unavailable model output never implies a winning prediction or tactical recommendation',()=>{
 const html=renderEdgeLab({ready:false,reason:'Provider data is unavailable.'});
 assert.match(html,/Predictive data unavailable/);
 assert.match(html,/No speculative lineup swaps or fake win odds/);
 assert.doesNotMatch(html,/class="edge-hero"|class="edge-rec"|data-edge-mode/);
});
