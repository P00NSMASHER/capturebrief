/* Edge War Room: client presentation of verified, separately published model data. */
import {uiIcon,teamLogo,resolveTeam} from './league-branding.mjs';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const num=(v,d=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'—';
const status=(v)=>['critical','priority','attention','watch'].includes(v)?v:'watch';
function block(title,kicker,html,extra=''){
 return '<section class="edge-card"><div class="edge-card-heading"><div><span class="edge-eyebrow">'+esc(kicker)+'</span>'+
 '<h2>'+esc(title)+'</h2></div>'+extra+'</div>'+html+'</section>';
}
function button(label,scope){
 return '<button type="button" class="edge-button" data-edge-jump="'+esc(scope)+'">'+esc(label)+uiIcon('arrow')+'</button>';
}
function notice(model){
 return '<div class="edge-provenance"><span class="edge-indicator"></span>'+
 '<span>2026 WEEK '+model.modelWeek+' · FANTASYBOT PPR MODEL · '+num(model.modelAgeHours,1)+'h ago</span>'+
 '<span class="edge-method" aria-label="Illustrative forecasts, not Yahoo-confirmed scores">EXPERIMENTAL</span></div>';
}
function lineups(model){
 const v=model.lineup;
 const options=[
  ['safe','Cautious','Prefer lower-volatility players'],
  ['balanced','Balanced','Maximize projected points'],
  ['upside','Upside','Lean toward higher-scoring ranges']
 ];
 const risk='<div class="edge-mode" role="group" aria-label="Choose projection risk strategy">'+
 options.map(([id,label,desc])=>'<button type="button" class="'+(model.mode===id?'selected':'')+
 '" data-edge-mode="'+id+'" aria-pressed="'+(model.mode===id)+'" title="'+esc(desc)+'">'+label+'</button>').join('')+
 '</div>';
 if(!v?.available){
  const missing=model.roster.filter(p=>p.forecast===null&&!['IR','IR+','NA','TAXI'].includes(p.slot));
  return block('Projected lineup','MODEL COVERAGE',risk+
    '<div class="edge-no-data"><strong>Lineup optimization withheld.</strong><p>'+
    esc(v?.reason||'Full eligible-player projections unavailable.')+'</p>'+
    (missing.length?'<p>Missing: '+esc(missing.map(p=>p.name).join(', '))+'</p>':'')+
    '</div>');
 }
 const ins=v.inPlayers.map(p=>'<span class="edge-move-player edge-move-player--in">'+esc(p.name)+' <small>IN</small></span>').join('');
 const outs=v.outPlayers.map(p=>'<span class="edge-move-player edge-move-player--out">'+esc(p.name)+' <small>OUT</small></span>').join('');
 const swap=(v.inPlayers.length||v.outPlayers.length)?
 '<div class="edge-swap"><div class="edge-swap-label">MODEL LINEUP CHANGES</div><div class="edge-move-list">'+
 (outs||'<span class="edge-muted">No bench exits</span>')+uiIcon('arrow')+(ins||'<span class="edge-muted">No bench additions</span>')+
 '</div><p>Verify player availability, game-day locks, and Yahoo’s actual roster rules before changing anything.</p></div>':
 '<div class="edge-swap"><strong>The projected top-scoring lineup already matches your starters.</strong>'+
 '<p>Do not manufacture a swap when the forecast difference is negligible.</p></div>';
 const rows=v.assignments.map(p=>'<div class="edge-proj-row"><div class="edge-proj-slot">'+esc(p.slot)+'</div>'+
 '<div class="edge-proj-name"><strong>'+esc(p.name)+'</strong><small>'+esc(p.position)+
 (p.bye?' · BYE':'')+'</small></div>'+
 '<div class="edge-proj-value"><strong>'+num(p.forecast,1)+'</strong><small>projected</small></div></div>').join('');
 const opponent=model.opponents.find(x=>x.week===model.modelWeek);
 const predicted= model.illustrativeChance!==null?
 '<details class="edge-assumptions"><summary>Experimental win-likelihood scenario '+uiIcon('chevron')+'</summary>'+
 '<strong>'+num(model.illustrativeChance.value,0)+'% model illustration</strong>'+
 '<p>'+esc(model.illustrativeChance.assumptions)+'</p></details>':'';
 return block('Week '+model.modelWeek+' lineup lab','PLAYER-LEVEL FORECASTS',risk+
 '<div class="edge-three-metrics"><div><span>YOUR SAVED LINEUP</span><strong>'+num(v.currentScore,1)+'</strong><small>model pts</small></div>'+
 '<div><span>MODELED BEST</span><strong>'+num(v.mean,1)+'</strong><small>expected pts</small></div>'+
 '<div class="edge-uplift"><span>POTENTIAL CHANGE</span><strong>'+((v.gain||0)>0?'+':'')+num(v.gain,1)+'</strong><small>pts · modeled</small></div></div>'+
 swap+
 '<details class="edge-roster-details"><summary>View all '+v.assignments.length+' projected starters '+uiIcon('chevron')+'</summary>'+
 '<div class="edge-proj-list">'+rows+'</div></details>'+
 '<div class="edge-range"><div><span>MODELED SCENARIO BAND</span>'+
 '<strong>'+num(v.illustrativeLow,0)+'–'+num(v.illustrativeHigh,0)+' pts</strong></div>'+
 '<p>Illustrative one-standard-deviation spread from limited recent games, not a calibrated probability interval.</p></div>'+
 (opponent?'<p class="edge-context">Yahoo’s separate Week '+model.modelWeek+' forecast for '+esc(opponent.teamName)+
 ': '+num(opponent.yahooOppProjected,1)+' points. Not directly interchangeable with FantasyBot PPR projections.</p>':'')+
 predicted);
}
function waivers(model){
 const p=model.waivers;
 if(model.quality?.yahooFresh===false)
  return block('Waiver decisions on hold','CURRENT YAHOO INVENTORY NOT VERIFIED',
   '<div class="edge-no-data"><strong>Forward-looking research remains available, but no pickup is rated.</strong>'+
   '<p>The last Yahoo available-player capture is '+num(model.quality.yahooAgeHours,1)+
   ' hours old. The model uses a separately reverified FantasyBot roster for hypothetical lineup research only. Recheck Yahoo before any add, drop or claim.</p></div>'+
   button('View last saved player pool','players'));
 const upside=p.positive.slice(0,5).map(row=>'<article class="edge-waiver-row">'+
 '<div class="edge-waiver-position">'+esc(row.add.position)+'</div><div class="edge-waiver-identity"><strong>'+
 esc(row.add.name)+'</strong><small>Evaluate replacing '+esc(row.drop.name)+'</small><small>'+
 esc(row.availability==='waivers'?'On waivers at capture':'Free agent at capture')+'</small></div>'+
 '<div class="edge-waiver-impact"><strong>+'+num(row.projectedWeeklyUplift,1)+'</strong><small>modeled pts</small></div></article>').join('');
 const scout=p.watches.slice(0,8).map(row=>'<article class="edge-watch-row"><div class="edge-waiver-position">'+
 esc(row.position)+'</div><div class="edge-waiver-identity"><strong>'+esc(row.name)+'</strong><small>'+
 esc(row.availability==='waivers'?'Waivers':'Free agent')+' · model rank '+esc(row.rank||'—')+'</small></div>'+
 '<div class="edge-waiver-impact"><strong>'+num(row.forecast,1)+'</strong><small>Week '+model.modelWeek+' pts</small></div></article>').join('');
 return block('Waiver opportunities','YAHOO-VERIFIED AVAILABILITY · FANTASYBOT VALUE',
 '<div class="edge-brief"><strong>'+p.covered+' of '+p.total+' available players have verified forward forecasts.</strong>'+
 '<p>These are the only names ranked with model points. A player missing from the model is not assumed healthy or worthless.</p></div>'+
 (upside?'<div class="edge-list-subtitle">POTENTIAL ONE-WEEK LINEUP UPGRADES</div><div class="edge-waiver-list">'+upside+'</div>':
 '<div class="edge-no-data"><strong>No proven one-week starting upgrade in the captured pool.</strong>'+
 '<p>Use waiver priority for depth and future holes, not a meaningless shuffle.</p></div>')+
 '<div class="edge-list-subtitle">WORTH SCOUTING</div><div class="edge-watch-list">'+scout+'</div>'+
 '<p class="edge-context">These are hypotheses to check in Yahoo, not add/drop orders. League waiver prices, lock rules and future availability may differ.</p>'+
 button('Compare all available players','players'));
}
function byes(model){
 if(!model.byes.length)return block('Bye-week resilience','2026 OFFICIAL NFL SCHEDULE',
 '<p class="edge-context">No remaining byes for this roster were verified.</p>');
 const rows=model.byes.map(row=>{
  const shortages=row.shortages.map(s=>s.available===0?
   'No active '+s.position+' option':'Only '+s.available+' '+s.position+' for '+s.required+' required').join('; ');
  return '<article class="edge-bye-row edge-bye-row--'+status(row.priority)+'">'+
   '<div class="edge-bye-week"><span>WEEK</span><b>'+row.week+'</b></div>'+
   '<div class="edge-bye-content"><strong>'+esc(row.players.map(p=>p.name).join(' · '))+'</strong>'+
   '<small>'+esc(row.players.map(p=>p.position).join(', '))+'</small>'+
   (shortages?'<span class="edge-bye-warning">'+uiIcon('info')+esc(shortages)+'</span>':'')+'</div>'+
   '<span class="edge-bye-chip">'+(shortages?'COVERAGE GAP':row.startingCount?'STARTER BYE':'BENCH BYE')+'</span>'+
   '</article>';
 }).join('');
 return block('Beat the bye weeks','LOOK AHEAD · OFFICIAL NFL SCHEDULE',
 '<p class="edge-context">The best waiver move sometimes prevents a Week 13 lineup emergency instead of adding Week 10 points.</p>'+
 '<div class="edge-bye-list">'+rows+'</div>'+
 '<p class="edge-context">NFL bye source: <a href="https://www.nfl.com/news/2026-nfl-schedule-release-every-team-bye-week" target="_blank" rel="noopener noreferrer">official 2026 bye schedule</a>.</p>');
}
function tradeLeverage(model){
 const teWeek=model.byes.find(x=>x.week===13&&x.shortages.some(g=>g.position==='TE'&&g.available===0));
 const benchReceivers=model.roster.filter(p=>['BN','BE','BENCH'].includes(p.slot)&&p.position==='WR'&&
  Number.isFinite(p.forecast)).sort((a,b)=>b.forecast-a.forecast);
 const benches=benchReceivers.slice(0,3).map(p=>p.name).join(', ');
 const cards=[
  {title:teWeek?'Trade or add for a Week 13 TE':'Trade to solve a persistent starting-position weakness',
   copy:teWeek?'Bowers and Andrews share their Week 13 bye. A healthy tight end whose bye is NOT Week 13 is a specific roster need. Check Yahoo free agents before paying a trade premium.':
    'Compare available players and opponent roster depth before giving up a strong starter for a one-week matchup edge.'},
  {title:'Explore bench depth as negotiation leverage',
   copy:benches?'Your captured bench includes '+benches+'. This is an inventory of possible negotiation pieces, not a recommendation to trade any of them without comparable rest-of-season value.':
   'Player trade value cannot be estimated from a single week. Protect your regular starters and check other managers’ actual needs.'},
  {title:'Do not confuse weekly forecast gain with trade value',
   copy:'One-week PPR predictions do not measure playoff value, bye fit, injury probability, or an opponent’s needs. A fair trade requires independent rest-of-season values and the other side’s verified roster.'}
 ];
 const rows=cards.map((x,i)=>'<article class="edge-trade-row"><span class="edge-trade-index">'+(i+1)+'</span>'+
 '<div><strong>'+esc(x.title)+'</strong><p>'+esc(x.copy)+'</p></div></article>').join('');
 return block('Trade leverage','STRATEGY · NO FABRICATED OFFERS',
 '<div class="edge-trade-list">'+rows+'</div><div class="edge-context">No trades were proposed or executed. These are roster-planning hypotheses, not a completed market-value analysis.</div>'+
 button('Check available roster options','players'));
}

function opponents(model){
 const next=model.opponents.slice(0,3).map(x=>{
  const org=resolveTeam(x.teamName);
  return '<div class="edge-rival-row">'+teamLogo(org?.id,'sm')+
    '<div><small>WEEK '+x.week+' · FANTASYBOT POWER</small><strong>'+esc(x.teamName)+'</strong>'+
    '<span>'+(x.rank===null?'Rating unavailable':'#'+x.rank+' of 8 · rating '+num(x.rating,0)+'/100')+'</span></div>'+
    '<div class="edge-rival-projection"><strong>'+num(x.yahooOppProjected,1)+'</strong><span>Yahoo proj.</span></div></div>';
 }).join('');
 return block('Opponent scouting','POWER RANKS · NOT JUST RECORDS',
 '<div class="edge-brief"><strong>Brock Hard: #'+esc(model.powerRank??'—')+' of 8 in FantasyBot power ratings.</strong>'+
 '<p>A low standings seed does not necessarily mean a weak roster. Scout each opponent’s power rank before deciding how much upside to chase.</p></div>'+
 '<div class="edge-rival-list">'+next+'</div>'+
 '<p class="edge-context">Ratings are FantasyBot’s relative estimates and not calibrated victory percentages.</p>');
}
function recommendations(model){
 const cards=(model.priorities||[]).map((x,i)=>'<article class="edge-rec edge-rec--'+status(x.severity)+'">'+
 '<div class="edge-rec-number">'+(i+1)+'</div><div><span class="edge-rec-tag">'+
 esc(x.severity.toUpperCase())+'</span><h3>'+esc(x.title)+'</h3>'+
 '<ul><li>'+esc(x.detail)+'</li><li class="edge-evidence">'+esc(x.evidence)+'</li></ul></div></article>').join('');
 return block('What I would do first','YOUR AI GAME PLAN',
 '<div class="edge-priorities">'+cards+'</div>');
}
function briefing(model){
 const l=model.lineups.balanced;
 const top=model.priorities||[];
 const w13=model.byes.find(x=>x.week===13&&x.shortages.some(s=>s.position==='TE'&&s.available===0));
 const opp=model.opponents.find(x=>x.week===12),rival=model.opponents.find(x=>x.week===model.modelWeek);
 const record='6–2'; // Display alongside the current, independently sourced Yahoo standings, not a predicted result.
 const first='Brock Hard has the top FantasyBot power rating in its eight-team league, but this is a modeling signal, not a title guarantee. '+
  (l?.available?'For Week '+model.modelWeek+', the model projects '+num(l.mean,1)+' FantasyBot PPR points from its highest-scoring legal-slot combination, with '+
    num(l.gain,1)+' projected points of lineup improvement relative to the captured starters. ':
    'A complete Week '+model.modelWeek+' lineup forecast is not available. ')+
  'The first strategic decision is not cosmetic: Denver has a Week '+model.modelWeek+' bye, so Jonah Coleman cannot supply starting RB points.';
 const second='I would treat waiver priority as a resource, not an obligation to make a claim. '+
  (model.quality?.yahooFresh===false?'The Yahoo available-player inventory is old, so I would not assume any saved pickup is still claimable. ':
   model.waivers.positive.length?'The current matched Yahoo player pool offers at least one positive one-week projected lineup experiment. ':
   'The matched Yahoo waiver pool does not yet produce a material one-week starter improvement under this model. ')+
  'Before spending a claim, check injuries and NFL roles, then weigh the roster spot against your Week 13 tight-end exposure. '+
  (w13?'Both Brock Bowers and Mark Andrews have Week 13 byes; without another tight end, the roster currently has no eligible active option at that position. ':
    'Keep enough TE depth to survive the upcoming schedule. ')+
  'A trade should solve a longer-term roster need, not chase a single high-variance weekly score.';
 const third='Looking ahead, the matchup danger is not limited to raw standings. '+
  (opp?.rank?'Jersey Junkyard grades #'+opp.rank+' in FantasyBot power despite the separate Yahoo matchup forecast; that is a reason to prepare before Week 12. ':
    'Opponent ratings are incomplete and should not be assumed from the standings. ')+
  (rival?'Your Week '+model.modelWeek+' opponent '+rival.teamName+' ranks #'+(rival.rank??'—')+' in the power model. ':
    'The immediate opponent rating is not available. ')+
  'I would revisit these figures as news, usage, and injuries develop, because the scenario ranges are experimental estimates rather than validated win odds.';
 return block('Coach’s final read','AI MANAGER · FORECAST-DRIVEN',
 '<div class="edge-brief-paragraphs"><p>'+esc(first)+'</p><p>'+esc(second)+'</p><p>'+esc(third)+'</p></div>'+
 '<p class="edge-context">Source: FantasyBot 2026 Week '+model.modelWeek+' PPR rankings, current Yahoo roster and availability, and NFL bye schedule. No trades or claims were submitted.</p>');
}
export function renderEdgeLab(model){
 if(!model?.ready)return '<section class="edge-pending"><div class="edge-pending-icon">'+uiIcon('info')+'</div>'+
 '<h2>Predictive data unavailable</h2><p>'+esc(model?.reason||'The forward-looking model cannot be verified.')+'</p>'+
 '<small>No speculative lineup swaps or fake win odds will be shown.</small></section>';
 const first=model.priorities[0];
 const lineup=model.lineups.balanced;
 const yellow=model.quality?.yahooFresh===false?
 '<div class="edge-stale-banner"><strong>Research mode · Yahoo capture aging</strong>'+
 '<p>FantasyBot roster names were independently rechecked, but Yahoo lineup locks and acquisition status are not currently verified. This is a planning scenario, not an executable move list.</p></div>':'';
 return '<div class="edge-shell">'+yellow+'<div class="edge-intro"><span class="edge-eyebrow">BROCK HARD · INTELLIGENCE LAB</span>'+
 '<h1>Win the next decision.</h1><p>Model-driven lineup changes, verified waiver opportunities, opponent scouting and playoff risk—beyond Yahoo’s scoreboard.</p></div>'+
 '<section class="edge-hero">'+notice(model)+
 '<div class="edge-hero-label">HIGHEST-PRIORITY FINDING</div>'+
 '<h2>'+esc(first?.title||'Research your next lineup')+'</h2>'+
 '<p>'+esc(first?.detail||'Review the model report below')+'</p>'+
 '<div class="edge-hero-metrics"><div><span>WEEK '+model.modelWeek+' BEST</span><strong>'+
 (lineup?.available?num(lineup.mean,1):'—')+'</strong><small>model pts</small></div>'+
 '<div><span>MODEL LINEUP GAIN</span><strong>'+
 (lineup?.available?((lineup.gain||0)>0?'+':'')+num(lineup.gain,1):'—')+'</strong><small>not guaranteed</small></div>'+
 '<div><span>MY POWER RANK</span><strong>#'+esc(model.powerRank??'—')+'</strong><small>out of eight</small></div></div></section>'+
 '<div id="edge-priorities">'+recommendations(model)+'</div>'+
 '<div id="edge-lineup">'+lineups(model)+'</div>'+
 '<div id="edge-waivers">'+waivers(model)+'</div>'+
 '<div id="edge-trades">'+tradeLeverage(model)+'</div>'+
 '<div id="edge-rivals">'+opponents(model)+'</div>'+
 '<div id="edge-byes">'+byes(model)+'</div>'+
 '<div id="edge-brief">'+briefing(model)+'</div>'+
 '<details class="edge-methodology"><summary>How the AI predictions are built '+uiIcon('chevron')+'</summary>'+
 '<p>FantasyBot supplies explicit Week '+model.modelWeek+' PPR player forecasts. Yahoo supplies Brock’s actual roster, starting slots, available-player inventory and pregame opponent forecasts. Official NFL scheduling supplies bye weeks. The engine joins exact player identities, solves a constrained lineup assignment and evaluates hypothetical waiver substitutions. Scenarios use observed short-term scoring variation plus a positional prior. They are not audited or calibrated probabilities.</p>'+
 '<p>The model only runs when both captures identify the same 2026 Yahoo league and exact roster. It expires after 36 hours and never submits any transactions.</p>'+
 '<div class="edge-method-sources">'+model.sources.map(s=>'<div><strong>'+esc(s.label)+'</strong> <small>'+esc(s.date||'')+'</small></div>').join('')+'</div>'+
 '</details><p class="edge-public-note">This dashboard is public. Other league members could view any published AI strategy. Treat all recommendations as advisory until checked in Yahoo.</p>'+
 '</div>';
}
