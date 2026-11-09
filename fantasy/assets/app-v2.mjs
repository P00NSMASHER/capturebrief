import {TEAM_IDS,normalizeSnapshot,getFreshness,rosterBuckets,slotsFromRoster,optimizeLineup,rankWaiverTargets,estimateWinChance,isSafeUrl,round,teamPath,rosterStatusAlerts,compareScoredLineup,marketWatchlist,positionDepth} from './engine.mjs';
import {preparePrivateImport} from './snapshot-import.mjs';
import {LEAGUE_TEAMS,resolveTeam,teamLogo,uiIcon,leagueGallery,upcomingCards,teamStrip} from './league-branding.mjs';
import {buildCoachPlan,buildArchivedCoachReview} from './coach-engine.mjs';

const BASE='/capturebrief/fantasy/';
const root=document.getElementById('root');
const PRIVATE_KEY='fantasy-hq-private-v3';
const CACHE_KEY='fantasy-hq-public-last-good-v2';
let current=null,source='published',loading=false,activeTab='overview',message='',waiverFilter='ALL';
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
 const choices=[['overview','Home','home'],['lineup','Lineup','lineup'],['waivers','Players','waivers'],['lab','League','league'],['coach','Coach','coach']];
 return '<nav class="bottomnav" role="tablist" aria-label="Brock Hard sections">'+choices.map(([id,label,glyph])=>
 '<button type="button" role="tab" aria-label="'+(id==='overview'?'Overview':id==='waivers'?'Waivers':label)+'" aria-selected="'+(activeTab===id)+'" data-tab="'+id+'" class="'+(activeTab===id?'active':'')+'">'+
 uiIcon(glyph)+'<span>'+label+'</span></button>').join('')+'</nav>';
}
function masthead(team){
 const f=freshness();
 return '<header class="masthead"><div class="masttop"><a href="'+BASE+'" class="brand" aria-label="Brock Hard Fantasy HQ home">'+
 '<span class="brandmark">'+teamLogo('2','tiny')+'</span><span class="brandname">BROCK <b>HARD</b><small>FANTASY HQ · 2026</small></span></a>'+
 '<button type="button" class="refreshbtn" data-action="refresh" '+(loading?'disabled':'')+' aria-label="Check latest published Yahoo capture">'+
 uiIcon('refresh')+'<span>'+(loading?'Checking':'Refresh')+'</span></button></div>'+
 '<div class="statusrow"><span class="statusdot '+f.state+'"></span><span class="statusline">'+$esc(f.label)+'</span>'+
 '<span class="statussep">·</span><span>'+$esc(ageText(f))+'</span>'+
 '<span class="sourcelabel">'+(source==='private'?'PRIVATE CAPTURE · NOT LIVE':'PUBLISHED AUTO CAPTURE · NOT LIVE')+'</span></div></header>';
}
function riskRibbon(){
 const f=freshness(),old=f.state==='stale'||f.state==='unknown';
 const title=old?'Outdated fantasy data':'Data source notice';
 const line=old?'Archived Yahoo snapshot. Player status, waivers and decisions may have changed.':
   source==='private'?'This is a local, read-only capture; verify details with Yahoo before acting.':
   'Scores and roster details reflect the last Yahoo capture, not continuous live scoring.';
 return '<div class="riskbar '+(old?'archived':'')+'"><span class="riskicon">'+uiIcon('info')+'</span>'+
 '<div><strong>'+title+'</strong><p>'+line+'</p></div></div>';
}
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
function matchupCard(team){
 const side=scoreFor(team);
 if(!side)return section('Week '+txt(current.week)+' matchup','MATCHUP',empty('Matchup not in this capture','Check the next published Yahoo snapshot.'));
 const mine=side.mine,opp=side.opp;
 const opponent=resolveTeam(opp.teamId||opp.teamName);
 const probability=typeof mine.winProbability==='number'&&Number.isFinite(mine.winProbability)&&mine.winProbability>=0&&mine.winProbability<=1?mine.winProbability:null;
 const status=team.matchup?.status||'snapshot';
 return '<section class="panel matchup-panel"><div class="panelhead matchup-head"><div><div class="label">WEEK '+$esc(txt(current.week))+' · MATCHUP</div>'+
 '<h2>'+ (status==='final'?'Final matchup':status==='upcoming'?'Upcoming matchup':'Game week snapshot')+'</h2></div>'+
 '<span class="mini-pill">'+$esc(status.replace(/_/g,' ').toUpperCase())+'</span></div>'+
 '<div class="matchup"><div class="match-team">'+teamLogo('2','hero')+'<div class="matchlabel">YOUR TEAM</div>'+
 '<div class="matchname">'+$esc(team.short)+'</div><div class="matchscore">'+num(mine.points)+'</div>'+
 '<div class="matchproj">Yahoo pregame '+num(mine.projectedPoints,1)+'</div></div>'+
 '<div class="vs"><span>VS</span><i></i></div>'+
 '<div class="match-team against">'+teamLogo(opponent?.id,'hero')+'<div class="matchlabel">OPPONENT</div>'+
 '<div class="matchname">'+$esc(opp.teamName||opp.name||'Opponent')+'</div>'+
 '<div class="matchscore">'+num(opp.points)+'</div>'+
 '<div class="matchproj">Yahoo pregame '+num(opp.projectedPoints,1)+'</div></div></div>'+
 (probability===null?'':'<div class="probability"><div class="probability-copy"><strong>Win chance at capture</strong><b>'+num(probability*100,0)+'%</b></div>'+
 '<div class="probability-track" role="progressbar" aria-label="Yahoo win probability at capture" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+Math.round(probability*100)+'"><span style="width:'+Math.round(probability*100)+'%"></span></div>'+
 '<p>Yahoo estimate · not a live forecast</p></div>')+'</section>';
}
function controls(){return '<p class="controlcopy">Import a new Brock Hard JSON capture from your connected Flaim Fantasy conversation. Your file stays in this browser; this page does not contact Yahoo.</p>'+
  '<div class="controlrow"><button type="button" class="primarybutton" data-action="import">↥ Import updated Yahoo snapshot</button>'+
  (source==='private'?'<button type="button" class="minorbtn button" data-action="clear">Remove local capture</button>':'')+'</div>'+
  '<input id="importFile" type="file" accept=".json,application/json" hidden>'+
  '<div class="subnote">The capture is read-only and manual. This button imports a file; it is not a live Yahoo sync. Failed imports preserve your existing data.</div>'}
