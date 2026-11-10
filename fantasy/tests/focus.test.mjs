import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildGeniusLab} from '../assets/genius-engine.mjs';
import {buildStrategicReport} from '../assets/strategy-engine.mjs';
import {analyzeEdge} from '../assets/edge-engine.mjs';
import {buildCoachPlan} from '../assets/coach-engine.mjs';
import {focusHome,focusLineup,focusPlayers,focusLeague,focusCoach} from '../assets/focused-experience.mjs';

const read=x=>JSON.parse(readFileSync(x,'utf8'));
const sources=()=>{
 const y=read('fantasy/data.json'),edge=read('fantasy/edge.json'),intel=read('fantasy/intelligence.json');
 const now=Math.max(Date.parse(y.syncedAtIso),Date.parse(edge.observedAtIso),Date.parse(intel.capturedAtIso))+120000;
 return {y,edge,intel,now,team:y.teams.brock,model:analyzeEdge(y,edge,{now}),
  genius:buildGeniusLab(y,edge,intel,{now,simulations:300}),
  strategic:buildStrategicReport(y,edge,intel,{now,simulations:300}),
  coach:buildCoachPlan(y,{now})};
};
const panels=html=>(html.match(/class="focus-panel /g)||[]).length;
test('Home shows one decision, not three duplicated analysis modules',()=>{
 const x=sources(),html=focusHome({team:x.team,genius:x.genius,model:x.model,currentWeek:x.y.week});
 assert.equal(panels(html),1);
 assert.match(html,/Make one move that matters/);
 assert.match(html,/focus-lead-action/);
 assert.doesNotMatch(html,/How strong are you really\?|Make the next move count|GENIUS LAB \/ OWNED-BY-EVIDENCE/);
 assert.ok(!html.includes('Projected optimal lineup'));
});
test('Lineup retains three risk choices, explicit RB-to-flex cascade and source-labeled forecasts',()=>{
 const x=sources();
 assert.equal(x.model.ready,true,x.model.reason);
 const html=focusLineup({team:x.team,model:x.model,mode:'balanced'});
 assert.equal(panels(html),1);
 assert.equal((html.match(/data-edge-mode=/g)||[]).length,3);
 assert.match(html,/data-edge-mode="balanced" aria-pressed="true"/);
 assert.match(html,/Rhamondre Stevenson: W\/R\/T → RB/);
 assert.match(html,/Zay Flowers at W\/R\/T/);
 assert.match(html,/ESTIMATE · NOT A GUARANTEE/);
 assert.match(html,/Bench and reserve/);
 assert.doesNotMatch(html,/genius-player-signal|strat-lineup-metrics|edge-lineup/);
 const safe=focusLineup({team:x.team,model:x.model,mode:'safe'});
 assert.match(safe,/data-edge-mode="safe" aria-pressed="true"/);
});
test('Players has one explicit TE gap, one grounded trade fit and a list that stays expanded after filters',()=>{
 const x=sources(),html=focusPlayers({team:x.team,genius:x.genius,model:x.model,filter:'WR',poolOpen:true});
 assert.equal(panels(html),1);
 assert.match(html,/Week 13/);
 assert.match(html,/Woody Marks ⇄ Travis Kelce/);
 assert.match(html,/data-focus-pool open/);
 assert.match(html,/data-filter="WR" aria-pressed="true"/);
 assert.ok((html.match(/class="focus-market-row"/g)||[]).length>0);
 assert.ok((html.match(/class="focus-market-row"/g)||[]).length<x.team.availablePlayers.length);
 assert.doesNotMatch(html,/genius-scout-list|strat-shortage|strat-pick-list/);
});
test('League ranks every club exactly once and keeps playoff simulation off this tab',()=>{
 const x=sources(),html=focusLeague({genius:x.genius,strategic:x.strategic});
 assert.equal(panels(html),1);
 assert.equal((html.match(/class="focus-power-row/g)||[]).length,8);
 assert.equal((html.match(/role="img"/g)||[]).length,8);
 assert.match(html,/20 held-out games/);
 assert.match(html,/Records do not equal roster strength/);
 assert.doesNotMatch(html,/strat-odds-table|genius-statgrid--playoff|4 clubs6 clubs/);
});
test('Coach is the single home for five gain assumptions, two hypothetical playoff fields, three final paragraphs',()=>{
 const x=sources();
 assert.equal(x.genius.ready,true,x.genius.reason);
 const html=focusCoach({genius:x.genius,model:x.model,plan:x.coach,field:4,realization:.5});
 assert.equal(panels(html),1);
 assert.equal((html.match(/data-genius-realization=/g)||[]).length,5);
 assert.equal((html.match(/data-genius-field=/g)||[]).length,2);
 assert.equal((html.match(/class="focus-brief"/g)||[]).length,1);
 assert.equal((html.match(/<p>/g)||[]).length,3); // introductory sentence + three sourced report paragraphs
 assert.match(html,/data-genius-field="4" aria-pressed="true"/);
 assert.match(html,/data-genius-realization="0.5" aria-pressed="true"/);
 assert.match(html,/Conditional, not actual Yahoo playoff odds/);
 assert.doesNotMatch(html,/coach-insight|edge-shell|genius-panel|strat-odds-table/);
});
test('Every source-rendered name and scenario value is escaped',()=>{
 const x=sources(),g=structuredClone(x.genius);
 g.rankings[0].name='<img src=x onerror=alert(1)>';
 g.tradeCandidates[0].receive='<script>evil()</script>';
 const league=focusLeague({genius:g,strategic:x.strategic});
 const players=focusPlayers({team:x.team,genius:g,model:x.model});
 assert.match(league,/&lt;img/);
 assert.doesNotMatch(league,/<img src=x/);
 assert.match(players,/&lt;script/);
 assert.doesNotMatch(players,/<script>evil/);
});
test('UI layer has no new provider calls, secrets, roster transactions or another personally owned team',()=>{
 const ui=readFileSync('fantasy/assets/focused-experience.mjs','utf8');
 assert.doesNotMatch(ui,/\bfetch\(|XMLHttpRequest|WebSocket|submitTrade|claimPlayer|accessToken|refreshToken|client_secret|ownerId/);
 assert.doesNotMatch(ui,/Quick Snap Jamison|Highlight Reel Jamison/);
 const app=readFileSync('fantasy/assets/app-v2.mjs','utf8');
 assert.match(app,/focusHome\(/);
 assert.match(app,/focusLineup\(/);
 assert.match(app,/focusPlayers\(/);
 assert.match(app,/focusLeague\(/);
 assert.match(app,/focusCoach\(/);
 assert.doesNotMatch(app,/return geniusHome\(geniusReport\(\)\)\+homeStrategy/);
 assert.doesNotMatch(app,/geniusPlayers\(geniusReport\(\)\)\+playersStrategy/);
});
