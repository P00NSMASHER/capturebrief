/* Fantasy HQ — source-aware strategy components for Home, Lineup, Players & League.
   Pure HTML rendering; zero provider calls, no analytics or roster writes. */
import {teamLogo,resolveTeam,uiIcon} from './league-branding.mjs';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(n,d=1)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(d):'—';
const ch=(n,d=1)=>typeof n==='number'&&Number.isFinite(n)?(n>=0?'+':'')+n.toFixed(d):'—';
const button=(label,tab)=>'<button type="button" class="strat-link" data-tab="'+esc(tab)+'">'+esc(label)+uiIcon('arrow')+'</button>';
const pill=(label,tone='teal')=>'<span class="strat-pill strat-pill--'+esc(tone)+'">'+esc(label)+'</span>';
const error=()=>'<div class="strat-unavailable"><strong>Fresh strategy evidence is unavailable.</strong>'+
 '<span>The verified model or full-league data may have aged. Published Yahoo scores remain visible; no unsupported move is recommended.</span></div>';
const head=(kicker,title)=>'<div class="strat-heading"><div><span class="strat-kicker">'+esc(kicker)+'</span><h2>'+esc(title)+'</h2></div></div>';
const accuracy=b=>b?'<div class="strat-source">'+uiIcon('info')+
 '<span>'+b.matchups+' previous Yahoo league matchups · average forecast miss '+num(b.mae,1)+
 ' pts · correct favorites '+b.winnerCorrect+'/'+b.winnerTested+'. Retrospective performance, not certainty.</span></div>':'';