function stats(team){
 const flags=rosterStatusAlerts(team.roster).length;
 const val=(a,b,extra)=>'<div class="metric"><div class="metriclabel">'+a+'</div><div class="metricvalue">'+$esc(b)+'</div>'+
 (extra?'<div class="metricextra">'+extra+'</div>':'')+'</div>';
 return '<section class="metrics" aria-label="Team standings and availability">'+val('RECORD',txt(team.record),'Season record')+
 val('LEAGUE RANK',txt(team.rank),'League of eight')+val('WAIVER PRIORITY',txt(team.waiver),'Yahoo queue')+
 val('ROSTER FLAGS',String(flags),'At last capture')+'</section>';
}
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
 const derived=rosterStatusAlerts(team.roster),manual=Array.isArray(team.alerts)?team.alerts:[];
 const alerts=[...derived,...manual];
 const rows=alerts.length?'<div class="alert-grid">'+alerts.map(a=>
 '<div class="alertrow"><span class="status-chip '+(a.level==='urgent'?'urgent':'watch')+'">'+$esc(a.status||'!')+'</span>'+
 '<div><strong>'+$esc(a.name||a.title||'Roster status')+'</strong>'+
 '<p>'+$esc((a.status||'Status')+' · '+(a.slot||'Roster')+' at capture')+'</p></div></div>').join('')+'</div>':
 '<div class="quiet-empty">No player-status flags reported in this capture; verify current health on Yahoo.</div>';
 return section('Player status','YAHOO ROSTER · '+derived.length+' FLAGS',rows,
 '<button type="button" class="text-link" data-tab="lineup">See lineup '+uiIcon('arrow')+'</button>');
}
function strategy(team){const s=team.strategy;if(!s)return '';
  return section('Saved analysis','EXPLANATION',
    '<p class="bodycopy">'+$esc(s.summary||'')+'</p>'+
    '<div class="strategygrid">'+(s.bullets||[]).map(b=>'<div><span>'+$esc(b.label||'')+'</span><p>'+$esc(b.text||'')+'</p></div>').join('')+'</div>');}
