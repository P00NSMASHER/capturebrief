/* Brock Hard Genius Lab interactive, evidence-labeled presentation.
 * Dynamic HTML is escaped; buttons change client-only what-if assumptions,
 * never Yahoo transactions, API requests or provider data.
 */
import {teamLogo,uiIcon} from './league-branding.mjs';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const fixed=(x,d=1)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(d):'—';
const signed=(x,d=1)=>typeof x==='number'&&Number.isFinite(x)?(x>=0?'+':'')+fixed(x,d):'—';
const box=(header,title,content,cls='')=>
 '<section class="genius-panel '+cls+'"><div class="genius-head"><div><span class="genius-kicker">'+escape(header)+
 '</span><h2>'+escape(title)+'</h2></div><span class="genius-monogram">BR<span>2</span></span></div>'+content+'</section>';
const status=g=>'<span class="genius-status '+(g?.sourceGrade==='source-checked-model'?'genius-status--fresh':'genius-status--limited')+'">'+
 escape(g?.status||'SOURCE CHECK')+'</span>';
const badge=(x,color='default')=>'<span class="genius-tag genius-tag--'+color+'">'+escape(x)+'</span>';
const action=(label,tab)=>'<button type="button" class="genius-jump" data-tab="'+escape(tab)+'">'+escape(label)+uiIcon('arrow')+'</button>';
const historical=g=>!g?.ready||g.sourceGrade==='historical-only';
const caveat=(text)=>'<p class="genius-caveat">'+uiIcon('info')+'<span>'+escape(text)+'</span></p>';
function sourceWarning(g){
 return historical(g)?'<p class="genius-historical">Research-only: this Yahoo snapshot is too old to confirm lineup locks, health, or acquisitions. No transactions can be made here.</p>':'';
}
function getStrength(g,id){
 return g.allPlay.teams.find(x=>x.teamId===String(id))||null;
}
function rival(g){
 return g.matchup?getStrength(g,g.matchup.opponentId):null;
}
export function geniusHome(g){
 if(!g?.ready)return '';
 const b=g.allPlay.brock,r=rival(g),m=g.matchup,rel=g.reliability;
 const urgent=g.priorities.filter(x=>x.grade==='critical').slice(0,2);
 return box('GENIUS LAB / OWNED-BY-EVIDENCE','How strong are you really?',
 '<div class="genius-titleline">'+badge('8-WEEK POWER AUDIT','cyan')+status(g)+'</div>'+
 '<div class="genius-statgrid">'+
 '<div><small>ALL-PLAY WIN RATE</small><strong>'+fixed(b.allPlayPct,1)+'%</strong><span>Against all seven clubs each week</span></div>'+
 '<div><small>RECORD VS EXPECTED</small><strong>'+signed(b.luckWins,2)+'</strong><span>Wins vs all-play strength</span></div>'+
 '<div><small>FORECAST ERROR</small><strong>'+fixed(rel.forecastMAE,1)+'</strong><span>Points off per team score</span></div></div>'+
 '<p class="genius-lead">A '+escape(g.allPlay.brock.wins+'–'+g.allPlay.brock.losses)+
 ' historical record tells only part of the story. Against every league team in Weeks 1–8, Brock Hard would have won '+
 fixed(b.allPlayWins,1)+' of 56 comparisons. That is a more useful measure of sustainable roster strength.</p>'+
 (m?'<div class="genius-opponent"><div>'+teamLogo(m.opponentId,'sm')+
 '<div><span>NEXT OPPONENT</span><strong>'+escape(m.opponentName)+'</strong>'+
 '<small>Rival all-play '+fixed(r?.allPlayPct,1)+'% · historical scoring volatility '+fixed(r?.scoringVolatility,1)+' pts</small></div></div>'+
 '<div class="genius-opponent-score"><strong>'+signed(m.yahooMargin,1)+'</strong><span>Yahoo team gap</span></div></div>':'')+
 (urgent.length?'<div class="genius-small-actions">'+urgent.map(x=>
 '<div><span class="genius-pulse"></span><strong>'+escape(x.title)+'</strong></div>').join('')+'</div>':'')+
 sourceWarning(g)+
 '<div class="genius-footer">'+action('Explore every edge','coach')+
 '<small>Historical all-play strength is descriptive, not a prediction of future wins.</small></div>',
 'genius-panel--hero');
}
export function geniusLineup(g){
 if(!g?.ready)return '';
 const m=g.matchup,rel=g.reliability,model=g.model;
 const clips=model?.roster?.filter(x=>x.forecast!==null).map(p=>{
  const h=p.history||[],values=h.map(x=>x.points).filter(x=>typeof x==='number'&&Number.isFinite(x));
  const avg=values.length?values.reduce((s,n)=>s+n,0)/values.length:null;
  const current=p.forecast;
  return {name:p.name,slot:p.slot,position:p.position,forecast:current,
   trend:p.modelTrend?.direction||'unknown',historyAvg:avg,
   deviation:avg===null?null:current-avg,injury:p.injury,matchupGrade:p.matchupGrade||null,bye:p.bye};
 })||[];
 const note=historical(g)?'<div class="genius-historical">This lineup model is historical. Check Yahoo for newer injury, bye and game-lock information before changing starters.</div>':
 '<div class="genius-decision-note">The biggest edge may be removing a known zero-point bye rather than chasing a small projected-point difference.</div>';
 const risky=clips.filter(p=>p.bye||p.injury||p.matchupGrade==='D'||p.matchupGrade==='F').slice(0,5);
 return box('PROJECTION / RISK-AWARE DECISIONS','Know what the forecast misses',
 '<div class="genius-titleline">'+status(g)+badge('ROLLING OUT-OF-SAMPLE AUDIT','violet')+'</div>'+
 '<div class="genius-statgrid">'+
 '<div><small>WEEK '+escape(m?.week??'—')+' YAHOO EDGE</small><strong>'+signed(m?.yahooMargin,1)+'</strong><span>Team forecasts, not player forecasts</span></div>'+
 '<div><small>HISTORICAL MARGIN BAND</small><strong>'+fixed(m?.marginBand.low,0)+' to '+fixed(m?.marginBand.high,0)+'</strong><span>10th–90th percentile of error scenarios</span></div>'+
 '<div><small>MODELED LINEUP UPLIFT</small><strong>'+signed(g.forecast.baseProjectionGain,1)+'</strong><span>Separate FantasyBot PPR model</span></div></div>'+
 '<div class="genius-miniboard"><div class="genius-miniboard-label"><strong>Player volatility / flags</strong>'+
 '<span>Verified Yahoo slot + independent model</span></div>'+
 (risky.length?risky.map(p=>
 '<div class="genius-player-signal"><strong>'+escape(p.name)+'</strong>'+
 '<span>'+escape(p.slot)+' · '+(p.bye?badge('BYE','danger'):p.injury?badge(p.injury,'amber'):
 p.matchupGrade?badge('MATCHUP '+p.matchupGrade,'amber'):badge('SCOUT'))+'</span>'+
 '<small>Forecast '+fixed(p.forecast,1)+' · sampled recent average '+fixed(p.historyAvg,1)+'</small></div>').join(''):
 '<div class="genius-noalerts">No obvious bye or status signal in covered starters. This is not proof every player is healthy.</div>')+
 '</div>'+note+
 caveat('The historical matchup margin band comes from Yahoo team-score errors; it is not a calibrated confidence interval for a FantasyBot lineup forecast.')+
 '<div class="genius-footer">'+action('Compare cautious / upside lineups','coach')+'</div>');
}
export function geniusPlayers(g){
 if(!g?.ready)return '';
 const gap=g.roster.urgentTe,market=g.roster.teMarket,trade=g.tradeCandidates;
 const soon=g.roster.byes.filter(x=>x.week<=14&&(x.teShortage||x.qbShortage)).slice(0,4);
 return box('WAIVER / TRADE OPTIMIZER','Buy protection before you need it',
 '<div class="genius-titleline">'+status(g)+badge('MULTI-WEEK ROSTER FIT','violet')+'</div>'+
 (gap?'<div class="genius-threat"><span>FUTURE LINEUP FAILURE</span><strong>Week '+gap.week+': no available rostered TE</strong>'+
 '<p>Both covered tight ends have NFL byes. A compatible replacement fixes a complete position shortage, even if it adds no immediate Week 10 points.</p></div>':'')+
 (soon.length?'<div class="genius-bye-grid">'+soon.map(x=>
 '<div><strong>W'+x.week+'</strong><span>'+escape(x.teShortage?'TE COVERAGE GAP':'QB COVERAGE GAP')+'</span></div>').join('')+'</div>':'')+
 '<h3 class="genius-subhead">League-listed tight ends worth checking</h3>'+
 (market.length?'<div class="genius-scout-list">'+market.slice(0,4).map(p=>
 '<div><span class="genius-dot"></span><strong>'+escape(p.name)+'</strong>'+
 badge(p.status==='free_agent'?'FA':'WAIVERS',p.status==='free_agent'?'cyan':'amber')+
 '<small>No Week 13 bye · Yahoo availability at capture</small></div>').join('')+'</div>':
 '<p class="genius-historical">No verified compatible TE candidate is in the captured 25-player inventory.</p>')+
 '<h3 class="genius-subhead">Market-fit trade shortlist</h3>'+
 (trade.length?'<div class="genius-trade">'+trade.slice(0,2).map(p=>
 '<div><span>GIVE</span><strong>'+escape(p.give)+'</strong><b>⇄</b><span>GET</span><strong>'+escape(p.receive)+'</strong>'+
 '<small>To '+escape(p.toTeam)+' · FantasyBot '+escape(String(p.marketGive))+' vs '+escape(String(p.marketReceive))+
 ' model market units; opponent has matching roster need/surplus</small></div>').join('')+'</div>':
 '<p class="genius-historical">No defensible trade match in the sourced examples.</p>')+
 sourceWarning(g)+caveat('Trade figures are comparative third-party market estimates, not guaranteed acceptance or full-season forecast values. No offers are submitted.')+
 '<div class="genius-footer">'+action('Inspect captured player pool','waivers')+'</div>');
}
export function geniusLeague(g){
 if(!g?.ready)return '';
 const teams=g.rankings,own=g.allPlay.brock,rel=g.reliability;
 const tr=teams.map((t,i)=>{
  const isMe=t.teamId==='2';const luck=Number(t.luckWins||0);
  const chance=t.historicalAllPlayPct;
  return '<div class="genius-standing'+(isMe?' genius-standing--me':'')+'">'+
   '<span class="genius-standing-rank">'+(i+1)+'</span>'+teamLogo(t.teamId,'sm')+
   '<div><strong>'+escape(t.name)+'</strong><small>Actual seed #'+escape(t.yahooStanding)+
   ' · all-play expected wins '+fixed(t.historicalExpectedWins,2)+'</small></div>'+
   '<span class="genius-standing-record">'+fixed(chance,1)+'%<small>ALL-PLAY</small></span>'+
   '<span class="genius-standing-luck '+(luck>0?'lucky':luck<0?'unlucky':'')+'">'+signed(luck,2)+
   '<small>WIN GAP</small></span></div>';
 }).join('');
 const grade=rel.rollingBrier<=.25?'Better than coinflip baseline on this small holdout sample':
  'Did not beat the 0.25 coinflip Brier baseline on this holdout';
 return box('LEAGUE / FORECAST LAB','Reveal who is genuinely dangerous',
 '<div class="genius-titleline">'+status(g)+badge('ALL-PLAY · W1–W8','cyan')+'</div>'+
 '<div class="genius-statgrid">'+
 '<div><small>YOUR ALL-PLAY</small><strong>'+fixed(own.allPlayPct,1)+'%</strong><span>8 weeks × 7 rivals</span></div>'+
 '<div><small>OUT-OF-SAMPLE BRIER</small><strong>'+fixed(rel.rollingBrier,3)+'</strong><span>20 future-held-out games</span></div>'+
 '<div><small>FORECAST HIT RATE</small><strong>'+fixed(rel.rollingAccuracy,1)+'%</strong><span>Walk-forward test only</span></div></div>'+
 '<div class="genius-scoring-note">'+escape(grade)+'. The predictions were produced using earlier historical weeks only; sample size is limited.</div>'+
 '<div class="genius-standing-head"><span>LEAGUE ALL-PLAY RANK</span><span>WINS VS STRENGTH</span></div>'+
 '<div class="genius-standings">'+tr+'</div>'+
 caveat('All-play is a retrospective score comparison, not a true rest-of-season roster forecast. Luck wins are actual wins minus all-play expected wins; they do not prove causation.')+
 '<div class="genius-footer">'+action('Model conditional playoff paths','coach')+'</div>');
}
export function geniusCoach(g,{field=4,realization=.5}={}){
 if(!g?.ready)return '';
 const m=g.matchup,p=g.playoff,rel=g.reliability,
 gains=[0,.25,.5,.75,1];
 const caps=(g.forecast.baseProjectionGain||0);
 const controls='<div class="genius-controls"><div><label>WHAT FRACTION OF THE MODEL UPLIFT MATERIALIZES?</label>'+
 '<div class="genius-segments" role="group" aria-label="Forecast gain realization">'+gains.map(v=>
 '<button type="button" data-genius-realization="'+v+'" aria-pressed="'+(Math.abs(realization-v)<.001)+'">'+
 (v*100)+'%</button>').join('')+'</div></div>'+
 '<div><label>HYPOTHETICAL PLAYOFF FIELD</label>'+
 '<div class="genius-segments genius-segments--field" role="group" aria-label="Playoff field size">'+[4,6].map(v=>
 '<button type="button" data-genius-field="'+v+'" aria-pressed="'+(field===v)+'">'+v+' clubs</button>').join('')+'</div></div></div>';
 const fields=p?'<div class="genius-statgrid genius-statgrid--playoff">'+
 '<div><small>WEEK 10 SCENARIO</small><strong>'+fixed(p.scenario.week10WinPercent,1)+'%</strong>'+
 '<span>Baseline '+fixed(p.baseline.week10WinPercent,1)+'% · '+signed(p.delta.nextGame,1)+'pp</span></div>'+
 '<div><small>TOP-'+field+' SCENARIO</small><strong>'+fixed(p.scenario.madeFieldPercent,1)+'%</strong>'+
 '<span>'+signed(p.delta.field,1)+'pp vs no modeled gain</span></div>'+
 '<div><small>GAIN ASSUMED</small><strong>'+signed(p.appliedWeeklyGain,1)+'</strong>'+
 '<span>of '+fixed(caps,1)+' potential Week 10 points</span></div></div>':'';
 return box('GENIUS LAB / EXPERIMENTS','Change the assumption. See the consequence.',
 '<div class="genius-titleline">'+status(g)+badge('EXPLAINABLE SCENARIO','violet')+'</div>'+
 '<p class="genius-lead">Optimizing the roster and winning the matchup are different questions. Test how the estimated advantage changes if only part of a projected gain becomes real.</p>'+
 controls+fields+
 '<div class="genius-match-band"><div><span>Yahoo’s W10 pregame gap</span><strong>'+signed(m?.yahooMargin,1)+' pts</strong></div>'+
 '<div><span>Historical outcome scenario frequency</span><strong>'+fixed(m?.historicalWinScenario,1)+'%</strong></div>'+
 '<div><span>10th–90th-percentile score margin</span><strong>'+fixed(m?.marginBand.low,0)+' to '+fixed(m?.marginBand.high,0)+'</strong></div></div>'+
 '<div class="genius-credibility"><div>'+badge('HOLDOUT AUDIT','cyan')+
 '<strong>'+rel.rollingTestGames+' genuine out-of-sample matchups</strong></div>'+
 '<p>Walk-forward Brier '+fixed(rel.rollingBrier,3)+' versus 0.250 constant coinflip baseline. '+
 'Future results may differ; probabilities are conditional model frequencies, not calibrated outcomes.</p></div>'+
 sourceWarning(g)+
 caveat(p?.notes?.join(' ')||'Playoff field size, tiebreakers, and exact playoff calendar are unverified. No actual qualification odds are claimed.')+
 '<div class="genius-footer">'+action('Review exact lineup decisions','lineup')+'</div>',
 'genius-panel--scenario');
}
export function geniusArchived(g){
 if(!g?.ready)return '';
 const b=g.allPlay.brock,rel=g.reliability;
 return box('HISTORICAL RECORD / NO CURRENT MOVES','The strategy archive still has value',
 '<p class="genius-historical">Yahoo and/or projection inputs are too old to recommend any current adds, drops, trades, or lineup changes. Research only.</p>'+
 '<div class="genius-statgrid">'+
 '<div><small>HISTORICAL ALL-PLAY</small><strong>'+fixed(b.allPlayPct,1)+'%</strong><span>Eight verified weeks</span></div>'+
 '<div><small>YAHOO FORECAST MAE</small><strong>'+fixed(rel.forecastMAE,1)+'</strong><span>64 team-score observations</span></div>'+
 '<div><small>HELD-OUT GAMES</small><strong>'+rel.rollingTestGames+'</strong><span>Rolling-origin tests</span></div></div>'+
 caveat('Information is explicitly historical. Refresh Yahoo and independent model sources before taking action.'),
 'genius-panel--archived');
}
