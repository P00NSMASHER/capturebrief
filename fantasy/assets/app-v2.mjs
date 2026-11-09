import {TEAM_IDS,normalizeSnapshot,getFreshness,rosterBuckets,slotsFromRoster,optimizeLineup,rankWaiverTargets,estimateWinChance,isSafeUrl,round,teamPath} from './engine.mjs';
import {preparePrivateImport} from './snapshot-import.mjs';

const BASE='/capturebrief/fantasy/';
const root=document.getElementById('root');
const PRIVATE_KEY='fantasy-hq-private-v3';
const CACHE_KEY='fantasy-hq-public-last-good-v2';
let current=null,source='published',loading=false,activeTab='overview',message='';
const $esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const txt=(v,empty='—')=>v===null||v===undefined||v===''?empty:String(v);
const num=(v,dec=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(dec):'—';
const cap=s=>String(s||'').replace(/(^|[\s_-])\w/g,c=>c.toUpperCase());
const selected=()=> 'brock';
const freshness=()=>getFreshness(current?.syncedAtIso);
const icon=(name)=>({bolt:'⚡',lineup:'▥',waiver:'↗',chart:'◉',home:'⌂',refresh:'↻'}[name]||'•');
const badge=(value,tone='neutral')=>'<span class="badge '+tone+'">'+$esc(value)+'</span>';
const section=(title,kicker,inner,more='')=>'<section class="panel"><div class="panelhead"><div><div class="label">'+$esc(kicker)+'</div><h2>'+$esc(title)+'</h2></div>'+more+'</div>'+inner+'</section>';
const empty=(title,detail)=>'<div class="empty"><div class="emptymark">◇</div><strong>'+$esc(title)+'</strong><p>'+$esc(detail)+'</p></div>';
function ageText(f){if(f.ageHours===null)return 'Timestamp unavailable';return f.ageHours<1?'Captured less than an hour ago':f.ageHours<24?'Captured '+num(f.ageHours,1)+'h ago':'Captured '+Math.floor(f.ageHours/24)+' days ago'}
function safeLeagueLink(team){return isSafeUrl(team.leagueUrl)?'<a class="minorbtn" href="'+$esc(team.leagueUrl)+'" target="_blank" rel="noopener noreferrer">Open Yahoo <span aria-hidden="true">↗</span></a>':''}
function nav(){
 const choices=[['overview','Overview','⌂'],['lineup','Lineup','▥'],['waivers','Waivers','↗'],['lab','Analysis','◉']];
 return '<nav class="bottomnav" role="tablist" aria-label="Brock Hard sections">'+choices.map(([id,label,glyph])=>
 '<button type="button" role="tab" aria-selected="'+(activeTab===id)+'" data-tab="'+id+'" class="'+(activeTab===id?'active':'')+'"><span class="navglyph">'+glyph+'</span><span>'+label+'</span></button>').join('')+'</nav>';
}
function masthead(team){const f=freshness();
  const currentTeam='<div class="context">BROCK HARD & TEE BAGGIN · YAHOO FOOTBALL</div>';
  return '<header class="masthead"><div class="masttop"><a href="'+BASE+'" class="brand"><span class="brandmark">F<span>.</span></span><span>FANTASY <b>HQ</b><small>COMMAND CENTER</small></span></a>'+
    '<button type="button" class="refreshbtn" data-action="refresh" '+(loading?'disabled':'')+' aria-label="Check latest published Yahoo capture">'+(loading?'Checking…':'↻ Refresh')+'</button></div>'+
    currentTeam+'<div class="statusrow"><span class="statusdot '+f.state+'"></span>'+
    '<span class="statusline">'+$esc(f.label)+'</span><span class="statussep">/</span><span>'+$esc(ageText(f))+'</span>'+
    '<span class="sourcelabel">'+(source==='private'?'PRIVATE CAPTURE · NOT LIVE':'PUBLISHED AUTO CAPTURE · NOT LIVE')+'</span></div></header>'}
function riskRibbon(){const f=freshness();const old=f.state==='stale'||f.state==='unknown';
  const line=old?'Recommendations, waivers, injuries and player status below reflect an archived snapshot. They are NOT verified for today.':
    source==='private'?'Local data was imported on this device. Verify the source timestamp before making roster moves.':
    'This page checks for newer Brock Hard captures automatically. The scheduled publisher can update hourly; this is not continuous Yahoo streaming.';
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
    '<div class="matchup"><div><div class="matchlabel">YOUR TEAM</div><div class="matchname">'+$esc(team.short)+'</div><div class="matchscore">'+num(mine.points)+'</div><div class="matchproj">Pregame projection '+num(mine.liveProjectedPoints??mine.projectedPoints)+'</div></div><span class="vs">VS</span>'+
    '<div class="against"><div class="matchlabel">OPPONENT</div><div class="matchname">'+$esc(opp.teamName||opp.name||'Opponent')+'</div><div class="matchscore">'+num(opp.points)+'</div><div class="matchproj">Pregame projection '+num(opp.liveProjectedPoints??opp.projectedPoints)+'</div></div></div>'+
    (typeof mine.winProbability==='number'?'<div class="subnote">Yahoo win probability at capture: '+num(mine.winProbability*100,0)+'%.</div>':'')+
    '<div class="subnote">Yahoo pregame projections may be lower than points already scored. Data does not update continuously.</div>');}