export function homeStrategy(report){
 if(!report?.ready)return '<section class="strat-card strat-card--home">'+head('DECISION SUPPORT','What matters next')+error()+'</section>';
 const model=report.model,first=report.priorities||[];
 const highlights=first.slice(0,4).map((p,i)=>
 '<article class="strat-priority"><span class="strat-order">'+(i+1)+'</span><div>'+
 '<strong>'+esc(p.title)+'</strong><p>'+esc(p.detail)+'</p></div>'+
 button('Review',p.tab||'coach')+'</article>').join('');
 const win=report.odds?.baseline?.week10Win;
 const next=report.exposure.week10;
 const metrics=[
 ['WEEK 10',next?.projectedMargin===undefined?'—':ch(next.projectedMargin,1)+' pts','Yahoo pregame gap'],
 ['HISTORICAL MAE',num(report.calibration.mae,1)+' pts','Yahoo score forecast miss'],
 ['NEXT OPPONENT',next?.opponentPowerRank?'#'+next.opponentPowerRank:'—','FantasyBot power rank']
 ];
 return '<section class="strat-card strat-card--home">'+
 '<div class="strat-titleline">'+head('INTELLIGENCE / PRIORITIZED','Make the next move count')+
 pill(report.status==='actionable-forecast'?'SOURCE-CHECKED':'RESEARCH ONLY',report.status==='actionable-forecast'?'teal':'amber')+'</div>'+
 '<div class="strat-metrics">'+metrics.map(([key,value,desc])=>
 '<div class="strat-metric"><span>'+esc(key)+'</span><strong>'+esc(value)+'</strong><small>'+esc(desc)+'</small></div>').join('')+'</div>'+
 '<div class="strat-priorities">'+highlights+'</div>'+
 '<div class="strat-bottom">'+button('Open the full Coach intelligence lab','coach')+
 '<p>League forecasts are imperfect; decisions are advisory and never submitted automatically.</p></div>'+
 '</section>';
}
export function lineupStrategy(report){
 if(!report?.ready)return '<section class="strat-card">'+head('MODELED START/SIT','Find your lineup advantage')+error()+'</section>';
 const model=report.model,v=model?.lineups?.balanced,source=report.source;
 const plan=v?.available?
 '<div class="strat-lineup-metrics">'+
 '<div><span>CAPTURED STARTERS</span><strong>'+num(v.currentScore,1)+'</strong><small>model PPR pts</small></div>'+
 '<div><span>EXACT BEST LINEUP</span><strong>'+num(v.mean,1)+'</strong><small>model PPR pts</small></div>'+
 '<div><span>PROJECTED GAIN</span><strong>'+ch(v.gain,1)+'</strong><small>uncertain</small></div></div>'+
 '<div class="strat-swaps">'+(v.inPlayers?.length?v.inPlayers.map(p=>
 '<div class="strat-swap strat-swap--in"><span>START</span><strong>'+esc(p.name)+'</strong><small>'+esc(p.slot)+' · '+num(p.modelPoints,1)+' projected</small></div>').join(''):
 '<p class="strat-muted">No positive roster switch projected.</p>')+
 (v.outPlayers?.length?v.outPlayers.map(p=>'<div class="strat-swap strat-swap--out"><span>MOVE OUT</span><strong>'+esc(p.name)+
 '</strong><small>'+esc(p.slot)+(p.bye?' · BYE':'')+'</small></div>').join(''):'')+'</div>':
 '<div class="strat-muted">Full lineup recommendations are unavailable: '+esc(v?.reason||'Missing player forecasts')+'.</div>';
 const risk=v?.available?'<div class="strat-riskline"><span>Illustrative team band</span><strong>'+num(v.illustrativeLow,0)+'–'+num(v.illustrativeHigh,0)+'</strong></div>':'';
 const next=report.model?.byes?.filter(b=>b.week<=14&&b.startingCount>0).slice(0,3)||[];
 return '<section class="strat-card">'+
 '<div class="strat-titleline">'+head('EXACT SLOT OPTIMIZATION','Build the strongest next-week lineup')+
 pill('WEEK '+(model?.modelWeek||'—')+' · PPR')+'</div>'+plan+risk+
 '<div class="strat-forecast-note">FantasyBot player estimates use the league’s verified full-PPR rules. K/DEF point components are not independently reconciled. Yahoo lineup locks and late injury news remain unverified.</div>'+
 (next.length?'<div class="strat-next-byes"><strong>Upcoming starter byes</strong>'+
 next.map(g=>'<span>Week '+g.week+': '+esc(g.players.filter(p=>p.starting).map(p=>p.name).join(', '))+'</span>').join('')+'</div>':'')+
 accuracy(report.calibration)+'</section>';
}
export function playersStrategy(report){
 if(!report?.ready)return '<section class="strat-card">'+head('WAIVER EDGE','Make every claim count')+error()+'</section>';
 const market=report.waiverPriorities||[],gap=report.week13,validated=report.status==='actionable-forecast';
 const deal=report.trade.find(x=>x.recommendation==='investigate');
 const featured=market.filter(p=>p.name==='Dallas Goedert');
 const other=market.filter(p=>p.name!=='Dallas Goedert').slice(0,5);
 const board=validated?'<div class="strat-pick-list">'+
 [...featured,...other].map((p,i)=>
 '<div class="strat-pick"><span class="strat-pick-number">'+(i+1)+'</span>'+
 '<div><strong>'+esc(p.name)+'</strong><span>'+esc(p.reason||'Projected one-week scouting lead')+'</span></div>'+
 '<div class="strat-pick-score">'+(p.week10Projection==null?'BYE FIT':num(p.week10Projection,1)+' pts')+'</div></div>').join('')+'</div>':
 '<div class="strat-muted">Current Yahoo availability is too old to endorse acquisitions. Research the historical roster fit, then refresh Yahoo before acting.</div>';
 const trade=deal?'<div class="strat-trade-preview"><div><span>PLAYER YOU WOULD SEND</span><strong>'+esc(deal.outgoing)+'</strong></div>'+
 '<div class="strat-exchange">⇄</div><div><span>PLAYER YOU WOULD TARGET</span><strong>'+esc(deal.target)+'</strong></div></div>'+
 '<p>Recipient: '+esc(deal.team)+' · FantasyBot value comparison '+esc(String(deal.modelValueOutgoing))+
 ' to '+esc(String(deal.modelValueIncoming))+' (even). The recipient needs RB depth and has TE surplus. Verify interest, current values and transaction rules; nothing has been proposed.</p>':'';
 return '<section class="strat-card">'+
 '<div class="strat-titleline">'+head('FUTURE VALUE / ROSTER FIT','Find value before everyone else')+
 pill(validated?'YAHOO-CHECKED AT CAPTURE':'ARCHIVED MARKET',validated?'teal':'amber')+'</div>'+
 (gap.te13Shortage?'<div class="strat-shortage"><span>WEEK 13 POSITION GAP</span>'+
 '<strong>Both rostered tight ends are on bye.</strong>'+
 '<p>Holding the current roster would leave no eligible TE option. An advance acquisition can be worth more than a small Week 10 projected gain.</p></div>':'')+
 '<h3 class="strat-subhead">Watchlist ranked by fit, not popularity</h3>'+board+
 '<h3 class="strat-subhead">Trade that solves a real problem</h3>'+trade+
 '<div class="strat-bottom">'+button('View all 25 captured available players','waivers')+
 '<p>Displayed players were available only when Yahoo was captured. No waiver claim or trade has been placed.</p></div>'+
 '</section>';
}
function oddsTable(data){
 if(!data)return '<div class="strat-muted">Playoff simulation unavailable.</div>';
 const a=data.baseline,b=data.optimized;
 const cells=[
 ['Top 4',a.top4,b.top4,data.delta.top4],
 ['Top 6',a.top6,b.top6,data.delta.top6],
 ['Week 10 win',a.week10Win,b.week10Win,data.delta.week10Win]
 ];
 return '<div class="strat-odds-table"><div class="strat-odds-head"><span>CONDITIONAL SCENARIO</span><span>BASE</span><span>IF MODEL GAIN</span></div>'+
 cells.map(([name,base,opt,gain])=>'<div class="strat-odds-row"><strong>'+esc(name)+'</strong>'+
 '<span>'+num(base,1)+'%</span><span>'+num(opt,1)+'% <small>'+ch(gain,1)+'pp</small></span></div>').join('')+'</div>';
}
export function leagueStrategy(report){
 if(!report?.ready)return '<section class="strat-card">'+head('LEAGUE INTELLIGENCE','Know the real threats')+error()+'</section>';
 const power=report.rankings||[],schedule=report.upcoming||[];
 const swing=[...schedule].sort((a,b)=>(a.projectedMargin)-(b.projectedMargin)).slice(0,2);
 const table=power.map(t=>'<div class="strat-power-row">'+teamLogo(t.id,'sm')+
 '<span class="strat-power-name">'+esc(t.name)+(t.id==='2'?'<small>YOUR TEAM</small>':'')+'</span>'+
 '<span class="strat-power-rank">#'+t.rank+' <small>YAHOO</small></span>'+
 '<span class="strat-power-rank">#'+(t.powerRank??'—')+' <small>MODEL</small></span></div>').join('');
 const futures=schedule.map(g=>
 '<div class="strat-matchup-row">'+teamLogo(resolveTeam(g.opponent)?.id,'sm')+
 '<div><span>WEEK '+g.week+'</span><strong>'+esc(g.opponent)+'</strong>'+
 '<small>Power #'+esc(g.opponentPowerRank??'—')+' · Yahoo gap '+ch(g.projectedMargin,1)+' pts</small></div></div>').join('');
 const c=report.calibration||{};
 const assumptions=report.odds?.assumptions||[];
 return '<section class="strat-card">'+
 '<div class="strat-titleline">'+head('EIGHT CLUBS / ONE TROPHY','Scout opponents, not standings alone')+
 pill('MODEL + YAHOO')+'</div>'+
 (swing.length?'<div class="strat-threat"><span>MOST PRESSING MATCHUP</span>'+
 '<strong>Week '+swing[0].week+' · '+esc(swing[0].opponent)+'</strong>'+
 '<p>Yahoo projects '+ch(swing[0].projectedMargin,1)+' points for Brock. Opponent power rank #'+esc(swing[0].opponentPowerRank??'—')+
 ', independent of their current record.</p></div>':'')+
 '<h3 class="strat-subhead">Conditional playoff scenarios</h3>'+oddsTable(report.odds)+
 '<p class="strat-smallnote">Assumptions: regular season ends Week 14, 4 or 6 playoff teams, wins then points-for tiebreaker. Actual Yahoo playoff rules are not verified. “If model gain” assumes the full forecast lineup benefit occurs in Week 10; no lineup changes are made.</p>'+
 '<h3 class="strat-subhead">Rankings versus roster strength</h3>'+
 '<div class="strat-power-table"><div class="strat-power-row strat-power-row--head"><span>TEAM</span><span>YAHOO</span><span>POWER</span></div>'+
 table+'</div>'+
 '<div class="strat-two-cols"><div><h3 class="strat-subhead">Remaining opponents</h3>'+futures+'</div>'+
 '<div><h3 class="strat-subhead">How predictable is this league?</h3>'+
 '<div class="strat-cal-metrics"><div><strong>'+num(c.mae,1)+'</strong><span>Mean absolute points error</span></div>'+
 '<div><strong>'+num(c.rmse,1)+'</strong><span>RMSE per team score</span></div>'+
 '<div><strong>'+num(c.winnerAccuracy,1)+'%</strong><span>Yahoo favorites correct, '+c.matchups+' games</span></div></div></div></div>'+
 '<p class="strat-smallnote">Playoff percentages are conditional simulations using empirical league scoring errors—not verified qualification probabilities. The 4/6-team league field size and scoring tiebreaker must be confirmed before treating them as actual odds.</p>'+
 '</section>';
}
export function archivedStrategy(report){
 if(!report?.ready)return '';
 return '<section class="strat-card strat-card--archived">'+head('HISTORICAL RESEARCH','Earlier league intelligence')+
 '<p>From the saved Week '+esc(report.model?.modelWeek??'10')+' analysis: Yahoo’s pregame scores missed by '+num(report.calibration?.mae,1)+
 ' points on average across '+(report.calibration?.teamObservations??'—')+' team scores. This historical benchmark is still informative, but all player move, availability and playoff recommendations are suspended until current Yahoo data is verified.</p>'+
 '</section>';
}
