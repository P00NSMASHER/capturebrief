import {TEAM_IDS,normalizeSnapshot,getFreshness,rosterBuckets,slotsFromRoster,optimizeLineup,rankWaiverTargets,estimateWinChance,isSafeUrl,round,teamPath,rosterStatusAlerts,compareScoredLineup,marketWatchlist,positionDepth} from './engine.mjs';
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
function decision(team){
 const old=!freshness().actionable;
 const flags=rosterStatusAlerts(team.roster);
 const rosterCount=Array.isArray(team.roster)?team.roster.length:0;
 const candidates=Array.isArray(team.availablePlayers)?team.availablePlayers.length:0;
 const movements=Array.isArray(team.transactions)?team.transactions.length:0;
 const note=String(team.nextMove||'');
 const generic=/^No verified projected|^No saved recommendation|^Optimization unavailable/i.test(note);
 const headline=generic?'Brock Hard snapshot available':txt(team.nextMove,'Brock Hard snapshot available');
 const detail=generic?
   'Captured '+rosterCount+' Yahoo roster players, '+candidates+' league-available players, '+movements+
   ' recent completed movements, and '+flags.length+' roster status flags. The lineup and waiver tabs use the verified evidence available; future player projections were not supplied.':
   team.nextDetail||'Capture details are available on the Lineup, Waivers and Analysis tabs.';
 const enrichment=team.analysisAsOfIso?
   '<div class="subnote">Standings and upcoming matchup outlook checked '+$esc(team.analysisAsOfIso)+'. Core roster capture: '+$esc(txt(current.syncedAtIso))+'.</div>':'';
 return section(old?'Archived data coverage':'Flaim data coverage','LEAGUE DATA',
  '<div class="decisionbox"><div class="decisionflag">'+(old?'ARCHIVED · RECHECK IN YAHOO':'SNAPSHOT COVERAGE')+'</div>'+
  '<h3>'+$esc(headline)+'</h3><p>'+$esc(detail)+'</p>'+
  '<div class="decisionbottom">'+badge('Evidence: '+(old?'archived':'provider snapshot'),old?'bad':'muted')+
  (team.confidence?badge('At capture: '+team.confidence):'')+'</div>'+enrichment+'</div>');
}
function alertList(team){
  const derived=rosterStatusAlerts(team.roster), manual=Array.isArray(team.alerts)?team.alerts:[];
  const alerts=[...derived,...manual];
  return section('Roster status alerts','YAHOO STATUS AT CAPTURE',alerts.length?
    '<div class="list">'+alerts.map(a=>'<div class="alertrow"><span class="alertdot '+$esc(a.level||'watch')+'"></span><div><strong>'+$esc(a.title||'Roster status')+'</strong><p>'+$esc(a.text||'')+'</p></div></div>').join('')+'</div>'+
    '<div class="subnote">'+derived.length+' Yahoo status flags at capture. Verify current health and lineup eligibility in Yahoo before moving players.</div>':
    '<div class="subnote">No provider status flags were included in this capture. This is not proof that the live roster is healthy.</div>');}
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
function lineupView(team){
  const buckets=rosterBuckets(team.roster);
  const counts=team.lineupSlots||slotsFromRoster(team.roster);
  const optimizer=freshness().actionable&&team.projectionCoverage==='complete'?optimizeLineup(team.roster,counts):
    {available:false,reason:'A complete verified future player projection set was not supplied'};
  const scored=compareScoredLineup(team.roster,counts);
  let opt='',title='Projected optimal lineup',kicker='EXACT SLOT ASSIGNMENT';
  if(optimizer.available){
    opt='<div class="optresult"><div><div class="label">MAXIMIZED PROJECTED POINTS</div><div class="optbig">'+num(optimizer.score,2)+'</div></div>'+
    '<div class="optgain">'+(optimizer.gain===null?'BASELINE UNKNOWN':(optimizer.gain>=0?'+':'')+num(optimizer.gain,2)+' VS CURRENT')+'</div></div>'+
    '<div class="list">'+optimizer.assignments.map(a=>playerRow({...a.player,slot:a.slot})).join('')+'</div>'+
    '<div class="subnote">Advisory projected-point optimization; Yahoo locks and transactions are not handled by this page.</div>';
  }else if(scored.available){
    title='Highest-scoring lineup so far';kicker='WEEK '+txt(current.week)+' · ACTUAL POINTS';
    const swaps=scored.in.length?
      '<div class="waiverrow"><div><strong>Hindsight difference</strong><small>Bench in: '+$esc(scored.in.join(', '))+'</small><small>Starter out: '+$esc(scored.out.join(', '))+'</small></div></div>':
      '<div class="subnote">Your starters already match the highest-scoring combination at capture.</div>';
    opt='<div class="optresult"><div><div class="label">HIGHEST POINTS ALREADY SCORED</div><div class="optbig">'+num(scored.best,2)+'</div></div>'+
      '<div class="optgain">'+(scored.gap>0?'+':'')+num(scored.gap,2)+' VS CURRENT '+num(scored.current,2)+'</div></div>'+
      swaps+'<div class="subnote">Retrospective, week-to-date Yahoo scoring only. These are NOT future projections or start/sit recommendations. Some players may be locked; scores can change.</div>';
  }else{
    title='Lineup coverage';kicker='EVIDENCE CHECK';
    opt='<div class="subnote">Verified future player projections are absent, and a complete scored-player comparison could not be calculated: '+$esc(scored.reason)+'. Current assignments remain shown below without speculative recommendations.</div>';
  }
  return section(title,kicker,opt)+
    section('Starting roster','CURRENT SNAPSHOT',buckets.starters.length?'<div class="list">'+buckets.starters.map(playerRow).join('')+'</div>':empty('No starters found','Import a full roster snapshot.'))+
    section('Bench','DEPTH',buckets.bench.length?'<div class="list">'+buckets.bench.map(playerRow).join('')+'</div>':empty('No bench entries','No bench data was saved.'))+
    section('Reserve / IR','INJURY LIST',buckets.reserve.length?'<div class="list">'+buckets.reserve.map(playerRow).join('')+'</div>':'<div class="subnote">No reserve assignments at capture.</div>');}
