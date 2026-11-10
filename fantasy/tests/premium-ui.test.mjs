import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {LEAGUE_TEAMS,resolveTeam,teamLogo,uiIcon,leagueGallery,upcomingCards,teamStrip} from '../assets/league-branding.mjs';

const app=()=>readFileSync('fantasy/assets/app-v2.mjs','utf8');
const css=()=>readFileSync('fantasy/assets/premium-v3.css','utf8');

test('all eight verified 2026 Yahoo league teams have unique custom SVG mascot crests',()=>{
 assert.equal(LEAGUE_TEAMS.length,8);
 assert.deepEqual(LEAGUE_TEAMS.map(t=>t.id),['1','2','3','4','5','6','7','8']);
 assert.equal(new Set(LEAGUE_TEAMS.map(t=>t.name)).size,8);
 for(const t of LEAGUE_TEAMS){
  const svg=teamLogo(t.id,'lg');
  assert.match(svg,/<svg class="club-emblem/);
  assert.match(svg,/<path /);
  assert.match(svg,/<circle /);
  assert.match(svg,/role="img"/);
  assert.match(svg,/<\/svg>/);
  assert.doesNotMatch(svg,/<text|<image|http:|https:|onload=/);
 }
 assert.equal(new Set(LEAGUE_TEAMS.map(t=>teamLogo(t.id))).size,8);
 assert.ok(!app().includes("team.id==='brock'?'BH'"));
});
test('matchup opponents resolve to correct custom marks without fetching rival rosters',()=>{
 assert.equal(resolveTeam('470.l.290846.t.4'),null); // Requires normalized provider id, never guesses foreign id
 assert.equal(resolveTeam('4').short,'Chasing Greatness');
 assert.equal(resolveTeam('Jersey junkyard').id,'5');
 assert.equal(resolveTeam('BEEFS GAY').id,'1');
 assert.equal(resolveTeam('Josh ❤️creampies').id,'6');
 assert.equal(resolveTeam('other league'),null);
 assert.match(teamLogo('4'),/Chasing Greatness custom crest/);
 assert.match(teamLogo('2'),/Brock Hard &amp; Tee Baggin custom crest/);
});
test('eight-team gallery is branding only: no owner names, standings fiction or other owned teams',()=>{
 const g=leagueGallery();
 assert.equal((g.match(/class="club-tile/g)||[]).length,8);
 assert.equal((g.match(/role="img"/g)||[]).length,8);
 assert.match(g,/Custom crests identify/);
 assert.match(g,/YOUR TEAM/);
 assert.doesNotMatch(g,/Quick Snap|Highlight Reel|ownerId|ownerName|@|<script/);
});
test('upcoming team preview uses only real saved team-level forecasts and escapes untrusted text',()=>{
 const view=upcomingCards({upcomingMatchups:[
  {week:10,opponent:'Chasing Greatness',myProjected:125.1,opponentProjected:119.2},
  {week:11,opponent:'<img src=x onerror=alert(1)>',myProjected:130,opponentProjected:99},
  {week:12,opponent:'Jersey junkyard',myProjected:null,opponentProjected:102}
 ]},9);
 assert.equal((view.match(/class="upcoming-card"/g)||[]).length,2);
 assert.match(view,/125.1/);
 assert.match(view,/Chasing Greatness custom crest/);
 assert.doesNotMatch(view,/<img|onerror=alert\(1\)>/);
 assert.match(view,/&lt;img/);
 assert.ok(teamStrip({upcomingMatchups:[]},9).includes('not yet verified'));
});
test('premium app preserves Brock-only read-only snapshots and working client navigation',()=>{
 const a=app();
 assert.match(a,/leagueGallery\(\)/);
 assert.match(a,/premium/i.test(css())?/teamLogo\('2','display'\)/:/teamLogo/);
 assert.match(a,/waiverFilter/);
 assert.match(a,/data-filter/);
 assert.match(a,/role="tabpanel"/);
 assert.match(a,/source==='published'&&!freshness\(\)\.actionable\?archivedView\(\)/);
 assert.match(a,/preparePrivateImport\(raw/);
 assert.match(a,/cache:'no-store'/);
 assert.doesNotMatch(a,/new WebSocket|fetch\(['"]https:\/\/football\.fantasysports\.yahoo/);
 const nav=uiIcon('home')+uiIcon('lineup')+uiIcon('waivers')+uiIcon('league')+uiIcon('coach');
 assert.equal((nav.match(/<svg/g)||[]).length,5);
});
test('iPhone-sized CSS includes safe-area navigation, reduced motion, good touch targets',()=>{
 const c=css();
 assert.match(c,/safe-area-inset-bottom/);
 assert.match(c,/max-width:410px/);
 assert.match(c,/prefers-reduced-motion:reduce/);
 assert.match(c,/focus-visible/);
 assert.match(c,/min-height:44px/);
 assert.match(c,/\.club-grid/);
 const future=readFileSync('fantasy/assets/future-v1.css','utf8');
 const genius=readFileSync('fantasy/assets/genius-v1.css','utf8');
 assert.match(genius,/prefers-reduced-motion:reduce/);
 assert.match(genius,/\.genius-segments/);
 assert.match(genius,/\.genius-standing/);
 assert.match(genius,/\.genius-statgrid/);
 assert.match(future,/prefers-reduced-motion:reduce/);
 assert.match(future,/\.bottomnav/);
 assert.match(future,/\.teamhero/);
 assert.match(future,/\.edge-hero/);
 assert.match(future,/\.strat-card/);
 for(const path of ['fantasy/index.html','fantasy/brock/index.html']){
  const h=readFileSync(path,'utf8');
  assert.match(h,/premium-v3\.css\?v=1/);
  assert.match(h,/coach-v1\.css\?v=2/);
  assert.match(h,/edge-v1\.css\?v=1/);
  assert.match(h,/strategy-v1\.css\?v=1/);
  assert.match(h,/future-v1\.css\?v=1/);
  assert.match(h,/genius-v1\.css\?v=1/);
  assert.match(h,/app-v2\.mjs\?v=11/);
 }
});