function overviewQuickPanels(team){
 const market=marketWatchlist(team.availablePlayers,3);
 const choices=market.length?market.map(p=>
 '<div class="preview-player"><span class="player-avatar pos-'+$esc(p.position)+'">'+$esc(p.position)+'</span>'+
 '<div><strong>'+$esc(p.name)+'</strong><small>'+$esc(p.team||'NFL')+' · '+$esc(p.acquisitionState==='waivers'?'Waivers':'Free agent')+'</small></div>'+
 '<span class="market-number">'+num(p.percentOwned,0)+'%<small>Yahoo</small></span></div>').join(''):
 '<div class="quiet-empty">No verified available players at capture.</div>';
 return '<div class="home-columns"><section class="panel compact-panel"><div class="panelhead"><div><div class="label">LOOKING AHEAD</div><h2>Coming up</h2></div>'+
 '<button class="text-link" type="button" data-tab="lab">League '+uiIcon('arrow')+'</button></div>'+
 upcomingCards(team,current.week)+'</section>'+
 '<section class="panel compact-panel"><div class="panelhead"><div><div class="label">AVAILABLE AT CAPTURE</div><h2>On the radar</h2></div>'+
 '<button class="text-link" type="button" data-tab="waivers">All players '+uiIcon('arrow')+'</button></div>'+
 '<div class="preview-list">'+choices+'</div><p class="caption-note">Ranked by Yahoo-wide roster rate, not projected performance.</p></section></div>';
}
function summaryView(team){
 return matchupCard(team)+stats(team)+overviewQuickPanels(team)+alertList(team)+
 '<details class="small-disclosure"><summary>Capture details '+uiIcon('chevron')+'</summary>'+decision(team)+'</details>'+strategy(team);
}
function playerRow(p){
 const injury=p.injury?badge(p.injury,'bad'):'';
 const projected=typeof p.projection==='number'&&teamProjectionSupported();
 const scored=typeof p.actualPoints==='number'&&Number.isFinite(p.actualPoints);
 const points=projected?num(p.projection,2)+'<small>PROJ.</small>':scored?num(p.actualPoints,2)+'<small>PTS</small>':'—';
 return '<div class="playerrow"><span class="slot">'+$esc(txt(p.slot,'—'))+'</span>'+
 '<span class="player-avatar pos-'+$esc(p.position||'UN')+'">'+$esc(p.position||'NFL')+'</span>'+
 '<div class="playername"><strong>'+$esc(p.name)+'</strong><small>'+$esc([p.nflTeam,p.position].filter(Boolean).join(' · '))+'</small></div>'+
 injury+'<span class="proj">'+points+'</span></div>';
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
 const all=Array.isArray(team.availablePlayers)?team.availablePlayers:[];
 const positions=['ALL','QB','RB','WR','TE','K','DEF'];
 const filtered=waiverFilter==='ALL'?all:all.filter(p=>String(p.position).toUpperCase()===waiverFilter);
 const filters='<div class="filterbar" role="group" aria-label="Filter by player position">'+positions.map(pos=>
 '<button type="button" data-filter="'+pos+'" aria-pressed="'+(waiverFilter===pos)+'" class="'+(waiverFilter===pos?'chosen':'')+'">'+(pos==='ALL'?'All':pos)+'</button>').join('')+'</div>';
 const rows=filtered.map(p=>{
  const status=p.acquisitionState==='free_agent'?'FREE AGENT':p.acquisitionState==='waivers'?'WAIVERS':'UNKNOWN';
  const owned=Number.isFinite(p.percentOwned)?num(p.percentOwned,0)+'%':'—';
  return '<div class="playerrow available-row"><span class="player-avatar pos-'+$esc(p.position||'NFL')+'">'+$esc(p.position||'NFL')+'</span>'+
  '<div class="playername"><strong>'+$esc(p.name||'Unknown')+'</strong><small>'+$esc(p.team||'NFL')+' · '+status+
  (p.waiverDate?' · '+$esc(p.waiverDate):'')+'</small></div>'+
  '<span class="market-number">'+owned+'<small>rostered</small></span></div>';
 }).join('');
 const spotlight=market.map((p,i)=>'<div class="preview-player"><span class="scout-rank">'+(i+1)+'</span>'+
 '<span class="player-avatar pos-'+$esc(p.position)+'">'+$esc(p.position)+'</span><div><strong>'+$esc(p.name)+'</strong>'+
 '<small>'+$esc(p.team||'NFL')+' · '+$esc(p.acquisitionState==='waivers'?'On waivers':'Free agent')+'</small></div>'+
 '<span class="market-number">'+num(p.percentOwned,0)+'%<small>Yahoo</small></span></div>').join('');
 const depth=positionDepth(team.roster);
 const depthRows=depth.map(d=>'<div class="depth-item"><strong>'+d.position+'</strong><div class="depth-rail"><span style="width:'+Math.round(d.total/8*100)+'%"></span></div>'+
 '<b>'+d.total+'</b></div>').join('');
 const decision=rated.available?(rated.recommendations.length?
 '<div class="list">'+rated.recommendations.map(p=>'<div class="waiverrow"><strong>'+$esc(p.add)+'</strong><small>Drop '+$esc(p.drop)+' · +'+num(p.improvement,2)+' proj. pts</small></div>').join('')+'</div>':
 '<p class="caption-note">No positive projected upgrade from verified candidates.</p>'):
 '<p class="caption-note">Yahoo does not provide complete player-level forward projections in this capture. This list uses market roster rate only—not add/drop improvement.</p>';
 return '<div class="tab-intro"><span class="eyebrow">YOUR FREE-AGENT BOARD</span><h1>Find your next pickup.</h1>'+
 '<p>'+all.length+' players available in this league at the last Yahoo capture.</p></div>'+
 section('Most rostered available','YAHOO MARKET · NOT A RECOMMENDATION',
 spotlight?'<div class="preview-list">'+spotlight+'</div>':'<div class="quiet-empty">Availability was not captured.</div>')+
 section('Player pool',''+filtered.length+' MATCH'+(filtered.length===1?'':'ES'),
 filters+(rows?'<div class="list">'+rows+'</div>':'<div class="quiet-empty">No '+$esc(waiverFilter)+' players in this capture.</div>'))+
 '<div class="home-columns"><section class="panel compact-panel"><div class="panelhead"><div><div class="label">ROSTER FIT</div><h2>Your position depth</h2></div></div>'+
 '<div class="depth-list">'+depthRows+'</div></section>'+
 '<section class="panel compact-panel"><div class="panelhead"><div><div class="label">DECISION SUPPORT</div><h2>Projected upgrade</h2></div></div>'+
 decision+'</section></div>'+
 '<p class="footnote">Yahoo roster rates are platform-wide, not your league’s ownership %. Waiver dates are calendar days, not guaranteed clearance times. This app never adds or drops players.</p>';
}
function labView(team){
 const m=team.matchupModel||null;
 const chance=m&&freshness().actionable?estimateWinChance(m.myProjected,m.oppProjected,m.mySigma,m.oppSigma):null;
 const side=scoreFor(team);
 const providerChance=freshness().actionable&&typeof side?.mine?.winProbability==='number'?side.mine.winProbability*100:null;
 const facts=team.standings&&typeof team.standings==='object'?team.standings:{};
 const stat=(label,value)=>'<div class="league-stat"><span>'+label+'</span><strong>'+$esc(String(value))+'</strong></div>';
 const standings='<div class="league-standings"><div class="league-standings-head">'+teamLogo('2','lg')+
 '<div><span>YOUR STANDING</span><strong>'+ $esc(team.name) +'</strong><small>'+ $esc(txt(team.record)) +' · '+$esc(txt(team.rank))+'</small></div></div>'+
 '<div class="league-stats">'+stat('POINTS FOR',Number.isFinite(facts.pointsFor)?num(facts.pointsFor,1):'—')+
 stat('POINTS AGAINST',Number.isFinite(facts.pointsAgainst)?num(facts.pointsAgainst,1):'—')+
 stat('WAIVER',txt(team.waiver))+'</div></div>';
 const depth=positionDepth(team.roster);
 const depthRows=depth.map(d=>'<div class="depth-item"><strong>'+$esc(d.position)+'</strong>'+
 '<div class="depth-rail"><span style="width:'+Math.round(d.total/8*100)+'%"></span></div><b>'+d.total+'</b></div>').join('');
 const transactions=Array.isArray(team.transactions)?team.transactions.slice(0,12):[];
 const recent=transactions.length?'<div class="activity-feed">'+transactions.map(tr=>
 '<div class="activity"><span class="activity-bullet"></span><div><strong>'+$esc(tr.move||tr.type||'Transaction')+'</strong>'+
 '<span>'+$esc(txt(tr.date,'Date unavailable'))+'</span></div></div>').join('')+'</div>':
 '<div class="quiet-empty">No completed moves found in the bounded capture.</div>';
 const chanceCard=providerChance!==null?'<div class="winprob">'+num(providerChance,1)+'<small>% YAHOO WIN ESTIMATE AT CAPTURE</small></div>':
 chance!==null?'<div class="winprob">'+num(chance,1)+'<small>% MODEL ESTIMATE</small></div>':
 '<p class="caption-note">No verified win probability is present for this matchup.</p>';
 return '<div class="tab-intro"><span class="eyebrow">YOUR FANTASY LEAGUE</span><h1>The League.</h1><p>Eight clubs. One trophy. Your view is Brock Hard only.</p></div>'+
 leagueGallery()+
 section('Playoff race','YOUR VERIFIED POSITION',standings+
 '<p class="caption-note">This is Brock Hard’s Yahoo standing—not an estimated final playoff position. Other teams’ records were not included in the public Brock-only capture.</p>')+
 section('Next three matchups','YAHOO TEAM FORECASTS',upcomingCards(team,current.week)+
 '<p class="caption-note">Team pregame projections, not final scores or modeled playoff odds.</p>')+
 '<div class="home-columns"><section class="panel compact-panel"><div class="panelhead"><div><div class="label">YOUR TEAM</div><h2>Trade preparation</h2></div></div>'+
 '<div class="depth-list">'+depthRows+'</div><p class="caption-note">Roster depth, not player trade valuations.</p></section>'+
 '<section class="panel compact-panel"><div class="panelhead"><div><div class="label">AT CAPTURE</div><h2>Matchup forecast</h2></div></div>'+
 chanceCard+'<p class="caption-note">No individual player projections were supplied.</p></section></div>'+
 section('Recent Brock Hard activity','COMPLETED MOVES · BOUNDED',recent);
}
function tabbar(){return '<div class="tabs" role="tablist" aria-label="Team dashboard views">'+[
  ['overview','Overview'],['lineup','Lineup'],['waivers','Waivers'],['lab','Analysis']].map(([id,label])=>
   '<button type="button" role="tab" aria-selected="'+(id===activeTab)+'" class="'+(id===activeTab?'active':'')+'" data-tab="'+id+'">'+label+'</button>').join('')+'</div>';}