function controls(){return '<p class="controlcopy">Import a new Brock Hard JSON capture from your connected Flaim Fantasy conversation. Your file stays in this browser; this page does not contact Yahoo.</p>'+
  '<div class="controlrow"><button type="button" class="primarybutton" data-action="import">↥ Import updated Yahoo snapshot</button>'+
  (source==='private'?'<button type="button" class="minorbtn button" data-action="clear">Remove local capture</button>':'')+'</div>'+
  '<input id="importFile" type="file" accept=".json,application/json" hidden>'+
  '<div class="subnote">The capture is read-only and manual. This button imports a file; it is not a live Yahoo sync. Failed imports preserve your existing data.</div>'}
function stats(team){const flagCount=team.roster.filter(p=>p.injury).length;
  const val=(a,b)=>'<div class="metric"><div class="metriclabel">'+a+'</div><div class="metricvalue">'+$esc(b)+'</div></div>';
  return '<div class="metrics">'+val('RECORD',txt(team.record))+val('LEAGUE RANK',txt(team.rank))+
    val('WAIVER PRIORITY',txt(team.waiver))+val('ROSTER FLAGS',String(flagCount))+'</div>'}
function decision(team){const old=!freshness().actionable;return section(old?'Archived source note':'Flaim data status','LEAGUE DATA',
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
  const projected=typeof p.projection==='number'&&teamProjectionSupported();
  const scored=typeof p.actualPoints==='number'&&Number.isFinite(p.actualPoints);
  const points=projected?num(p.projection,2)+'<small>PROJECTION</small>':scored?num(p.actualPoints,2)+'<small>REPORTED PTS</small>':'—';
  return '<div class="playerrow"><span class="slot">'+$esc(txt(p.slot,'—'))+'</span><div class="playername"><strong>'+$esc(p.name)+'</strong><small>'+$esc([p.nflTeam,p.position].filter(Boolean).join(' · '))+'</small></div>'+injury+'<span class="proj">'+points+'</span></div>';
}
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
  const available=Array.isArray(team.availablePlayers)?team.availablePlayers:[];
  const availableRows=available.map(p=>{
    const status=p.acquisitionState==='free_agent'?'FREE AGENT':p.acquisitionState==='waivers'?'ON WAIVERS':'AVAILABLE';
    const when=p.waiverDate?' · waiver date '+$esc(p.waiverDate):'';
    const owned=Number.isFinite(p.percentOwned)?$esc(p.percentOwned+'% Yahoo-wide rostered'):'Yahoo market rate unavailable';
    return '<div class="waiverrow"><div><strong>'+$esc(p.name||'Unknown player')+'</strong><small>'+$esc([p.position,p.team].filter(Boolean).join(' · '))+' · '+owned+when+'</small></div>'+badge(status,'muted')+'</div>';
  }).join('');
  return section(old?'Archived available players':'Available in this league at capture','FLAIM FANTASY · YAHOO',availableRows?'<div class="list">'+availableRows+'</div><div class="subnote">This is league-specific availability as of the snapshot, not proof an immediate add is legal. Yahoo-wide rates are not ownership within this league.</div>':empty('No inventory captured','Available-player data was not included.'))+
    section('Projected add/drop impact','DECISION ENGINE',dynamic)+
    section(old?'Archived waiver notes':'Waiver watchlist','SNAPSHOT · NOT LIVE',
      oldCards?'<div class="list">'+oldCards+'</div>':empty('No waiver notes','Import an updated waiver inventory for this league.'))+
    '<div class="footnote">Yahoo waiver order, acquisition state, limits, deadlines and player eligibility must be checked directly before submitting any transaction.</div>';}
