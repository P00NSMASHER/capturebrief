import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildCoachPlan,coachBulletPoints,buildArchivedCoachReview} from '../assets/coach-engine.mjs';
import {uiIcon} from '../assets/league-branding.mjs';

const checkAt=Date.parse('2026-11-09T19:30:00Z');
function fixture(){
 const player=(id,name,position,slot,actualPoints,injury=null)=>({
   id,name,position,slot,actualPoints,injury,projection:null,locked:false,
   eligiblePositions:position==='RB'?['RB','W/R/T']:position==='WR'?['WR','W/R/T']:[position]
 });
 return {
  schemaVersion:3,season:2026,week:9,provider:'Yahoo',syncedAtIso:'2026-11-09T17:30:21.368Z',
  teams:{brock:{
   leagueId:'470.l.290846',teamId:'2',name:'Brock Hard & Tee Baggin',record:'6-2',rank:'1 of 8',
   projectionCoverage:'none',lineupSlots:{QB:1,'W/R/T':1},
   roster:[
    player('100','Test QB','QB','QB',10),
    player('101','Flagged Starter','RB','W/R/T',10,'Q'),
    player('102','Bench RB','RB','BN',14),
    player('103','Bench WR','WR','BN',18),
    player('104','Reserve WR','WR','IR',0,'O')
   ],
   availablePlayers:[
    {id:'400',name:'Market QB',position:'QB',acquisitionState:'waivers',percentOwned:77},
    {id:'401',name:'Available QB',position:'QB',acquisitionState:'free_agent',percentOwned:53},
    {id:'402',name:'Market WR',position:'WR',acquisitionState:'waivers',percentOwned:85}
   ],
   standings:{rank:1,leagueSize:8,wins:6,losses:2,pointsFor:1200.34,pointsAgainst:1125.90,asOfIso:'2026-11-09T17:30:21Z'},
   upcomingMatchups:[
    {week:10,opponent:'Opponent A',myProjected:135,opponentProjected:124},
    {week:11,opponent:'Opponent B',myProjected:125,opponentProjected:123},
    {week:12,opponent:'Opponent C',myProjected:137,opponentProjected:128}
   ]
  }}
 };
}
test('Coach prioritizes an actually flagged starter and an actual one-QB depth gap',()=>{
 const plan=buildCoachPlan(fixture(),{now:checkAt});
 assert.equal(plan.ready,true);
 assert.equal(plan.status,'snapshot');
 assert.equal(plan.priorities.length,3);
 assert.match(plan.priorities[0].title,/Flagged Starter/);
 assert.match(plan.priorities[0].detail,/Q/);
 assert.equal(plan.priorities[0].actionTab,'lineup');
 assert.equal(plan.priorities[1].filter,'QB');
 assert.equal(plan.priorities[1].actionTab,'waivers');
 assert.match(plan.priorities[1].detail,/Market QB/);
 assert.match(plan.priorities[1].detail,/Available QB/);
 assert.equal(plan.facts.qbDepth,1);
 assert.equal(plan.facts.flaggedStarters,1);
});
test('Coach computes only verified Yahoo standings and labeled team-level pregame gaps',()=>{
 const p=buildCoachPlan(fixture(),{now:checkAt});
 assert.equal(p.facts.rank,1);
 assert.equal(p.facts.differential,74.44);
 assert.match(p.sections.league[0].detail,/\+74\.44/);
 assert.match(p.sections.playoffs[0].title,/Week 11/);
 assert.match(p.sections.playoffs[0].detail,/\+2\.0 Brock points/);
 assert.match(p.sections.playoffs[0].evidence,/not a win prediction/);
 assert.doesNotMatch(JSON.stringify(p),/guaranteed champion|100% playoff|clinched/);
});
test('Scored-week hindsight never turns into a next-week start/sit recommendation',()=>{
 const p=buildCoachPlan(fixture(),{now:checkAt});
 const hindsight=p.sections.lineup.find(x=>x.id==='lineup-hindsight');
 assert.ok(hindsight);
 assert.match(hindsight.detail,/points already scored/);
 assert.match(hindsight.detail,/not a next-week start\/sit recommendation/);
 assert.equal(p.facts.scoredGap,8);
 assert.equal(p.sections.trades.some(x=>x.id==='trade-gate'),true);
 assert.match(p.sections.trades.find(x=>x.id==='trade-gate').detail,/Do not send a named offer/);
 assert.equal(p.projectionCoverage,'none');
});
test('No source makes a named trade or speculative waiver claim, even if Yahoo market is populated',()=>{
 const f=fixture();f.teams.brock.availablePlayers=[];
 f.teams.brock.upcomingMatchups=[];f.teams.brock.standings=null;
 const p=buildCoachPlan(f,{now:checkAt});
 assert.equal(p.ready,true);
 assert.match(p.sections.waivers[0].title,/Check for quarterback cover/);
 assert.match(p.sections.playoffs[0].title,/Check the remaining schedule/);
 assert.match(p.sections.league[0].title,/Standings details are incomplete/);
 assert.ok(!JSON.stringify(p).includes('Market QB'));
 assert.ok(!JSON.stringify(p).includes('opponent owner'));
});
test('Fail-closed when season, league, team, roster, or source freshness is invalid',()=>{
 const f=fixture();
 f.season=2027;assert.equal(buildCoachPlan(f,{now:checkAt}).ready,false);
 f.season=2026;f.teams.brock.teamId='3';assert.equal(buildCoachPlan(f,{now:checkAt}).ready,false);
 f.teams.brock.teamId='2';f.teams.brock.leagueId='invalid';assert.equal(buildCoachPlan(f,{now:checkAt}).ready,false);
 f.teams.brock.leagueId='470.l.290846';f.teams.brock.roster[1].id=f.teams.brock.roster[0].id;
 assert.equal(buildCoachPlan(f,{now:checkAt}).ready,false);
 const stale=fixture();
 const p=buildCoachPlan(stale,{now:Date.parse('2026-11-10T02:30:21Z')});
 assert.equal(p.ready,false);assert.equal(p.status,'archived');
 assert.equal(p.priorities.length,0);
 const mixed=fixture();mixed.teams.other={name:'OTHER OWNED TEAM'};
 assert.equal(buildCoachPlan(mixed,{now:checkAt}).ready,false);
});
test('Navigation remains Brock-only, four decision jobs, current published data and no extra API',()=>{
 const app=readFileSync('fantasy/assets/app-v2.mjs','utf8');
 assert.doesNotMatch(app,/\['coach','Coach','coach'\]/);
 assert.match(app,/function coachView\(team\)/);
 assert.match(app,/playerPoolOpen/);
 assert.match(app,/focusPlayers\(/);
 assert.match(app,/\['overview','lineup','waivers','lab'\]/);
 assert.match(app,/source==='published'&&!freshness\(\)\.actionable\?archivedView\(\)/);
 assert.match(app,/buildCoachPlan\(current,/);
 assert.doesNotMatch(app,/new WebSocket|client_secret|rosterTransaction|submitTrade/);
 const icon=uiIcon('coach');
 assert.match(icon,/M12 3 14\.6/);
 assert.match(icon,/<svg/);
});
test('No private source envelopes, credentials, or other personal team snapshots in coach data',()=>{
 const f=fixture();
 const output=JSON.stringify(buildCoachPlan(f,{now:checkAt}));
 assert.ok(!output.includes('oauth'));
 assert.ok(!output.includes('refreshToken'));
 assert.ok(!output.includes('ownerId'));
 assert.ok(!output.includes('Quick Snap'));
 assert.ok(!output.includes('Highlight Reel'));
 assert.deepEqual(Object.keys(f.teams),['brock']);
});


test('Coach insight cards are scannable bullets with unchanged evidence and no made-up projections',()=>{
 const p=buildCoachPlan(fixture(),{now:checkAt});
 assert.equal(p.ready,true);
 for(const cards of Object.values(p.sections)){
  assert.ok(cards.length>0);
  for(const c of cards){
   assert.ok(Array.isArray(c.bullets)&&c.bullets.length>=1&&c.bullets.length<=5);
   assert.equal(c.bullets.join(' '),c.detail);
   assert.ok(c.evidence.length>0);
  }
 }
 assert.deepEqual(coachBulletPoints('Scores were 148.58 points. Next week needs verification.'),
  ['Scores were 148.58 points.','Next week needs verification.']);
 assert.doesNotMatch(JSON.stringify(p.sections),/guaranteed playoff spot|live injury/);
});

test('Three-paragraph elite-style coach recap reflects only verified team, roster and matchup facts',()=>{
 const p=buildCoachPlan(fixture(),{now:checkAt});
 assert.ok(p.ready);
 assert.equal(p.summary.length,3);
 assert.ok(p.summary.every(x=>typeof x==='string'&&x.length>200));
 assert.match(p.summary[0],/6–2/);
 assert.match(p.summary[0],/1200\.34/);
 assert.match(p.summary[0],/1125\.90/);
 assert.match(p.summary[0],/\+74\.44/);
 assert.match(p.summary[1],/Flagged Starter/);
 assert.match(p.summary[1],/Market QB/);
 assert.match(p.summary[2],/Week 11 against Opponent B/);
 assert.match(p.summary[2],/\+2\.0 points/);
 assert.match(p.summary[2],/not winning probabilities/);
 assert.ok(!p.summary.join(' ').includes('Current playoff probability'));
});
test('Recap fails honestly when data is absent and does not repeat invented standings or names',()=>{
 const raw=fixture();
 raw.teams.brock.standings=null;
 raw.teams.brock.availablePlayers=[];
 raw.teams.brock.upcomingMatchups=[];
 const p=buildCoachPlan(raw,{now:checkAt});
 assert.equal(p.summary.length,3);
 assert.match(p.summary[0],/not complete enough/);
 assert.match(p.summary[1],/No verified quarterback pickup/);
 assert.match(p.summary[2],/incomplete/);
 assert.doesNotMatch(p.summary.join(' '),/Market QB|Opponent B|1200\.34|guaranteed/);
 const stale=buildCoachPlan(fixture(),{now:Date.parse('2026-11-10T02:30:21Z')});
 assert.equal(stale.ready,false);
 assert.equal(stale.summary,undefined);
});

test('Historical recap survives a stale Yahoo snapshot without unlocking move recommendations',()=>{
 const raw=fixture(),now=Date.parse('2026-11-10T05:30:00Z');
 const live=buildCoachPlan(raw,{now});
 assert.equal(live.ready,false);
 assert.equal(live.status,'archived');
 const review=buildArchivedCoachReview(raw,{now});
 assert.ok(review);
 assert.equal(review.historical,true);
 assert.equal(review.captureAt,raw.syncedAtIso);
 assert.equal(review.summary.length,3);
 assert.match(review.summary[0],/At the saved Week 9 Yahoo capture, Brock Hard was 6–2/);
 assert.ok(review.summary.every(p=>p.length>200));
 assert.equal(review.priorities,undefined);
 assert.equal(review.sections,undefined);
 assert.doesNotMatch(JSON.stringify(review),/guaranteed champion|100% playoff|clinched/);
});
test('Archived review rejects wrong teams, manipulated player identities and future timestamps',()=>{
 const now=Date.parse('2026-11-09T19:30:00Z');
 const mixed=fixture();mixed.teams.other={name:'OTHER OWNED TEAM'};
 assert.equal(buildArchivedCoachReview(mixed,{now}),null);
 const bad=fixture();bad.teams.brock.teamId='7';
 assert.equal(buildArchivedCoachReview(bad,{now}),null);
 const badIds=fixture();badIds.teams.brock.roster[0].id=badIds.teams.brock.roster[1].id;
 assert.equal(buildArchivedCoachReview(badIds,{now}),null);
 const future=fixture();future.syncedAtIso='2026-11-10T20:00:00Z';
 assert.equal(buildArchivedCoachReview(future,{now}),null);
});