function coachAction(item){
 if(!item?.actionTab||!['overview','lineup','waivers','lab'].includes(item.actionTab))return '';
 return '<button type="button" class="coach-action" data-tab="'+item.actionTab+'"'+
 (item.filter==='QB'&&item.actionTab==='waivers'?' data-coach-filter="QB"':'')+'>'+
 $esc(item.actionLabel||'Review')+uiIcon('arrow')+'</button>';
}
function coachInsight(item){
 const tone=['priority','attention'].includes(item.tone)?item.tone:'neutral';
 return '<article class="coach-insight coach-insight--'+tone+'">'+
 '<div class="coach-insight-head"><span class="coach-signal coach-signal--'+tone+'">'+
 (tone==='priority'?'PRIORITY':tone==='attention'?'WATCH':'SOURCE-BACKED')+'</span></div>'+
 '<h3>'+$esc(item.title)+'</h3>'+
 '<ul class="coach-points">'+(Array.isArray(item.bullets)?item.bullets:[]).map(line=>
 '<li>'+$esc(line)+'</li>').join('')+'</ul>'+
 '<div class="coach-evidence"><span>'+uiIcon('info')+$esc(item.evidence)+'</span>'+coachAction(item)+'</div></article>';
}
function coachAssessment(summary,capture,archived=false){
 if(!Array.isArray(summary)||summary.length!==3)return '';
 return '<section class="panel coach-assessment'+(archived?' coach-assessment--archived':'')+'" aria-labelledby="coach-assessment-title">'+
 '<div class="panelhead"><div><div class="label">'+
 (archived?'LAST VERIFIED CAPTURE · ARCHIVED REVIEW':'THE BIG PICTURE · MANAGER’S DESK')+'</div>'+
 '<h2 id="coach-assessment-title">'+(archived?'Coach’s saved assessment':'Coach’s final assessment')+'</h2></div>'+
 '<span class="mini-pill">3-PARAGRAPH RECAP</span></div>'+
 '<div class="coach-recap">'+summary.map((paragraph,i)=>
 '<p class="coach-recap-paragraph" data-recap-index="'+(i+1)+'">'+$esc(paragraph)+'</p>').join('')+'</div>'+
 '<div class="coach-recap-source">'+uiIcon('info')+
 '<span>Based on the saved Week '+$esc(String(current.week))+' Yahoo capture · '+$esc(String(capture))+
 (archived?'. Historical review only: old availability and player statuses are NOT current and no moves are recommended.':
 '. Recheck Yahoo before acting; this is not live analysis.')+'</span></div></section>';
}