function labView(team){const m=team.matchupModel||null;
  const chance=m&&freshness().actionable?estimateWinChance(m.myProjected,m.oppProjected,m.mySigma,m.oppSigma):null;
  const side=scoreFor(team);
  const providerChance=freshness().actionable&&typeof side?.mine?.winProbability==='number'?side.mine.winProbability*100:null;
  return section('Matchup forecast','PROVIDER EVIDENCE',
    providerChance!==null?'<div class="winprob">'+num(providerChance,1)+'<small>% YAHOO-REPORTED WIN ESTIMATE</small></div><div class="subnote">This estimate can change during games and is not our custom model.</div>':
    chance===null?empty('Win probability not rated','A verified provider probability or a complete projection and uncertainty estimate for both teams is required.'):
      '<div class="winprob">'+num(chance,1)+'<small>% ESTIMATED WIN CHANCE</small></div>'+
      '<div class="subnote">Normal-distribution approximation; estimates are not guaranteed outcomes.</div>')+
    section('Playoff outlook','MONTE CARLO',
      empty('Full-season simulation not rated','Provide current standings, remaining schedule, playoff rules and matchup probabilities. This snapshot does not include complete evidence.'))+
    section('Trade evaluation','ROSTER VALUE',
      empty('Opponent roster valuation unavailable','Import current projections for both sides and roster requirements before comparing trades.'))+
    section('Recent league activity',team.transactionsCoverage?.limited?'HISTORY · BOUNDED':'HISTORY',
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
    riskRibbon()+'<div class="heroactions">'+safeLeagueLink(team)+'</div>'+
    '<div id="tabPanel" role="tabpanel">'+t+'</div>'+section('Data controls','PRESERVE YOUR SNAPSHOT',controls())+
    '<div class="footnote">Fantasy HQ operates in read-only mode. No transactions or lineup submissions occur through this application.</div></div>'+nav();}
function archivedView(){
 const date=Number.isFinite(Date.parse(current?.syncedAtIso))?
   new Date(current.syncedAtIso).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}):'unknown date';
 return '<div class="container">'+masthead()+messageBox()+
  '<section class="panel archived-fallback" role="status">'+
  '<div class="label">BROCK HARD · NO CURRENT CAPTURE</div>'+
  '<h1>Update your Yahoo data</h1>'+
  '<p><strong>Outdated fantasy data.</strong> The public file was captured '+$esc(date)+
  '. Week 4 results are intentionally hidden rather than shown as current.</p>'+
  '<button type="button" class="primarybutton" data-action="import">↥ Import updated Yahoo snapshot</button>'+
  '<input id="importFile" type="file" accept=".json,application/json" hidden>'+
  '<p class="subnote">Use the private JSON file from Flaim Fantasy in ChatGPT. It stays on this device. Automatic Yahoo sign-in is not enabled.</p>'+
  '</section><p class="footnote">Brock Hard only · read-only · no roster transactions</p></div>'+nav();
}
function render(){
 if(!root)return;
 if(!current){root.innerHTML='<div class="loader">Loading Brock Hard…</div>';return;}
 const team=current.teams.brock;
 document.title=team?'Brock Hard · Fantasy HQ':'Brock Hard · Data unavailable';
 root.innerHTML=team?(source==='published'&&!freshness().actionable?archivedView():teamView(team)):'<div class="loader">Brock Hard snapshot unavailable. Import a verified private snapshot.</div>';
}
function onlyBrockRaw(raw){
 const normalized=normalizeSnapshot(raw);
 if(!normalized.teams.brock||!raw?.teams?.brock)throw new Error('Brock Hard not present in the snapshot');
 const clean={};
 for(const key of ['schemaVersion','provider','season','week','syncedAtIso','syncedAt','source','captureType'])
  if(Object.hasOwn(raw,key))clean[key]=raw[key];
 clean.teams={brock:raw.teams.brock};
 return clean;
}
function captureMs(s){const n=Date.parse(s||'');return Number.isFinite(n)?n:-Infinity}
function validatePublished(raw){
 const cleaned=onlyBrockRaw(raw);
 const snapshot=normalizeSnapshot(cleaned);
 if(snapshot.schemaVersion===3 &&
    (snapshot.teams.brock.leagueId!=='470.l.290846'||snapshot.teams.brock.teamId!=='2'))
    throw new Error('Published source is not the authorized Brock Hard team');
 if(captureMs(snapshot.syncedAtIso)===-Infinity||captureMs(snapshot.syncedAtIso)>Date.now()+300000)
    throw new Error('Published capture time is missing or invalid');
 return {raw:cleaned,snapshot};
}
async function getPublic(){
 const r=await fetch(BASE+'data.json?cachebust='+Date.now(),{cache:'no-store',headers:{Accept:'application/json'}});
 if(!r.ok)throw new Error('Published snapshot request returned HTTP '+r.status);
 const result=validatePublished(await r.json());
 try{
  const stored=localStorage.getItem(CACHE_KEY);
  const existing=stored?validatePublished(JSON.parse(stored)).snapshot:null;
  if(!existing||captureMs(result.snapshot.syncedAtIso)>captureMs(existing.syncedAtIso))
    localStorage.setItem(CACHE_KEY,JSON.stringify(result.raw));
 }catch{}
 return result.snapshot;
}
function acceptNewer(latest){
 if(!latest?.teams?.brock||!Number.isFinite(captureMs(latest.syncedAtIso)))return false;
 if(current&&captureMs(latest.syncedAtIso)<=captureMs(current.syncedAtIso))return false;
 current=latest;source='published';
 try{localStorage.removeItem(PRIVATE_KEY)}catch{}
 return true;
}
async function refresh(silent=false){
 if(loading)return;
 loading=true;
 if(!silent){message='Checking the newest published Brock Hard capture. Yahoo is not contacted by this page.';render();}
 try{
  const latest=await getPublic(),changed=acceptNewer(latest);
  if(changed)message='Verified newer provider capture loaded: '+latest.syncedAtIso+'. This is a saved snapshot, not continuous live sync.';
  else if(!silent)message='Already showing the newest verified capture available. Captured at '+(current?.syncedAtIso||'unknown')+'.';
 }catch(err){if(!silent)message='Update unavailable: '+err.message+'. Previous verified capture retained.'}
 finally{loading=false;render()}
}
async function handleImport(file){if(!file)return;
 if(file.size>2_000_000){message='Import rejected: limit is 2 MB.';render();return;}
 try{
  const raw=JSON.parse(await file.text());
  if(raw.schemaVersion!==3)throw new Error('Private import requires schemaVersion 3');
  const brockOnly=preparePrivateImport(raw,{previousIso:source==='private'?current?.syncedAtIso:null});
  const normalized=normalizeSnapshot(brockOnly);
  try{localStorage.setItem(PRIVATE_KEY,JSON.stringify(brockOnly))}catch{throw new Error('Browser storage is unavailable')}
  current=normalized;source='private';message='Brock Hard capture imported privately. No file was uploaded or published. This is not live synchronization.';render();
 }catch(e){message='Import rejected: '+e.message;render()}
}
document.addEventListener('click',event=>{
 const tab=event.target.closest('button[data-tab]');
 if(tab){activeTab=tab.dataset.tab;render();return}
 const control=event.target.closest('[data-action]');if(!control)return;
 if(control.dataset.action==='refresh')refresh(false);
 if(control.dataset.action==='import')document.getElementById('importFile')?.click();
 if(control.dataset.action==='clear'){
  localStorage.removeItem(PRIVATE_KEY);source='published';message='Private import cleared from this browser.';
  try{const c=localStorage.getItem(CACHE_KEY);if(c){const safe=onlyBrockRaw(JSON.parse(c));current=normalizeSnapshot(safe);localStorage.setItem(CACHE_KEY,JSON.stringify(safe))}else current=null}catch{current=null}
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
  if(stored){
   const safe=onlyBrockRaw(JSON.parse(stored)),snap=normalizeSnapshot(safe);
   if(snap.schemaVersion===3&&captureMs(snap.syncedAtIso)!==-Infinity){
    current=snap;source='private';
    localStorage.setItem(PRIVATE_KEY,JSON.stringify(safe));
   }
  }
 }catch{try{localStorage.removeItem(PRIVATE_KEY)}catch{}}
 if(current)render();
 try{acceptNewer(await getPublic())}
 catch(error){
  if(!current){
   try{
    const cached=localStorage.getItem(CACHE_KEY);
    if(cached){const old=validatePublished(JSON.parse(cached));current=old.snapshot;source='published';message='Network error. Showing previously verified published capture.'}
   }catch{}
  }
  if(!current){root.innerHTML='<div class="loader"><strong>Fantasy HQ could not load.</strong><p>'+$esc(error.message)+'</p><button class="primarybutton" data-action="refresh">Retry</button></div>'}
 }
 if(current)render();
 // iPhone background tabs may suspend timers. A visibility check catches the next foreground visit.
 const check=()=>{if(document.visibilityState==='visible')refresh(true)};
 setInterval(check,5*60*1000);
 document.addEventListener('visibilitychange',check);
 window.addEventListener('focus',check);
})();