function waiverView(team){
  const old=!freshness().actionable;
  const rated=old?{available:false,reason:'Archived capture'}:rankWaiverTargets(team);
  const market=marketWatchlist(team.availablePlayers,5);
  const dynamic=rated.available?(rated.recommendations.length?
    '<div class="list">'+rated.recommendations.map(r=>'<div class="waiverrow"><div><strong>'+$esc(r.add)+'</strong><small>Drop '+$esc(r.drop)+' · '+$esc(r.status)+'</small></div>'+badge('+'+num(r.improvement,2)+' pts','good')+'</div>').join('')+'</div>':
    '<div class="subnote">No positive verified projected upgrade among captured candidates.</div>'):
    (market.length?'<div class="list">'+market.map(p=>'<div class="waiverrow"><div><strong>'+$esc(p.name)+'</strong><small>'+$esc([p.position,p.team].filter(Boolean).join(' · '))+' · '+$esc(p.acquisitionState==='waivers'?'On waivers':'Free agent')+'</small></div>'+badge(num(p.percentOwned,0)+'% rostered','muted')+'</div>').join('')+'</div>':
      '<div class="subnote">No provider-backed available players were captured.</div>')+
    '<div class="subnote">Ranked only by Yahoo-wide market roster rate, not projected performance or add/drop uplift. Yahoo’s market percentage is not this league’s ownership rate.</div>';
  const available=Array.isArray(team.availablePlayers)?team.availablePlayers:[];
  const availableRows=available.map(p=>{
    const status=p.acquisitionState==='free_agent'?'FREE AGENT':p.acquisitionState==='waivers'?'ON WAIVERS':'STATE UNKNOWN';
    const when=p.waiverDate?' · waiver date '+$esc(p.waiverDate):'';
    const owned=Number.isFinite(p.percentOwned)?$esc(p.percentOwned+'% Yahoo-wide rostered'):'Market rate unavailable';
    return '<div class="waiverrow"><div><strong>'+$esc(p.name||'Unknown player')+'</strong><small>'+$esc([p.position,p.team].filter(Boolean).join(' · '))+' · '+owned+when+'</small></div>'+badge(status,'muted')+'</div>';
  }).join('');
  const depth=positionDepth(team.roster);
  const depthRows=depth.map(d=>'<div class="waiverrow"><div><strong>'+$esc(d.position)+' · '+d.total+' rostered</strong><small>'+d.active+' non-IR · '+d.flagged+' Yahoo status flag'+(d.flagged===1?'':'s')+'</small></div></div>').join('');
  return section(old?'Archived available players':'Available in this league at capture','FLAIM FANTASY · YAHOO',availableRows?'<div class="list">'+availableRows+'</div><div class="subnote">League-specific availability at the saved capture; no claim that an acquisition is currently legal.</div>':'<div class="subnote">No available-player inventory was published in this capture.</div>')+
    section(rated.available?'Projected add/drop uplift':'Top market-rate candidates',rated.available?'VERIFIED PROJECTION ENGINE':'YAHOO MARKET · NOT A PROJECTION',dynamic)+
    section('Roster depth for waiver decisions','SAVED BROCK HARD ROSTER','<div class="list">'+depthRows+'</div><div class="subnote">Position counts describe your roster, not a prescription to drop or add a player.</div>')+
    '<div class="footnote">Check Yahoo’s current waiver status, deadlines, eligible positions and roster rules before any transaction.</div>';
}
function labView(team){
  const m=team.matchupModel||null;
  const chance=m&&freshness().actionable?estimateWinChance(m.myProjected,m.oppProjected,m.mySigma,m.oppSigma):null;
  const side=scoreFor(team);
  const providerChance=freshness().actionable&&typeof side?.mine?.winProbability==='number'?side.mine.winProbability*100:null;
  const facts=team.standings&&typeof team.standings==='object'?team.standings:{};
  const standings='<div class="metrics">'+
    '<div class="metric"><div class="metriclabel">LEAGUE RANK</div><div class="metricvalue">'+$esc(txt(team.rank))+'</div></div>'+
    '<div class="metric"><div class="metriclabel">RECORD</div><div class="metricvalue">'+$esc(txt(team.record))+'</div></div>'+
    (Number.isFinite(facts.pointsFor)?'<div class="metric"><div class="metriclabel">POINTS FOR</div><div class="metricvalue">'+num(facts.pointsFor,1)+'</div></div>':'')+
    (Number.isFinite(facts.pointsAgainst)?'<div class="metric"><div class="metriclabel">POINTS AGAINST</div><div class="metricvalue">'+num(facts.pointsAgainst,1)+'</div></div>':'')+
    '</div>';
  const schedule=Array.isArray(team.upcomingMatchups)?team.upcomingMatchups.filter(x=>Number.isInteger(x.week)&&x.week>current.week&&x.opponent&&Number.isFinite(x.myProjected)&&Number.isFinite(x.opponentProjected)).slice(0,5):[];
  const schedules=schedule.length?'<div class="list">'+schedule.map(x=>
    '<div class="waiverrow"><div><strong>Week '+x.week+' vs '+$esc(x.opponent)+'</strong>'+
    '<small>Yahoo pregame team forecast: '+num(x.myProjected,1)+' vs '+num(x.opponentProjected,1)+'</small></div>'+
    badge((x.myProjected-x.opponentProjected>=0?'+':'')+num(x.myProjected-x.opponentProjected,1)+' pts','muted')+'</div>').join('')+'</div>':'';
  const depth=positionDepth(team.roster);
  const tradeDepth='<div class="list">'+depth.map(d=>'<div class="waiverrow"><div><strong>'+$esc(d.position)+' · '+d.total+' rostered</strong>'+
    '<small>'+d.active+' non-IR · '+d.flagged+' player status flag'+(d.flagged===1?'':'s')+'</small></div></div>').join('')+'</div>'+
    '<div class="subnote">Position depth is verified from Brock Hard’s roster. Actual weekly scores are not rest-of-season trade values. A fair-value trade calculation requires the specific incoming players and comparable verified forward projections.</div>';
  return section('Matchup forecast','PROVIDER EVIDENCE',
    providerChance!==null?'<div class="winprob">'+num(providerChance,1)+'<small>% YAHOO-REPORTED WIN ESTIMATE</small></div><div class="subnote">Yahoo’s captured estimate may change; it is not a custom simulation.</div>':
    chance===null?'<div class="subnote">Yahoo did not provide a verified matchup probability at this capture.</div>':
      '<div class="winprob">'+num(chance,1)+'<small>% MODEL ESTIMATE</small></div>'+
      '<div class="subnote">Normal-distribution approximation only.</div>')+
    section('Playoff race','VERIFIED STANDINGS · NO FABRICATED ODDS',
      standings+schedules+
      '<div class="subnote">These are saved league standings'+(schedule.length?' and Yahoo’s upcoming pregame team forecasts':'')+(team.analysisAsOfIso?' (outlook checked '+$esc(team.analysisAsOfIso)+')':'')+'. A playoff probability requires verified playoff rules and a complete remaining schedule with defensible win probabilities; none is invented.</div>')+
    section('Trade preparation','VERIFIED ROSTER DEPTH · NO GUESSED VALUE',tradeDepth)+
    section('Recent Brock Hard activity',team.transactionsCoverage?.limited?'HISTORY · BOUNDED':'HISTORY',
      team.transactions.length?'<div class="list">'+team.transactions.slice(0,20).map(tr=>
        '<div class="transaction"><span>'+$esc(txt(tr.date,''))+'</span><strong>'+$esc(tr.move||tr.type||'Transaction')+'</strong></div>').join('')+'</div>':
        '<div class="subnote">No verified completed transactions were present in the saved bounded history.</div>');
}
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
// Extra verified analysis may arrive without changing the provider roster capture.
// Never advance to an older core capture, even if enrichment is newer.
function isVerifiedAdvance(latest,previous){
 if(!previous)return true;
 const fresh=captureMs(latest?.syncedAtIso),old=captureMs(previous?.syncedAtIso);
 if(fresh>old)return true;
 if(fresh<old)return false;
 const x=captureMs(latest?.teams?.brock?.analysisAsOfIso);
 const y=captureMs(previous?.teams?.brock?.analysisAsOfIso);
 return x>y;
}
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
  if(isVerifiedAdvance(result.snapshot,existing))
    localStorage.setItem(CACHE_KEY,JSON.stringify(result.raw));
 }catch{}
 return result.snapshot;
}
function acceptNewer(latest){
 if(!latest?.teams?.brock||!Number.isFinite(captureMs(latest.syncedAtIso)))return false;
 if(!isVerifiedAdvance(latest,current))return false;
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
