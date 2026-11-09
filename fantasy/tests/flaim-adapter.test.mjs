import test from 'node:test';
import assert from 'node:assert/strict';
import {TEAM_IDS,buildPrivateV3,refreshWithReader} from '../adapter/flaim-private-v3.mjs';
import {normalizeSnapshot,getFreshness,rankWaiverTargets,optimizeLineup} from '../assets/engine.mjs';
const AT='2026-11-08T23:50:00.000Z';
const MAP={brock:{leagueKey:'470.l.111',teamId:'2'}};
const wrap=data=>({success:true,data});
function one(){
 const lk=MAP.brock.leagueKey,tk=lk+'.t.2';
 return {
  league:wrap({leagueKey:lk,currentWeek:9,rosterPositions:[{position:'QB',count:1},{position:'RB',count:1},{position:'W/R/T',count:1},{position:'BN',count:6},{position:'IR',count:2}]}),
  roster:wrap({teamKey:tk,teamName:'Fictional Brock Hard',snapshot:{type:'current'},players:[
   {playerId:'11',name:'Fictional QB',position:'QB',selectedPosition:'QB',eligiblePositions:['QB'],points:0,isEditable:false,isUndroppable:false},
   {playerId:'12',name:'Fictional RB',position:'RB',selectedPosition:'RB',eligiblePositions:['RB','W/R/T'],points:9.5,isEditable:true,isUndroppable:true},
   {playerId:'13',name:'Fictional Bench',position:'WR',selectedPosition:'BN',eligiblePositions:['WR','W/R/T'],points:5.4}
  ]}),
  matchups:wrap({leagueKey:lk,currentWeek:9,matchupWeek:9,matchups:[{status:'in_progress',home:{teamKey:tk,teamId:'2',points:72.3,winProbability:0,projectedPoints:120.5},away:{teamKey:lk+'.t.7',teamId:'7',points:50.7,winProbability:1}}]}),
  standings:wrap({leagueKey:lk,standings:[{teamKey:tk,rank:'2',wins:'5',losses:'3',ties:0,waiverPriority:2}]}),
  freeAgents:wrap({leagueKey:lk,seasonYear:2026,freeAgents:[{playerId:'99',name:'Fictional Available',position:'WR',acquisitionState:'waivers',waiverDate:'2026-11-11',percentOwned:62,points:35}]})
 };
}
function bundle(){return{seasonYear:2026,capturedAtIso:AT,teamMap:structuredClone(MAP),teams:{brock:one()}}}
function run(d,previous=null,nowIso=AT){return buildPrivateV3(d,{previous,nowIso})}
test('Brock only: valid owner-mapped provider data converts to private schema v3',()=>{
 assert.deepEqual(TEAM_IDS,['brock']);
 const x=run(bundle());assert.equal(x.ok,true);assert.equal(x.liveSync,false);
 assert.deepEqual(Object.keys(x.snapshot.teams),['brock']);
 const t=normalizeSnapshot(x.snapshot).teams.brock;
 assert.equal(t.roster[0].actualPoints,0);assert.equal(t.roster[0].projection,null);
 assert.equal(t.roster[1].cantCut,true);
 assert.equal(t.lineupSlots['W/R/T'],1);assert.equal(t.matchup.home.winProbability,0);
 assert.equal(t.availablePlayers[0].waiverDate,'2026-11-11');
 assert.equal(t.projectionCoverage,'none');
 assert.equal(rankWaiverTargets(t).available,false);
 assert.equal(optimizeLineup(t.roster,t.lineupSlots).available,false);
 assert.equal(getFreshness(x.snapshot.syncedAtIso,Date.parse(AT)).actionable,true);
});
test('401, expired Yahoo state, 403, incomplete roster, wrong team/league/week retain last good',()=>{
 const good=run(bundle()).snapshot;
 for(const mode of ['401','expired','403','roster','team','league','week','standing','historical']){
  const b=bundle();b.capturedAtIso='2026-11-08T23:51:00Z';
  if(mode==='401')b.teams.brock.roster={success:false,status:401,error:{code:'invalid_token',message:'secret token'}};
  if(mode==='expired')b.teams.brock.roster={success:false,error:{code:'TOKEN_EXPIRED'}};
  if(mode==='403')b.teams.brock.roster={success:false,status:403,error:{code:'access_denied'}};
  if(mode==='roster')b.teams.brock.roster.data.players=[];
  if(mode==='team')b.teams.brock.roster.data.teamKey='470.l.111.t.9';
  if(mode==='league')b.teams.brock.freeAgents.data.leagueKey='470.l.999';
  if(mode==='week')b.teams.brock.matchups.data.matchupWeek=8;
  if(mode==='standing')b.teams.brock.standings.data.standings=[];
  if(mode==='historical')b.teams.brock.roster.data.snapshot.type='week';
  const x=run(b,good,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false,mode);assert.equal(x.snapshot,good,mode);
  assert.ok(!JSON.stringify(x).includes('secret token'));
 }
});
test('only advanced capture timestamps accepted',()=>{
 const good=run(bundle()).snapshot;
 for(const date of ['bad','2026-11-08T22:00:00Z','2026-11-09T01:00:00Z',AT]){
  const b=bundle();b.capturedAtIso=date;
  const x=run(b,good,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false,date);assert.equal(x.snapshot,good,date);
 }
});
test('other teams ignored and stripped even from last-good fallback',()=>{
 const b=bundle();b.teams.quick={private:'do not expose'};b.teamMap.quick={leagueKey:'470.l.333',teamId:'1'};
 const good=run(b).snapshot;assert.deepEqual(Object.keys(good.teams),['brock']);
 const prior={...good,teams:{...good.teams,quick:{name:'PRIVATE QUICK'}}};
 const failed=bundle();failed.teams.brock.roster={success:false,status:401};
 const x=run(failed,prior,'2026-11-08T23:51:00Z');
 assert.equal(x.ok,false);assert.deepEqual(Object.keys(x.snapshot.teams),['brock']);
});
test('synthetic fixtures are explicit, archived and not live sync',()=>{
 const b=bundle();b.fixture=true;assert.equal(run(b).ok,false);
 b.allowFixtures=true;const x=run(b);
 assert.equal(x.ok,true);assert.equal(x.liveSync,false);assert.equal(x.fixture,true);
 assert.match(x.snapshot.source,/SYNTHETIC TEST FIXTURE/);
 assert.equal(getFreshness(x.snapshot.syncedAtIso,Date.parse(AT)).actionable,false);
});
test('injected reader calls Brock only; failure never replaces previous',async()=>{
 const prior=run(bundle()).snapshot,seen=[];
 const x=await refreshWithReader({teamMap:{...MAP,quick:{leagueKey:'470.l.333',teamId:'1'}},
  previous:prior,clock:()=> '2026-11-08T23:51:00Z',
  readLeague:async(id,target)=>{seen.push([id,target.teamId]);throw Object.assign(new Error('secret'),{status:401})}});
 assert.equal(x.ok,false);assert.equal(x.snapshot,prior);assert.deepEqual(seen,[['brock','2']]);
 assert.ok(!JSON.stringify(x).includes('secret'));
});
test('fresh authorized capture from injected reader contains only Brock',async()=>{
 const seen=[];
 const x=await refreshWithReader({teamMap:MAP,clock:()=>AT,readLeague:async id=>{seen.push(id);return one()}});
 assert.equal(x.ok,true);assert.deepEqual(seen,['brock']);assert.deepEqual(Object.keys(x.snapshot.teams),['brock']);
});
test('no reader or missing mapping fails closed',async()=>{
 const prior=run(bundle()).snapshot;
 const x=await refreshWithReader({teamMap:MAP,previous:prior,clock:()=>AT});
 assert.equal(x.ok,false);assert.equal(x.snapshot,prior);
 const b=bundle();delete b.teamMap.brock;assert.equal(run(b,prior).ok,false);
});
