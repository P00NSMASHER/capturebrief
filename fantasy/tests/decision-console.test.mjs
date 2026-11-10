import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {focusHome,focusLeague} from '../assets/focused-experience.mjs';

const team={
 name:'Brock Hard & Tee Baggin',record:'7-2',
 standings:{rank:1,leagueSize:8,pointsFor:1366.72,pointsAgainst:1252.96},
 upcomingMatchups:[
  {week:11,opponent:'BEEFS GAY',myProjected:135.2,opponentProjected:110.15},
  {week:12,opponent:'Jersey junkyard',myProjected:149.7,opponentProjected:141.09}
 ]
};

test('Today leads with the exact stale-data blocker and useful verified context',()=>{
 const html=focusHome({team,genius:null,model:{quality:{yahooFresh:false},modelWeek:11},currentWeek:10,freshness:{ageHours:42}});
 assert.match(html,/Refresh the Yahoo roster snapshot/);
 assert.match(html,/42 hours old/);
 assert.match(html,/data-action="refresh"/);
 assert.match(html,/7-2/);
 assert.match(html,/1 \/ 8/);
 assert.match(html,/\+113\.8/);
 assert.match(html,/BEEFS GAY/);
 assert.doesNotMatch(html,/current move recommendation/);
});

test('League falls back to verified standings and schedule when advanced evidence is mismatched',()=>{
 const html=focusLeague({genius:{ready:false},strategic:null,team});
 assert.match(html,/VERIFIED LEAGUE SNAPSHOT/);
 assert.match(html,/1366\.7/);
 assert.match(html,/BEEFS GAY/);
 assert.match(html,/historical all-play comparison is withheld/);
 assert.doesNotMatch(html,/No current league evidence/);
});

test('App exposes four distinct jobs and removes the stale home scoreboard',()=>{
 const app=readFileSync('fantasy/assets/app-v2.mjs','utf8');
 assert.match(app,/\['overview','Today','home'\]/);
 assert.match(app,/\['waivers','Market','waivers'\]/);
 assert.doesNotMatch(app,/\['coach','Coach','coach'\]/);
 const summary=app.slice(app.indexOf('function summaryView'),app.indexOf('function lineupView'));
 assert.doesNotMatch(summary,/matchupCard/);
});
