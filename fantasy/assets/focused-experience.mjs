/* One purpose per tab. Decision data comes from previously validated read-only
 * Yahoo, FantasyBot and league-intelligence sources. Presentational only.
 * No provider network calls, user mutations, invented player projections or
 * duplicated analytics cards. Everything user-supplied is escaped.
 */
import {teamLogo,uiIcon} from './league-branding.mjs';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const n=(v,p=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(p):'—';
const signed=(v,p=1)=>typeof v==='number'&&Number.isFinite(v)?(v>0?'+':'')+n(v,p):'—';
const valid=(p)=>p&&typeof p.name==='string'&&p.name.length>0;
const btn=(label,tab,extra='')=>'<button type="button" class="focus-cta" data-tab="'+esc(tab)+'"'+extra+'>'+esc(label)+uiIcon('arrow')+'</button>';
const heading=(kicker,title)=>'<header class="focus-head"><span>'+esc(kicker)+'</span><h2>'+esc(title)+'</h2></header>';
const card=(cls,html)=>'<section class="focus-panel '+cls+'">'+html+'</section>';
const sourceLine=(label,copy)=>'<p class="focus-source"><span>'+esc(label)+'</span> · '+esc(copy)+'</p>';
const empty=copy=>'<div class="focus-empty">'+esc(copy)+'</div>';
const historical=(model)=>model?.quality?.yahooFresh===false;
const note=()=>'<span class="focus-model-tag">ESTIMATE · NOT A GUARANTEE</span>';

export function focusHome({team,genius,model,currentWeek}){
 const healthy=genius?.ready&&genius.sourceGrade==='source-checked-model';
 const top=genius?.ready&&healthy?genius.actionablePriorities?.[0]:null;
 const first=top||null;
 const title=first?.title||'Check the latest lineup before kickoff';
 const desc=first?.body||'The current forecast is incomplete or the Yahoo snapshot is old. Review roster health and eligibility in Yahoo rather than acting on a stale model.';
 const destination=first?.tab||'lineup';
 return card('focus-home',heading('YOUR ONE NEXT DECISION','Make one move that matters')+
 '<div class="focus-lead-action"><div><strong>'+esc(title)+'</strong><p>'+esc(desc)+'</p></div>'+
 (healthy?btn('See the exact decision',destination):btn('Inspect lineup evidence','lineup'))+'</div>'+
 '<div class="focus-subline"><span>Week '+esc(currentWeek)+' Yahoo capture</span>'+
 '<span>'+(healthy?'Independent Week '+esc(model?.modelWeek||currentWeek+1)+' forecast':'No current move recommendation')+'</span></div>');
}
const line=(label,body,tone='neutral')=>'<div class="focus-move focus-move--'+esc(tone)+'"><span>'+esc(label)+'</span><strong>'+esc(body)+'</strong></div>';
const rosterRow=p=>'<div class="focus-roster-row"><span>'+esc(p.slot||'—')+'</span><strong>'+esc(p.name)+'</strong>'+
 '<small>'+esc(p.position||'')+(p.injury?' · '+esc(p.injury):'')+'</small></div>';
export function focusLineup({team,model,mode='balanced'}){
 const ready=model?.ready&&model.quality?.yahooFresh&&model.lineups?.balanced?.available;
 const selected=['safe','balanced','upside'].includes(mode)?mode:'balanced';
 const best=model?.lineups?.[selected];
 const blocks=[];
 if(ready){
  const changedOut=(best.outPlayers||[]).filter(x=>valid(x));
  const shifted=(best.assignments||[]).filter(a=>{
   const original=(model.roster||[]).find(p=>String(p.id)===String(a.id));
   return original&&original.slot!==a.slot&&
     !['BN','BE','BENCH','IR','NA','TAXI'].includes(original.slot);
  }).filter(x=>valid(x));
  const inPlayers=(best.inPlayers||[]).filter(x=>valid(x));
  for(const p of changedOut)blocks.push(line('1 · BENCH',p.name+' ('+p.slot+(p.bye?', bye':'')+')','out'));
  for(const p of shifted){
   const old=(model.roster||[]).find(q=>String(q.id)===String(p.id));
   blocks.push(line('2 · SLIDE',p.name+': '+old.slot+' → '+p.slot,'shift'));
  }
  for(const p of inPlayers)blocks.push(line('3 · START',p.name+' at '+p.slot,'in'));
 }
 const modes='<div class="focus-scenario-modes" role="group" aria-label="Lineup risk preference">'+
 [['safe','Cautious'],['balanced','Balanced'],['upside','Upside']].map(([id,label])=>
 '<button type="button" data-edge-mode="'+id+'" aria-pressed="'+(selected===id)+'">'+label+'</button>').join('')+'</div>';
 const summary=ready?'<div class="focus-lineup-metrics"><div><span>CURRENT MODEL</span><strong>'+n(best.currentScore,1)+'</strong></div>'+
 '<div><span>BEST LEGAL SLOTS</span><strong>'+n(best.mean,1)+'</strong></div>'+
 '<div><span>ESTIMATED DIFFERENCE</span><strong>'+signed(best.gain,1)+'</strong></div></div>':'';
 const action=ready?
  '<div class="focus-move-list">'+(blocks.length?blocks.join(''):line('ALREADY BEST','No higher-projected assignment in the current roster'))+'</div>'+
  sourceLine('FANTASYBOT PPR','Week '+model.modelWeek+' projections; check Yahoo locks, injury updates and eligibility before making any change'):
  empty('No complete, current, source-verified Week '+esc(model?.modelWeek||'—')+' model is available. Showing saved slots without a speculative swap.');
 const starters=team.roster.filter(p=>!['BN','BE','BENCH','IR','IR+','NA','TAXI'].includes(p.slot));
 const reserves=team.roster.filter(p=>!starters.includes(p));
 return card('focus-lineup',heading('START / SIT','Only the changes that affect your next score')+
 (ready?modes+note():'')+summary+action+
 '<details class="focus-secondary"><summary>See the '+starters.length+' starting slots at capture '+uiIcon('chevron')+'</summary>'+
 '<div class="focus-roster">'+starters.map(rosterRow).join('')+'</div></details>'+
 '<details class="focus-secondary"><summary>Bench and reserve ('+reserves.length+') '+uiIcon('chevron')+'</summary>'+
 '<div class="focus-roster">'+reserves.map(rosterRow).join('')+'</div></details>');
}
export function focusPlayers({team,genius,model,filter='ALL',poolOpen=false}){
 const ready=genius?.ready&&!historical(model)&&genius.sourceGrade==='source-checked-model';
 const gap=genius?.roster?.urgentTe;
 const trade=(genius?.tradeCandidates||[]).find(t=>t.isSupported&&t.opponentNeed&&t.opponentSurplus);
 const all=Array.isArray(team.availablePlayers)?team.availablePlayers:[];
 const faForecasts=new Map((model?.waivers?.watches||[]).map(p=>[String(p.id),p]));
 const positions=['ALL','QB','RB','WR','TE','K','DEF'];
 const eligible=all.filter(p=>filter==='ALL'||p.position===filter);
 // Do not imply an unverified pickup: the source distinguishes league availability
 // at capture from up-to-date acquisition permission.
 const market=eligible.map(p=>{
  const prediction=faForecasts.get(String(p.id));
  return '<div class="focus-market-row"><span>'+esc(p.position||'—')+'</span><strong>'+esc(p.name)+'</strong>'+
  '<small>'+(prediction&&ready?n(prediction.forecast,1)+' model pts':'No current forecast')+
  ' · '+esc(p.acquisitionState==='free_agent'?'FA at capture':p.acquisitionState==='waivers'?'Waivers at capture':'Status unverified')+'</small></div>';
 }).join('');
 const shortages=gap?
 '<div class="focus-need"><span>HIGHEST-COST ROSTER GAP</span>'+
 '<strong>Week '+esc(gap.week)+': no rostered TE with an NFL game unless the roster changes</strong>'+
 '<p>Both saved tight ends share an NFL bye. Solve the coverage gap before a low-impact speculative pickup.</p></div>':
 empty('No verified single-position zero was found in the current supported bye calendar.');
 const marketNote=ready?'The Yahoo player pool was verified at capture; recheck before acting.':'Yahoo availability or model is outdated. No acquisition is recommended.';
 return card('focus-players',heading('WAIVERS / TRADE','Solve an actual roster problem')+
 shortages+
 (trade?'<div class="focus-trade"><span>TRADE IDEA TO INVESTIGATE — NOT AN OFFER</span>'+
 '<strong>'+esc(trade.give)+' ⇄ '+esc(trade.receive)+'</strong>'+
 '<p>Opponent '+esc(trade.toTeam)+' has the matching positional need/surplus. Third-party market units: '+
 esc(trade.marketGive)+' / '+esc(trade.marketReceive)+'. No acceptance probability is established.</p></div>':'')+
 '<details class="focus-secondary" data-focus-pool'+(poolOpen?' open':'')+'><summary>Browse '+all.length+' Yahoo-listed players at capture '+uiIcon('chevron')+'</summary>'+
 '<div class="filterbar focus-filters" role="group" aria-label="Filter by player position">'+positions.map(x=>
 '<button type="button" data-filter="'+x+'" aria-pressed="'+(x===filter)+'" class="'+(x===filter?'chosen':'')+'">'+
 (x==='ALL'?'All':x)+'</button>').join('')+'</div>'+
 '<div class="focus-roster">'+(market||empty('No players in this position at capture.'))+'</div></details>'+
 sourceLine('CURRENT STATUS',marketNote));
}
export function focusLeague({genius,strategic}){
 if(!genius?.ready)return card('focus-league',heading('EIGHT-TEAM SCOUTING','No current league evidence')+
 empty('The full league record is missing or the saved weeks have changed. Do not infer opponent strength from rankings alone.'));
 const ranking=genius.rankings||[];
 const leader=ranking[0],b=ranking.find(x=>x.teamId==='2'),rel=genius.reliability;
 const table=ranking.map((p,i)=>
 '<div class="focus-power-row'+(p.teamId==='2'?' focus-power-row--me':'')+'">'+
 '<span class="focus-place">'+(i+1)+'</span>'+teamLogo(p.teamId,'sm')+
 '<div><strong>'+esc(p.name)+'</strong><small>Yahoo seed #'+esc(p.yahooStanding||'—')+'</small></div>'+
 '<span class="focus-rate">'+n(p.historicalAllPlayPct,1)+'%</span></div>').join('');
 const rivals=strategic?.ready?strategic.upcoming:genius?.matchup?[{
  week:genius.matchup.week,opponent:genius.matchup.opponentName,
  projectedMargin:genius.matchup.yahooMargin,opponentPowerRank:null}]:[];
 return card('focus-league',heading('OPPONENT INTELLIGENCE','Records do not equal roster strength')+
 '<div class="focus-rival-lead"><strong>'+esc(leader?.name||'—')+
 ' led the first eight weeks by all-play performance.</strong>'+
 '<p>Brock Hard ranked '+esc((ranking.findIndex(x=>x.teamId==='2')+1))+
 ' by historical all-play. The standings lead does not automatically make it the strongest scoring team.</p></div>'+
 '<div class="focus-power-head"><span>ALL-PLAY RANK</span><span>WINS VS ALL 7 EACH WEEK</span></div>'+
 '<div class="focus-power-list">'+table+'</div>'+
 '<details class="focus-secondary"><summary>See upcoming opponents ('+rivals.length+') '+uiIcon('chevron')+'</summary>'+
 '<div class="focus-roster">'+rivals.map(r=>'<div class="focus-schedule-row">'+
 '<span>W'+esc(r.week)+'</span><strong>'+esc(r.opponent)+'</strong>'+
 '<small>Yahoo pregame gap '+signed(r.projectedMargin,1)+' pts</small></div>').join('')+'</div></details>'+
 sourceLine('BACKTEST','20 held-out games · Brier '+n(rel.rollingBrier,3)+' · 64 projected-versus-actual team scores; small sample, not a guarantee'));
}
export function focusCoach({genius,model,plan,field=4,realization=.5}){
 const ok=genius?.ready;
 const p=genius?.playoff;
 const choices=[0,.25,.5,.75,1];
 const body=ok?'<div class="focus-whatif"><div class="focus-control"><strong>How much of the projected lineup gain happens?</strong>'+
 '<div class="focus-segments" role="group" aria-label="Lineup gain realized">'+choices.map(v=>
 '<button type="button" data-genius-realization="'+v+'" aria-pressed="'+(v===realization)+'">'+(v*100)+'%</button>').join('')+'</div></div>'+
 '<div class="focus-control"><strong>Hypothetical playoff field</strong><div class="focus-segments" role="group" aria-label="Playoff field">'+
 [4,6].map(v=>'<button type="button" data-genius-field="'+v+'" aria-pressed="'+(v===field)+'">'+v+' teams</button>').join('')+'</div></div>'+
 '<div class="focus-sim-result"><div><span>WEEK 10</span><strong>'+n(p?.scenario?.week10WinPercent,1)+'%</strong>'+
 '<small>'+signed(p?.delta?.nextGame,1)+' percentage points vs baseline</small></div>'+
 '<div><span>TOP '+field+'</span><strong>'+n(p?.scenario?.madeFieldPercent,1)+'%</strong>'+
 '<small>Conditional, not actual Yahoo playoff odds</small></div></div></div>':
 empty('No compatible, current Week '+esc(model?.modelWeek||'—')+' forecasts and league evidence to run a useful comparison.');
 const summary=Array.isArray(plan?.summary)&&plan.summary.length===3?plan.summary:
 (ok?[
  'Your league scoring strength is best evaluated across all eight teams, not just from the current standings.',
  'Start with legal lineup changes and bye coverage before pursuing lower-certainty trade or waiver ideas.',
  'Playoff paths remain conditional until the actual Yahoo bracket and updated game probabilities are confirmed.'
 ]:[]);
 const paras=summary.map(s=>'<p>'+esc(s)+'</p>').join('');
 return card('focus-coach',heading('DECISION LAB','Test the decision, not the hype')+
 '<p class="focus-intro">Set assumptions yourself. These results show sensitivity, not how many games you are guaranteed to win.</p>'+
 body+sourceLine('MODEL LIMIT','Only 32 completed games and 20 rolling holdout matchups; playoff field and tiebreaker are hypothetical.')+
 '<details class="focus-secondary focus-method"><summary>See model sources and limitations '+uiIcon('chevron')+'</summary>'+
 '<ul><li>Yahoo Week 9 standings and Week 10–14 team projections.</li>'+
 '<li>FantasyBot player estimates and historical team-score residuals are separate models.</li>'+
 '<li>4-team and 6-team playoff fields are scenarios, not verified league rules.</li>'+
 '<li>No roster, waiver or trade action can be submitted here.</li></ul></details>'+
 (paras?'<section class="focus-brief"><h3>Coach’s final assessment</h3>'+paras+'</section>':''));
}
