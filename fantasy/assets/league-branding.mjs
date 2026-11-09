/* Fantasy HQ · Original league crest set. Stylized artwork is created for this app;
   these are NOT claimed to be team-uploaded Yahoo avatars. No external requests. */
export const LEAGUE_TEAMS=Object.freeze([
 {id:'1',name:'BEEFS GAY',short:'BEEFS',color:'#ff9c6a',kind:'bull'},
 {id:'2',name:'Brock Hard & Tee Baggin',short:'Brock Hard',color:'#45efc1',kind:'bolt'},
 {id:'3',name:'Frenchville HornHog',short:'HornHog',color:'#bc9aff',kind:'boar'},
 {id:'4',name:'Chasing Greatness',short:'Chasing Greatness',color:'#f8cd74',kind:'trophy'},
 {id:'5',name:'Jersey junkyard',short:'Jersey Junkyard',color:'#ffa36b',kind:'gear'},
 {id:'6',name:'Josh ❤️creampies',short:'Josh',color:'#ff84bd',kind:'heart'},
 {id:'7',name:'Elmira Express',short:'Elmira Express',color:'#8bd8ff',kind:'train'},
 {id:'8',name:'Hazleton Coal Mine',short:'Hazleton Coal Mine',color:'#c5e987',kind:'mine'}
]);
const norm=s=>String(s??'').toLowerCase().replace(/[^a-z0-9]+/g,'').trim();
const x=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function resolveTeam(value){
 const id=String(value?.teamId??value?.id??value??'');
 return LEAGUE_TEAMS.find(t=>t.id===id)||LEAGUE_TEAMS.find(t=>norm(t.name)===norm(value?.teamName??value?.name??value))||null;
}
const marks={
 bolt: '<path d="M57 11 28 54h20l-8 35 34-48H53Z" fill="#eafff9"/><path d="m30 65-12-7 5 13 9 4M70 27l12-9-5 18-8 3" fill="#72eccc" opacity=".75"/><path d="M25 78q25 14 50-4" fill="none" stroke="#eafff9" stroke-width="3" opacity=".6"/>',
 bull:'<path d="M27 34Q12 28 11 13q12 10 24 8L39 34Zm46 0q15-6 16-21-12 10-24 8l-4 13Z" fill="#fff0df"/><path d="M29 35q7-11 21-11t21 11l-5 31q-7 13-16 14-12-1-18-14Z" fill="#f9f0df"/><path d="M38 45h8l-3 6-7-2Zm16 0h8l2 4-7 2Z" fill="#623d3a"/><path d="M38 63q12-9 24 0l-4 10H42Z" fill="#dca78e"/><circle cx="44" cy="67" r="2" fill="#623d3a"/><circle cx="56" cy="67" r="2" fill="#623d3a"/>',
 boar:'<path d="M19 45q-4-22 10-28l9 14q12-8 24 0l9-14q14 6 10 28l-6 24-25 16-25-16Z" fill="#f4e9ff"/><path d="M28 48 41 54l-4 5-12-3Zm44 0L59 54l4 5 12-3Z" fill="#4f356c"/><path d="M37 66q13-11 26 0l-6 14H43Z" fill="#ba8aca"/><path d="M29 65 15 57l7 16 15 5m34-13 14-8-7 16-15 5" fill="#e4ceff"/><circle cx="44" cy="70" r="2" fill="#54306d"/><circle cx="56" cy="70" r="2" fill="#54306d"/>',
 trophy:'<path d="M34 20h32l-4 37q-5 9-12 9t-12-9Z" fill="#fff0c9"/><path d="M32 28H19v9q1 17 19 18m30-27h13v9Q80 54 62 55" fill="none" stroke="#fff0c9" stroke-width="7" stroke-linecap="round"/><path d="M50 65v12m-16 4h32" stroke="#fff0c9" stroke-width="7" stroke-linecap="round"/><path d="m50 30 4 8 9 1-7 6 2 9-8-4-8 4 2-9-7-6 9-1Z" fill="#c29142"/>',
 gear:'<path d="m45 13 10 0 3 10 9 4 10-4 7 8-6 9 3 10 10 5-2 11-11 1-6 8 1 11-10 5-7-8H45l-7 8-10-5 1-11-6-8-11-1-2-11 10-5 3-10-6-9 7-8 10 4 9-4Z" fill="#ffe3c8"/><circle cx="50" cy="52" r="19" fill="#b7643c"/><path d="m38 46 7-7 6 7-6 6 15 15 6-6-15-15 6-6-7-7-7 7" fill="none" stroke="#fff8ef" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"/>',
 heart:'<path d="M50 82 18 52Q1 33 19 21q15-10 31 5 16-15 31-5 18 12 1 31Z" fill="#fff1f6"/><path d="m30 51 14 0 7-15 8 28 7-13h11" stroke="#c64b81" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="m22 16 2-7m59 9 5-5" stroke="#fff4fd" stroke-width="4" stroke-linecap="round"/>',
 train:'<path d="M29 16h42q8 0 8 9v44q0 9-10 9H31q-10 0-10-9V25q0-9 8-9Z" fill="#e5f7ff"/><path d="M30 28h40v24H30Z" fill="#4287b5"/><path d="m30 36 40-8v9l-40 8Z" fill="#99d8ef" opacity=".8"/><path d="M31 65h13m12 0h13" stroke="#36799b" stroke-width="5" stroke-linecap="round"/><path d="m30 79-9 12m49-12 9 12" stroke="#e5f7ff" stroke-width="5" stroke-linecap="round"/><path d="M40 20v6m20-6v6" stroke="#36799b" stroke-width="4"/>',
 mine:'<path d="m10 73 25-39 14 20 16-29 26 48Z" fill="#f0ffd5"/><path d="m35 34 8 11-9-4-6 6Zm30-9 9 15-10-5-8 7Z" fill="#95b76b"/><path d="m27 82 38-48m8 48L36 34" stroke="#465e46" stroke-width="7" stroke-linecap="round"/><path d="m59 35 12-15 6 13-12 7ZM27 35 18 19l-6 12 13 10" fill="#fff9e9"/><path d="M26 84h48" stroke="#f0ffd5" stroke-width="5" stroke-linecap="round"/>'
};
export function teamLogo(id,size='md'){
 const t=resolveTeam(id),color=t?.color??'#8aa4bf',kind=t?.kind??'trophy';
 const label=t?.name??'League team';
 return '<svg class="club-emblem club-emblem--'+x(size)+'" viewBox="0 0 100 100" role="img" aria-label="'+x(label)+' custom crest" focusable="false">'+
 '<circle cx="50" cy="50" r="48" fill="#0b1727" stroke="'+color+'" stroke-opacity=".72" stroke-width="2"/>'+
 '<circle cx="50" cy="50" r="42" fill="'+color+'" fill-opacity=".18" stroke="#e5faff" stroke-opacity=".17"/>'+
 '<circle cx="50" cy="50" r="36" fill="'+color+'" fill-opacity=".17"/>'+
 '<path d="M11 52a39 39 0 0 1 22-35M88 48a39 39 0 0 1-22 35" stroke="'+color+'" stroke-opacity=".75" stroke-width="2.5" fill="none" stroke-linecap="round"/>'+
 (marks[kind]||marks.trophy)+'</svg>';
}
export function uiIcon(kind){
 const paths={
 home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-7h6v7"/>',
 lineup:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M8 9h8M8 14h5"/>',
 waivers:'<path d="M4 19h16M4 13h11M4 7h6"/><path d="m16 4 4 3-4 3"/>',
 league:'<path d="M8 21h8M12 17v4M7 3h10v6a5 5 0 0 1-10 0Z"/><path d="M7 6H4a3 3 0 0 0 3 5m10-5h3a3 3 0 0 1-3 5"/>',
 refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5 10a7 7 0 0 1 12-3l3 5M4 12l3 5a7 7 0 0 0 12-3"/>',
 chevron:'<path d="m9 18 6-6-6-6"/>',
 arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 info:'<circle cx="12" cy="12" r="10"/><path d="M12 11v6m0-10h.01"/>'
 };
 return '<svg class="ui-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+(paths[kind]||paths.info)+'</svg>';
}
export function leagueGallery(){
 return '<section class="panel league-gallery"><div class="panelhead"><div><div class="label">THE LEAGUE</div><h2>All eight clubs</h2></div><span class="mini-pill">2026 SEASON</span></div><div class="club-grid">'+
 LEAGUE_TEAMS.map(t=>'<article class="club-tile'+(t.id==='2'?' club-tile--me':'')+'" style="--club-color:'+t.color+'">'+
 teamLogo(t.id,'lg')+'<strong>'+x(t.short)+'</strong><span>'+(t.id==='2'?'YOUR TEAM':'LEAGUE OPPONENT')+'</span></article>').join('')+
 '</div><p class="caption-note">Custom crests identify the eight Yahoo league teams. They are not Yahoo-uploaded team avatars. Opponent records are not included in this Brock-only capture.</p></section>';
}
export function upcomingCards(team,week){
 const rows=(Array.isArray(team.upcomingMatchups)?team.upcomingMatchups:[]).filter(g=>g&&Number.isInteger(g.week)&&g.week>Number(week)&&typeof g.opponent==='string'&&Number.isFinite(g.myProjected)&&Number.isFinite(g.opponentProjected)).slice(0,3);
 if(!rows.length)return '<div class="quiet-empty">Next opponents have not been verified in this capture.</div>';
 return '<div class="upcoming-list">'+rows.map(g=>{
  const opp=resolveTeam(g.opponent);
  return '<div class="upcoming-card">'+teamLogo(opp?.id,'sm')+
  '<div class="upcoming-name"><span>WEEK '+g.week+'</span><strong>'+x(g.opponent)+'</strong></div>'+
  '<div class="upcoming-forecast"><strong>'+g.myProjected.toFixed(1)+' <span>–</span> '+g.opponentProjected.toFixed(1)+'</strong><small>Yahoo team projections</small></div></div>';
 }).join('')+'</div>';
}
export function teamStrip(team,week){
 const next=(team?.upcomingMatchups||[]).find(g=>g&&g.week>week&&g.opponent);
 return '<div class="mini-next">'+(next?teamLogo(resolveTeam(next.opponent)?.id,'sm')+'<div><span>NEXT UP · WEEK '+x(next.week)+'</span><strong>'+x(next.opponent)+'</strong></div>':'<span>Next matchup is not yet verified</span>')+'</div>';
}
