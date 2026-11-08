import test from 'node:test';
import assert from 'node:assert/strict';
import {buildPrivateV3,refreshWithReader,TEAM_IDS} from '../adapter/flaim-private-v3.mjs';
import {normalizeSnapshot,getFreshness,rankWaiverTargets,optimizeLineup} from '../assets/engine.mjs';

const AT='2026-11-08T23:50:00.000Z';
const MAP={brock:{leagueKey:'470.l.111',teamId:'2'},
  quick:{leagueKey:'470.l.222',teamId:'1'},
  highlight:{leagueKey:'470.l.333',teamId:'4'}};
const wrap=data=>({success:true,data});
function one(id) {
 const target=MAP[id],lk=target.leagueKey,tk=lk+'.t.'+target.teamId;
 return {
  league:wrap({leagueKey:lk,currentWeek:9,
    rosterPositions:[{position:'QB',count:1},{position:'RB',count:1},
      {position:'W/R/T',count:1},{position:'BN',count:6},{position:'IR',count:2}]}),
  roster:wrap({teamKey:tk,teamName:'Fictional '+id,snapshot:{type:'current'},
    players:[{playerId:'11',name:'Fictional QB',position:'QB',selectedPosition:'QB',
      eligiblePositions:['QB'],points:0,isEditable:false,isUndroppable:false},
      {playerId:'12',name:'Fictional RB',position:'RB',selectedPosition:'RB',
        eligiblePositions:['RB','W/R/T'],points:9.5,isEditable:true,isUndroppable:true},
      {playerId:'13',name:'Fictional Bench',position:'WR',selectedPosition:'BN',
        eligiblePositions:['WR','W/R/T'],points:5.4}]}),
  matchups:wrap({leagueKey:lk,currentWeek:9,matchupWeek:9,
    matchups:[{status:'in_progress',home:{teamKey:tk,teamId:target.teamId,
       points:72.3,winProbability:0,projectedPoints:120.5},
      away:{teamKey:lk+'.t.7',teamId:'7',points:50.7,winProbability:1}}]}),
  standings:wrap({leagueKey:lk,standings:[{teamKey:tk,rank:'2',
    wins:'5',losses:'3',ties:0,waiverPriority:2}]}),
  freeAgents:wrap({leagueKey:lk,seasonYear:2026,freeAgents:[{
    playerId:'99',name:'Fictional Available',position:'WR',acquisitionState:'waivers',
    waiverDate:'2026-11-11',percentOwned:62,points:35}]})
 };
}
function bundle() {return{seasonYear:2026,capturedAtIso:AT,teamMap:structuredClone(MAP),
 teams:Object.fromEntries(TEAM_IDS.map(id=>[id,one(id)]))};}