function coachView(team){
 const plan=buildCoachPlan(current,{now:Date.now()});
 if(!plan.ready){
  const saved=plan.status==='archived'?buildArchivedCoachReview(current):null;
  return '<div class="tab-intro"><span class="eyebrow">FANTASY HQ · COACH</span>'+
  '<h1>Coach needs a fresh capture.</h1></div>'+
  '<section class="panel coach-unverified"><p>'+$esc(plan.subtitle)+'</p>'+
  '<button class="primarybutton" type="button" data-action="refresh">'+uiIcon('refresh')+
  ' Check published snapshot</button></section>'+
  (saved?coachAssessment(saved.summary,saved.captureAt,true):'');
 }
 const priority=plan.priorities||[];
 const metrics=plan.metrics.map(m=>'<div class="coach-metric"><span>'+$esc(m.label)+'</span><strong>'+$esc(m.value)+'</strong></div>').join('');
 const next=priority.map((c,i)=>'<article class="coach-step"><span class="coach-step-number">'+String(i+1)+'</span>'+
 '<div><strong>'+$esc(c.title)+'</strong><p>'+$esc(c.evidence)+'</p></div>'+coachAction(c)+'</article>').join('');
 const categories=[
  ['lineup','Lineup decisions','YOUR STARTERS'],
  ['waivers','Waiver targets','LEAGUE-AVAILABLE PLAYERS'],
  ['trades','Trade strategy','VALUE BEFORE VOLUME'],
  ['playoffs','Playoff preparation','ROAD AHEAD'],
  ['league','League insights','THE STANDINGS']
 ];
 const areas=categories.map(([id,label,kicker])=>{
  const cards=Array.isArray(plan.sections[id])?plan.sections[id]:[];
  return '<section class="panel coach-section" id="coach-'+id+'"><div class="panelhead"><div><div class="label">'+kicker+'</div>'+
   '<h2>'+label+'</h2></div><span class="mini-pill">'+cards.length+' CHECK'+(cards.length===1?'':'S')+'</span></div>'+
   '<div class="coach-insights">'+cards.map(coachInsight).join('')+'</div></section>';
 }).join('');
 return '<div class="tab-intro coach-intro"><span class="eyebrow">BROCK HARD · FANTASY COACH</span>'+
 '<h1>Your game plan.</h1><p>Manager-style insights from your saved Yahoo data. Clear next steps, no invented player projections.</p></div>'+
 '<section class="coach-hero"><div class="coach-hero-top"><span class="coach-orb">'+uiIcon('coach')+'</span>'+
 '<span class="coach-source">YAHOO SNAPSHOT · READ-ONLY</span></div><div class="coach-hero-kicker">COACH’S TOP CALL</div>'+
 '<h2>'+$esc(plan.headline)+'</h2><p>'+$esc(plan.subtitle)+'</p>'+
 '<div class="coach-hero-action">'+coachAction(priority[0])+'</div>'+
 '<div class="coach-hero-metrics">'+metrics+'</div></section>'+
 '<section class="panel coach-next"><div class="panelhead"><div><div class="label">PRIORITIZED FOR BROCK HARD</div>'+
 '<h2>Your next three checks</h2></div></div><div class="coach-steps">'+next+'</div></section>'+
 '<div class="coach-section-grid">'+areas+'</div>'+
 coachAssessment(plan.summary,plan.captureAt)+
 '<p class="coach-footer">Snapshot-based advice only. No player transactions, trade proposals, or Yahoo lineup edits are made by Coach.</p>';
}
function teamView(team){
 const view=activeTab==='coach'?coachView(team):activeTab==='lineup'?lineupView(team):activeTab==='waivers'?waiverView(team):activeTab==='lab'?labView(team):summaryView(team);
 const home=activeTab==='overview';
 const lead=home?
 '<div class="teamhero '+$esc(team.accent)+'"><div class="hero-copy"><span class="eyebrow">BROCK HARD · YAHOO FOOTBALL</span>'+
 '<h1>'+$esc(team.name)+'</h1><div class="herosub"><span class="record-pill">'+$esc(txt(team.record))+'</span>'+
 '<span>Season '+current.season+' · Week '+txt(current.week)+'</span></div></div>'+
 '<div class="hero-crest">'+teamLogo('2','display')+'</div></div>'+
 riskRibbon()+
 '<div class="heroactions">'+teamStrip(team,current.week)+safeLeagueLink(team)+'</div>':
 '<div class="subpage-context">'+teamLogo('2','sm')+
 '<div><strong>Brock Hard</strong><span>Week '+$esc(txt(current.week))+' · '+$esc(txt(team.record))+' · Read-only Yahoo snapshot</span></div>'+
 safeLeagueLink(team)+'</div>';
 return '<div class="container">'+masthead(team)+messageBox()+lead+
 '<main id="tabPanel" role="tabpanel" aria-label="'+$esc(activeTab)+'">'+view+'</main>'+
 '<details class="settings-panel"><summary>'+uiIcon('info')+' Data & snapshot settings '+uiIcon('chevron')+'</summary>'+
 section('Data controls','PRESERVE YOUR SNAPSHOT',controls())+'</details>'+
 '<div class="footnote legal-footer">Fantasy HQ is read-only. No lineup submissions, transactions or claims happen here.</div></div>'+nav();
}

