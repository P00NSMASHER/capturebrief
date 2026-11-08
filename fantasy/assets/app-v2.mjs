import {TEAM_IDS,normalizeSnapshot,getFreshness,rosterBuckets,slotsFromRoster,optimizeLineup,rankWaiverTargets,estimateWinChance,isSafeUrl,round,teamPath} from './engine.mjs';

const BASE='/capturebrief/fantasy/';
const root=document.getElementById('root');
const PRIVATE_KEY='fantasy-hq-private-v3';
const CACHE_KEY='fantasy-hq-public-last-good-v2';
let current=null,source='published',loading=false,activeTab='overview',message='';
const $esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const txt=(v,empty='—')=>v===null||v===undefined||v===''?empty:String(v);
const num=(v,dec=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(dec):'—';
const cap=s=>String(s||'').replace(/(^|[\s_-])\w/g,c=>c.toUpperCase());
const selected=()=>document.body.dataset.team||null;
const freshness=()=>getFreshness(current?.syncedAtIso);
const icon=(name)=>({bolt:'⚡',lineup:'▥',waiver:'↗',chart:'◉',home:'⌂',refresh:'↻'}[name]||'•');
const badge=(value,tone='neutral')=>'<span class="badge '+tone+'">'+$esc(value)+'</span>';
const section=(title,kicker,inner,more='')=>'<section class="panel"><div class="panelhead"><div><div class="label">'+$esc(kicker)+'</div><h2>'+$esc(title)+'</h2></div>'+more+'</div>'+inner+'</section>';
const empty=(title,detail)=>'<div class="empty"><div class="emptymark">◇</div><strong>'+$esc(title)+'</strong><p>'+$esc(detail)+'</p></div>';
function ageText(f){if(f.ageHours===null)return 'Timestamp unavailable';return f.ageHours<1?'Updated less than an hour ago':f.ageHours<24?'Updated '+num(f.ageHours,1)+'h ago':'Updated '+Math.floor(f.ageHours/24)+' days ago'}
function safeLeagueLink(team){return isSafeUrl(team.leagueUrl)?'<a class="minorbtn" href="'+$esc(team.leagueUrl)+'" target="_blank" rel="noopener noreferrer">Open Yahoo <span aria-hidden="true">↗</span></a>':''}
function nav(){return '<nav class="bottomnav" aria-label="Choose fantasy team">'+
  '<a href="'+BASE+'" class="'+(!selected()?'active':'')+'"><span class="navglyph">⌂</span><span>HOME</span></a>'+
  TEAM_IDS.map(id=>{const t=current?.teams[id];return '<a href="'+teamPath(id)+'" class="'+(selected()===id?'active':'')+'"><span class="navglyph">'+(id==='brock'?'B':id==='quick'?'Q':'H')+'</span><span>'+ $esc(t?.short?.split(' ')[0]||id.toUpperCase())+'</span></a>'}).join('')+
  '</nav>'}
function masthead(team){const f=freshness();
  const currentTeam=team?'<div class="context">'+$esc(team.name)+'</div>':'<div class="context">THREE LEAGUES · ONE COMMAND CENTER</div>';
  return '<header class="masthead"><div class="masttop"><a href="'+BASE+'" class="brand"><span class="brandmark">F<span>.</span></span><span>FANTASY <b>HQ</b><small>COMMAND CENTER</small></span></a>'+
    '<button class="refreshbtn" data-action="refresh" '+(loading?'disabled':'')+' aria-label="Recheck published snapshot">'+(loading?'Checking…':'↻ Check snapshot')+'</button></div>'+
    currentTeam+'<div class="statusrow"><span class="statusdot '+f.state+'"></span>'+
    '<span class="statusline">'+$esc(f.label)+'</span><span class="statussep">/</span><span>'+$esc(ageText(f))+'</span>'+
    '<span class="sourcelabel">'+(source==='private'?'PRIVATE IMPORT':'PUBLISHED SNAPSHOT')+'</span></div></header>'}
function riskRibbon(){const f=freshness();const old=f.state==='stale'||f.state==='unknown';
  const line=old?'Recommendations, waivers, injuries and player status below reflect an archived snapshot. They are NOT verified for today.':
    source==='private'?'Local data was imported on this device. Verify the source timestamp before making roster moves.':
    'This is the latest published snapshot, not a direct live Yahoo connection.';
  return '<div class="riskbar '+(old?'archived':'')+'"><span class="riskicon">'+(old?'!':'i')+'</span><div><strong>'+(old?'Outdated fantasy data':'Data source notice')+'</strong><p>'+$esc(line)+'</p></div></div>'}
function messageBox(){return message?'<div class="toast" role="status">'+$esc(message)+'</div>':''}
function scoreFor(team){const m=team.matchup;if(!m)return null;
  if (m.my&&m.opponent)return {mine:m.my,opp:m.opponent};
  if(!m.home||!m.away)return null;
  const own=String(team.teamId);
  const home=String(m.home.teamId||m.home.teamKey?.split('.t.').pop()||'');
  const away=String(m.away.teamId||m.away.teamKey?.split('.t.').pop()||'');
  if(own!==home&&own!==away)return null;
  return own===home?{mine:m.home,opp:m.away}:{mine:m.away,opp:m.home};
}
function matchupCard(team){const side=scoreFor(team);
  if(!side)return section('This week','MATCHUP',empty('Scoreboard unavailable','A valid matchup for this team is not present in the saved snapshot.'));
  const mine=side.mine,opp=side.opp;
  return section('Matchup snapshot','WEEK '+txt(current.week,'—'),
    '<div class="matchup"><div><div class="matchlabel">YOUR TEAM</div><div class="matchname">'+$esc(team.short)+'</div><div class="matchscore">'+num(mine.points)+'</div><div class="matchproj">Projected '+num(mine.liveProjectedPoints??mine.projectedPoints)+'</div></div><span class="vs">VS</span>'+
    '<div class="against"><div class="matchlabel">OPPONENT</div><div class="matchname">'+$esc(opp.teamName||opp.name||'Opponent')+'</div><div class="matchscore">'+num(opp.points)+'</div><div class="matchproj">Projected '+num(opp.liveProjectedPoints??opp.projectedPoints)+'</div></div></div>'+
    '<div class="subnote">Scores and projections are from the snapshot timestamp, not the live scoreboard.</div>');}
function teamCard(id,t){const f=freshness(),warn=f.state==='stale'||f.state==='unknown';
  return '<a class="teamcard '+$esc(t.accent)+'" href="'+teamPath(id)+'"><div class="teamrow"><span class="teamlogo">'+(id==='brock'?'BH':id==='quick'?'QS':'HR')+'</span>'+
    '<div><div class="teamtitle">'+$esc(t.name)+'</div><div class="teamid">'+$esc(t.provider.toUpperCase())+' · '+$esc(txt(t.record))+' · '+$esc(txt(t.rank))+'</div></div><span class="chevron">↗</span></div>'+
    '<div class="teamdivider"></div><div class="teamlabel">'+(warn?'ARCHIVED RECOMMENDATION':'SNAPSHOT RECOMMENDATION')+'</div>'+
    '<div class="teamdecision">'+$esc(txt(t.nextMove,'No recommendation saved'))+'</div>'+
    '<div class="teamfoot"><span>Waiver '+$esc(t.waiver)+'</span><span>View team →</span></div></a>'}
function homeView(){const ts=Object.entries(current.teams);
  return '<div class="container">'+masthead()+'<div class="headline"><div class="label">2026 FANTASY SEASON</div><h1>Your teams.<br><em>One clear view.</em></h1>'+
    '<p>Compare all three leagues, inspect rosters and waivers, and use verified projections when available.</p></div>'+
    riskRibbon()+messageBox()+'<div class="kickerrow"><span>YOUR LEAGUES</span>'+badge(ts.length+' CONNECTED RECORDS')+'</div><div class="teamgrid">'+ts.map(([id,t])=>teamCard(id,t)).join('')+'</div>'+
    section('Data controls','SOURCE & PRIVACY',controls())+
    section('Available analysis','DECISION ENGINE',
      '<div class="capgrid"><div><b>01 / LINEUP</b><p>Exact legal slot assignment once league-specific projections are complete.</p></div>'+
      '<div><b>02 / WAIVERS</b><p>Compare add/drop scenarios only with verified availability and projections.</p></div>'+
      '<div><b>03 / MATCHUPS</b><p>Model win chance only when projected points and uncertainty are supplied.</p></div>'+
      '<div><b>04 / PLAYOFFS</b><p>Requires full remaining schedule, standings and playoff configuration.</p></div></div>')+
    '<div class="footnote">Read-only interface. No lineup moves, claims or trades are sent to fantasy providers.</div></div>'+nav();}
function controls(){return '<p class="controlcopy">Recheck the published JSON or import an updated private v3 snapshot stored only in this browser. Rechecking does not sign into Yahoo or produce new league data.</p>'+
  '<div class="controlrow"><button class="primarybutton" data-action="refresh">↻ Recheck published data</button><button class="minorbtn button" data-action="import">Import private JSON</button>'+
  (source==='private'?'<button class="minorbtn button" data-action="clear">Remove private import</button>':'')+'</div>'+
  '<input id="importFile" type="file" accept=".json,application/json" hidden>'+
  '<div class="subnote">The private import is stored on this device. Refreshing the page does not upload it to GitHub.</div>'}
function stats(team){const flagCount=team.roster.filter(p=>p.injury).length;
  const val=(a,b)=>'<div class="metric"><div class="metriclabel">'+a+'</div><div class="metricvalue">'+$esc(b)+'</div></div>';
  return '<div class="metrics">'+val('RECORD',txt(team.record))+val('LEAGUE RANK',txt(team.rank))+
    val('WAIVER PRIORITY',txt(team.waiver))+val('ROSTER FLAGS',String(flagCount))+'</div>'}
function decision(team){const old=!freshness().actionable;return section(old?'Historical recommendation':'Snapshot recommendation','PRIORITY INTELLIGENCE',
  '<div class="decisionbox"><div class="decisionflag">'+(old?'ARCHIVED · DO NOT ACT ON WITHOUT RECHECKING':'SNAPSHOT ASSESSMENT')+'</div>'+
  '<h3>'+$esc(txt(team.nextMove,'No saved recommendation'))+'</h3><p>'+$esc(team.nextDetail||'')+'</p>'+
  '<div class="decisionbottom">'+badge('Evidence: '+(old?'outdated':'snapshot'),old?'bad':'muted')+
  (team.confidence?badge('At capture: '+team.confidence):'')+'</div></div>');}
function alertList(team){const alerts=team.alerts||[];
  return section('Roster alerts','HEALTH & AVAILABILITY',alerts.length?
    '<div class="list">'+alerts.map(a=>'<div class="alertrow"><span class="alertdot '+$esc(a.level||'watch')+'"></span><div><strong>'+$esc(a.title||'Roster alert')+'</strong><p>'+$esc(a.text||'')+'</p></div></div>').join('')+'</div>':
    empty('No saved alerts','This does not prove that the live roster has no injuries.'))}
function strategy(team){const s=team.strategy;if(!s)return '';
  return section('Saved analysis','EXPLANATION',
    '<p class="bodycopy">'+$esc(s.summary||'')+'</p>'+
    '<div class="strategygrid">'+(s.bullets||[]).map(b=>'<div><span>'+$esc(b.label||'')+'</span><p>'+$esc(b.text||'')+'</p></div>').join('')+'</div>');}
function summaryView(team){return stats(team)+matchupCard(team)+decision(team)+alertList(team)+strategy(team);}
function playerRow(p){const injury=p.injury?badge(p.injury,'bad'):'';
  return '<div class="playerrow"><span class="slot">'+$esc(txt(p.slot,'—'))+'</span><div class="playername"><strong>'+$esc(p.name)+'</strong><small>'+$esc([p.nflTeam,p.position].filter(Boolean).join(' · '))+'</small></div>'+
    injury+'<span class="proj">'+(typeof p.projection==='number'&&teamProjectionSupported()?num(p.projection)+'<small>PROJ</small>':'—')+'</span></div>';}
function teamProjectionSupported(){const t=current?.teams[selected()];return t?.projectionCoverage==='complete'}
function lineupView(team){const buckets=rosterBuckets(team.roster);
  const optimizer=freshness().actionable&&team.projectionCoverage==='complete'?optimizeLineup(team.roster,team.lineupSlots||slotsFromRoster(team.roster)):
    {available:false,reason:'No complete, current, player-level projection set is present'};
  let opt='';
  if(optimizer.available){
    opt='<div class="optresult"><div><div class="label">MAXIMIZED PROJECTED POINTS</div><div class="optbig">'+num(optimizer.score,2)+'</div></div>'+
    '<div class="optgain">'+(optimizer.gain===null?'BASELINE UNKNOWN':(optimizer.gain>=0?'+':'')+num(optimizer.gain,2)+' VS CURRENT')+'</div></div>'+
    '<div class="list">'+optimizer.assignments.map(a=>playerRow({...a.player,slot:a.slot})).join('')+'</div>'+
    '<div class="subnote">Advisory projection optimization only; provider lineup locks and actual submission are not performed.</div>';
  }else opt=empty('Optimization unavailable',optimizer.reason+'. Missing values are never replaced with guesses.');
  return section('Projected optimal lineup','EXACT SLOT ASSIGNMENT',opt)+
    section('Starting roster','CURRENT SNAPSHOT',buckets.starters.length?'<div class="list">'+buckets.starters.map(playerRow).join('')+'</div>':empty('No starters found','Import a full roster snapshot.'))+
    section('Bench','DEPTH',buckets.bench.length?'<div class="list">'+buckets.bench.map(playerRow).join('')+'</div>':empty('No bench entries','No bench data was saved.'))+
    section('Reserve / IR','INJURY LIST',buckets.reserve.length?'<div class="list">'+buckets.reserve.map(playerRow).join('')+'</div>':empty('No reserve entries','No reserve players are present in the saved snapshot.'));}
function waiverView(team){const old=!freshness().actionable, rated=old?{available:false,reason:'Archived snapshot: cannot rank waivers safely'}:rankWaiverTargets(team);
  let dynamic=rated.available?(rated.recommendations.length?
    '<div class="list">'+rated.recommendations.map(r=>'<div class="waiverrow"><div><strong>'+$esc(r.add)+'</strong><small>Drop '+$esc(r.drop)+' · '+$esc(r.status)+'</small></div>'+badge('+'+num(r.improvement,2)+' pts','good')+'</div>').join('')+'</div>':
    empty('No positive projected upgrade found','Among the imported candidates and droppable bench players.')):
    empty('No verified waiver ranking',rated.reason);
  const oldCards=(team.waivers||[]).map(w=>'<div class="waiverrow"><div><strong>'+$esc(w.name||'Unknown')+'</strong><small>'+$esc(w.pos||'')+'</small><p>'+$esc(w.why||'')+'</p></div>'+badge(w.tag||'ARCHIVE',old?'bad':'muted')+'</div>').join('');
  return section('Projected add/drop impact','DECISION ENGINE',dynamic)+
    section(old?'Archived waiver notes':'Waiver watchlist','SNAPSHOT · NOT LIVE',
      oldCards?'<div class="list">'+oldCards+'</div>':empty('No waiver notes','Import an updated waiver inventory for this league.'))+
    '<div class="footnote">Yahoo waiver order, acquisition state, limits, deadlines and player eligibility must be checked directly before submitting any transaction.</div>';}
function labView(team){const m=team.matchupModel||null;
  const chance=m&&freshness().actionable?estimateWinChance(m.myProjected,m.oppProjected,m.mySigma,m.oppSigma):null;
  return section('Matchup forecast','PROBABILITY MODEL',
    chance===null?empty('Win probability not rated','A valid current projection and uncertainty estimate for both teams is required.'):
      '<div class="winprob">'+num(chance,1)+'<small>% ESTIMATED WIN CHANCE</small></div>'+
      '<div class="subnote">Normal-distribution approximation; estimates are not guaranteed outcomes.</div>')+
    section('Playoff outlook','MONTE CARLO',
      empty('Full-season simulation not rated','Provide current standings, remaining schedule, playoff rules and matchup probabilities. This snapshot does not include complete evidence.'))+
    section('Trade evaluation','ROSTER VALUE',
      empty('Opponent roster valuation unavailable','Import current projections for both sides and roster requirements before comparing trades.'))+
    section('Recent league activity','HISTORY',
      team.transactions.length?'<div class="list">'+team.transactions.slice(0,20).map(tr=>
        '<div class="transaction"><span>'+$esc(txt(tr.date,''))+'</span><strong>'+$esc(tr.move||tr.type||'League transaction')+'</strong><small>'+$esc(tr.team||'')+'</small></div>').join('')+'</div>':
        empty('No stored transactions','Historical activity is not verified as complete.'))}
function tabbar(){return '<div class="tabs" role="tablist" aria-label="Team dashboard views">'+[
  ['overview','Overview'],['lineup','Lineup'],['waivers','Waivers'],['lab','Analysis']].map(([id,label])=>
   '<button type="button" role="tab" aria-selected="'+(id===activeTab)+'" class="'+(id===activeTab?'active':'')+'" data-tab="'+id+'">'+label+'</button>').join('')+'</div>';}
function teamView(team){const t=activeTab==='lineup'?lineupView(team):activeTab==='waivers'?waiverView(team):activeTab==='lab'?labView(team):summaryView(team);
  return '<div class="container">'+masthead(team)+messageBox()+
    '<div class="teamhero '+$esc(team.accent)+'"><div><span class="label">YOUR TEAM / '+$esc(team.provider.toUpperCase())+'</span><h1>'+$esc(team.name)+'</h1>'+
    '<div class="herosub">Season '+current.season+' · Week '+txt(current.week)+' · '+$esc(txt(team.record))+'</div></div>'+
    '<span class="crest">'+(team.id==='brock'?'BH':team.id==='quick'?'QS':'HR')+'</span></div>'+
    riskRibbon()+'<div class="heroactions">'+safeLeagueLink(team)+'<a class="minorbtn" href="'+BASE+'">All teams</a></div>'+
    tabbar()+'<div id="tabPanel" role="tabpanel">'+t+'</div>'+section('Data controls','PRESERVE YOUR SNAPSHOT',controls())+
    '<div class="footnote">Fantasy HQ operates in read-only mode. No transactions or lineup submissions occur through this application.</div></div>'+nav();}
function render(){if(!root)return;
 if(!current){root.innerHTML='<div class="loader">Loading Fantasy HQ…</div>';return;}
 const key=selected(),team=current.teams[key];
 document.title=team?team.short+' · Fantasy HQ':'Fantasy HQ · Command Center';
 root.innerHTML=key?(team?teamView(team):'<div class="loader">Team not found. <a href="'+BASE+'">Return home</a></div>'):homeView();}
async function getPublic() {
 const r=await fetch(BASE+'data.json?cachebust='+Date.now(),{cache:'no-store',headers:{Accept:'application/json'}});
 if(!r.ok)throw new Error('Published snapshot request returned HTTP '+r.status);
 const raw=await r.json(),normalized=normalizeSnapshot(raw);
 try{localStorage.setItem(CACHE_KEY,JSON.stringify(raw))}catch{}
 return normalized;
}
async function refresh(){if(loading)return;loading=true;message='Checking the published snapshot. This does not authenticate with Yahoo.';render();
 try {
   const latest=await getPublic();
   if(source==='private')message='Published snapshot checked; the private import remains active. Remove it to view the public data.';
   else {current=latest;message='Published snapshot loaded. Data timestamp: '+(latest.syncedAtIso||'unknown')+'.';}
 }catch(err){message='Update failed: '+err.message+'. The previous snapshot remains visible.'}
 finally{loading=false;render()}}
async function handleImport(file){if(!file)return;
 if(file.size>2_000_000){message='Import rejected: limit is 2 MB.';render();return;}
 try{
  const raw=JSON.parse(await file.text());
  if(raw.schemaVersion!==3)throw new Error('Private import requires schemaVersion 3');
  const normalized=normalizeSnapshot(raw);
  try{localStorage.setItem(PRIVATE_KEY,JSON.stringify(raw))}catch{throw new Error('Browser storage is unavailable')}
  current=normalized;source='private';message='Private JSON imported locally. No file was uploaded.';render();
 }catch(e){message='Import rejected: '+e.message;render()}
}
document.addEventListener('click',event=>{
 const tab=event.target.closest('button[data-tab]');
 if(tab){activeTab=tab.dataset.tab;render();return}
 const control=event.target.closest('[data-action]');if(!control)return;
 if(control.dataset.action==='refresh')refresh();
 if(control.dataset.action==='import')document.getElementById('importFile')?.click();
 if(control.dataset.action==='clear'){
  localStorage.removeItem(PRIVATE_KEY);source='published';message='Private import cleared from this browser.';
  try{const c=localStorage.getItem(CACHE_KEY);current=c?normalizeSnapshot(JSON.parse(c)):null}catch{current=null}
  if(current)render();else refresh();
 }
});
document.addEventListener('change',event=>{
 if(event.target.id==='importFile'){handleImport(event.target.files?.[0]);event.target.value='';}
});
(async()=>{
 const hash=location.hash.replace('#','');
 if(['overview','lineup','waivers','lab'].includes(hash))activeTab=hash;
 try{
   const stored=localStorage.getItem(PRIVATE_KEY);
   if(stored){current=normalizeSnapshot(JSON.parse(stored));source='private';render();return;}
 }catch{try{localStorage.removeItem(PRIVATE_KEY)}catch{}}
 try{current=await getPublic();}
 catch(e){
  try{const cached=localStorage.getItem(CACHE_KEY);if(cached){current=normalizeSnapshot(JSON.parse(cached));message='Network error. Showing the last successfully cached public snapshot.'}}
  catch{}
  if(!current){root.innerHTML='<div class="loader"><strong>Fantasy HQ could not load.</strong><p>'+$esc(e.message)+'</p><button class="primarybutton" data-action="refresh">Retry</button></div>';return;}
 }
 render();
})();