function run(data,previous=null,nowIso=AT) {
 return buildPrivateV3(data,{previous,nowIso});
}
test('current, owner-mapped Yahoo packets convert to the existing private v3 contract',()=>{
 const x=run(bundle());
 assert.equal(x.ok,true);
 assert.equal(x.liveSync,false);
 assert.deepEqual(Object.keys(x.snapshot.teams),TEAM_IDS);
 const parsed=normalizeSnapshot(x.snapshot);
 assert.equal(parsed.teams.brock.teamId,'2');
 assert.equal(parsed.teams.quick.teamId,'1');
 assert.equal(parsed.teams.highlight.teamId,'4');
 assert.equal(parsed.teams.brock.roster[0].actualPoints,0);
 assert.equal(parsed.teams.brock.roster[0].projection,null);
 assert.equal(parsed.teams.brock.roster[1].cantCut,true);
 assert.equal(parsed.teams.brock.lineupSlots['W/R/T'],1);
 assert.equal(parsed.teams.brock.matchup.home.winProbability,0);
 assert.equal(parsed.teams.brock.availablePlayers[0].waiverDate,'2026-11-11');
 assert.equal(parsed.teams.brock.availablePlayers[0].projection,null);
 assert.equal(getFreshness(x.snapshot.syncedAtIso,Date.parse(AT)).actionable,true);
 assert.equal(x.snapshot.captureType,'manual-provider-read');
 assert.ok(!JSON.stringify(x.snapshot).includes('client_secret'));
});
test('provider points never become forecasts or safe add/drop advice',()=>{
 const snap=normalizeSnapshot(run(bundle()).snapshot),t=snap.teams.brock;
 assert.equal(t.projectionCoverage,'none');
 assert.ok(t.roster.every(p=>p.projection===null));
 assert.equal(rankWaiverTargets(t).available,false);
 assert.equal(optimizeLineup(t.roster,t.lineupSlots).available,false);
});
test('auth 401, expired state and access denied fail closed without leaking errors',()=>{
 const good=run(bundle()).snapshot;
 for(const err of [{success:false,status:401,error:{code:'invalid_token',detail:'secret xyz'}},
   {success:false,error:{code:'TOKEN_EXPIRED'}},
   {success:false,status:403,error:{code:'access_denied'}}]) {
  const b=bundle();b.teams.quick.roster=err;
  const x=run(b,good,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false);
  assert.equal(x.snapshot,good);
  assert.ok(!JSON.stringify(x).includes('secret xyz'));
 }
});
test('wrong team and wrong league identity cannot silently cross-wire teams',()=>{
 const previous=run(bundle()).snapshot;
 for(const mode of ['team','league','duplicate']) {
  const b=bundle();b.capturedAtIso='2026-11-08T23:51:00Z';
  if(mode==='team')b.teams.quick.roster.data.teamKey='470.l.222.t.9';
  if(mode==='league')b.teams.quick.freeAgents.data.leagueKey='470.l.111';
  if(mode==='duplicate')b.teamMap.quick=b.teamMap.brock;
  const x=run(b,previous,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false);
  assert.equal(x.snapshot,previous);
 }
});
test('incomplete roster, missing standings, and mismatched weeks retain previous',()=>{
 const previous=run(bundle()).snapshot;
 for(const mode of ['roster','standings','week','historical']) {
  const b=bundle();b.capturedAtIso='2026-11-08T23:51:00Z';
  if(mode==='roster')b.teams.highlight.roster.data.players=[];
  if(mode==='standings')b.teams.highlight.standings.data.standings=[];
  if(mode==='week')b.teams.highlight.matchups.data.matchupWeek=8;
  if(mode==='historical')b.teams.highlight.roster.data.snapshot.type='week';
  const x=run(b,previous,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false,mode);
  assert.equal(x.snapshot,previous,mode);
 }
});
test('clock validation prevents stale captures, future dates and replacing newer good data',()=>{
 const good=run(bundle()).snapshot;
 for(const bad of ['nonsense','2026-11-08T22:00:00Z','2026-11-09T01:00:00Z',AT]) {
  const b=bundle();b.capturedAtIso=bad;
  const x=run(b,good,'2026-11-08T23:51:00Z');
  assert.equal(x.ok,false,bad);
  assert.equal(x.snapshot,good,bad);
 }
});
test('unrecognized fourth league is never imported',()=>{
 const b=bundle();b.teams.taco=one('brock');b.teamMap.taco={leagueKey:'470.l.999',teamId:'6'};
 assert.deepEqual(Object.keys(run(b).snapshot.teams),TEAM_IDS);
});
test('fixture is explicit, archived and is never represented as Yahoo live synchronization',()=>{
 const b=bundle();b.fixture=true;
 assert.equal(run(b).ok,false);
 b.allowFixtures=true;
 const x=run(b);
 assert.equal(x.ok,true);
 assert.equal(x.fixture,true);
 assert.equal(x.liveSync,false);
 assert.equal(x.snapshot.captureType,'synthetic-fixture');
 assert.match(x.snapshot.source,/SYNTHETIC TEST FIXTURE/);
 assert.equal(getFreshness(x.snapshot.syncedAtIso,Date.parse(AT)).actionable,false);
});
test('injected reader does only authorized read calls and never commits partial refresh',async()=>{
 const previous=run(bundle()).snapshot,seen=[];
 const x=await refreshWithReader({
  teamMap:MAP,previous,clock:()=> '2026-11-08T23:51:00Z',
  readLeague:async(id,target)=>{seen.push([id,target.teamId]);
    if(id==='highlight')throw Object.assign(new Error('secret should not leak'),{status:401});
    return one(id);}
 });
 assert.equal(x.ok,false);
 assert.equal(x.snapshot,previous);
 assert.deepEqual(seen.map(x=>x[0]),TEAM_IDS);
 assert.ok(!JSON.stringify(x).includes('secret should not leak'));
});
test('injected reader accepts all three new validated league responses',async()=>{
 const x=await refreshWithReader({teamMap:MAP,clock:()=>AT,readLeague:async id=>one(id)});
 assert.equal(x.ok,true);
 assert.equal(x.snapshot.week,9);
 assert.equal(x.snapshot.teams.highlight.roster.length,3);
});
test('no reader or invalid private mapping cannot manufacture a fresh snapshot',async()=>{
 const previous=run(bundle()).snapshot;
 const x=await refreshWithReader({teamMap:MAP,previous,clock:()=>AT});
 assert.equal(x.ok,false);
 assert.equal(x.snapshot,previous);
 const b=bundle();delete b.teamMap.quick;
 assert.equal(run(b,previous).ok,false);
});