function archivedView(){
 const date=Number.isFinite(Date.parse(current?.syncedAtIso))?
 new Date(current.syncedAtIso).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'unknown date';
 const t=current?.teams?.brock;
 const savedReport=activeTab==='coach'?buildArchivedCoachReview(current):null;
 return '<div class="container">'+masthead(t)+messageBox()+
 '<section class="archived-fallback panel"><div class="archive-logo">'+teamLogo('2','display')+'</div>'+
 '<div class="label">BROCK HARD · NO CURRENT CAPTURE</div><h1>Update your Yahoo data</h1>'+
 '<p><strong>Outdated fantasy data.</strong> Your Week '+$esc(txt(current?.week))+' capture from '+$esc(date)+
 ' is archived. Older results are intentionally withheld from current-decision views.</p>'+
 '<button type="button" class="primarybutton" data-action="refresh">'+uiIcon('refresh')+' Check published snapshot</button>'+
 '<details class="small-disclosure"><summary>Import a saved capture '+uiIcon('chevron')+'</summary>'+
 '<button type="button" class="minorbtn" data-action="import">↥ Import updated Yahoo snapshot</button></details>'+
 '<input id="importFile" type="file" accept=".json,application/json" hidden>'+
 '</section>'+(savedReport?coachAssessment(savedReport.summary,savedReport.captureAt,true):'')+
 '<p class="footnote">No Yahoo credentials or live provider access are used by this page.</p></div>'+nav();
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
 if(tab){activeTab=tab.dataset.tab;location.hash=activeTab;waiverFilter=tab.dataset.coachFilter==='QB'&&activeTab==='waivers'?'QB':'ALL';render();window.scrollTo({top:0,behavior:'instant'});return}
 const chip=event.target.closest('button[data-filter]');
 if(chip){waiverFilter=chip.dataset.filter;render();return}
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
 if(['overview','lineup','waivers','lab','coach'].includes(hash))activeTab=hash;
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
