(() => {
  'use strict';

  const VERSION = 4;
  const DB_NAME = 'abvm-school-star-world-v4';
  const DB_STORE = 'kv';
  const STATE_KEY = 'player-state';
  const PACK_KEY = 'last-good-pack-v5';
  const CATALOG = window.ABVM_CATALOG;
  const $ = id => document.getElementById(id);
  const $$ = selector => Array.from(document.querySelectorAll(selector));
  const HAIR_STYLES = ['Bob','Puffs','Coils','Spikes','Braids','Locs','Ponytail','Bun','Fade','Pixie'];
  const HAIR_COLORS = ['#33231f','#6b3f2a','#a45a34','#d9aa66','#171717','#6d2d7e','#b83f54','#2f5d8a'];
  const SKIN_TONES = ['#f7d6c2','#edc09f','#d99b73','#bd7d55','#99613f','#71452f'];
  const BODY_SHAPES = ['Classic','Tall','Round'];
  const BUDDIES = [
    {id:'sprout',name:'Sprout',emoji:'🐶'},
    {id:'moon',name:'Moon',emoji:'🐱'},
    {id:'berry',name:'Berry',emoji:'🐰'},
    {id:'sunny',name:'Sunny',emoji:'🐥'},
  ];
  const STARTER_LOOKS = [
    {skin:1,hairStyle:0,hairColor:0,bodyShape:0,label:'Classic'},
    {skin:2,hairStyle:1,hairColor:1,bodyShape:2,label:'Puffs'},
    {skin:3,hairStyle:4,hairColor:4,bodyShape:0,label:'Braids'},
    {skin:0,hairStyle:8,hairColor:3,bodyShape:1,label:'Fade'},
    {skin:4,hairStyle:6,hairColor:2,bodyShape:1,label:'Ponytail'},
    {skin:5,hairStyle:2,hairColor:4,bodyShape:2,label:'Coils'},
  ];
  const FALLBACK_ENVELOPE = {"source":"Verified ABVM local bootstrap pack","delivery":"fallback","sourceLastSeenAt":"2026-09-17T20:48:00-04:00","pack":{"schemaVersion":2,"sourceHash":"verified-bootstrap-2026-09-17-study-homework-v5","sourceCapturedAt":"2026-09-17T20:48:00-04:00","generatedAt":"2026-09-17T20:48:00-04:00","weekLabel":"Week of September 16, 2026","summary":"Verified ABVM Grade 2 homework plus current Spelling, Reading/ELA, and Religion study material. This safe local pack keeps the app useful until the complete sanitized live school feed is available.","homework":[{"day":"Thursday","subject":"Math","task":"Math pg. 8","due":"Tonight"},{"day":"Thursday","subject":"Spelling","task":"Spelling Choice Board activity","due":"Tonight"},{"day":"Thursday","subject":"Reading","task":"Read","due":"Tonight"},{"day":"Thursday","subject":"Parent","task":"Complete forms; cover books","due":"Tonight"},{"day":"Thursday","subject":"Reading","task":"Keep Reading Log & Behavior Chart in the HW folder","due":"Ongoing"},{"day":"Thursday","subject":"Homework Folder","task":"Return everything in the HW folder","due":"Next school day"}],"reminders":["Scholastic orders are due Thursday Sept. 17","Pretzel money is due Friday Sept. 18","Stationery money ($17) is due Wednesday Sept. 23","Lego Club is Friday Sept. 25 for students who signed up","Thursday special: Gym"],"importantDates":[{"label":"Scholastic orders due","date":"Thursday Sept. 17","kind":"deadline"},{"label":"Pretzel money due","date":"Friday Sept. 18","kind":"deadline"},{"label":"Stationery money due ($17)","date":"Wednesday Sept. 23","kind":"deadline"},{"label":"Pretzel delivery","date":"Thursday Sept. 24","kind":"event"},{"label":"Lego Club","date":"Friday Sept. 25","kind":"event"},{"label":"Picture Day","date":"Thursday Oct. 1","kind":"event"},{"label":"HSA meeting","date":"Thursday Oct. 1","kind":"meeting"},{"label":"12:00 Dismissal","date":"Friday Oct. 9","kind":"schedule_change"},{"label":"No School","date":"Monday Oct. 12","kind":"holiday"}],"subjects":[{"subject":"Spelling","topics":["Skill: short e, o, u","Basic words: went, tell, pet, job, fog, not, tug, hut, tub, bun","Review words: fix, has","High-frequency words: one, or, see"],"studyNotes":["Practice hearing and spelling the short e, short o, and short u sounds."]},{"subject":"Reading / ELA","topics":["Stories: Maria Celebrates Brazil; Big Red Lollipop; A Look at Families","Sight words: put, why, blue, help, for, yellow, both, there, even, ball, or, green, how, little, one, see, sounds, funny, find, could","Phonics: short a, short i, short e, o, u","Reading comprehension: visualize; plot (beginning, middle, end); understanding characters; captions","Word structure: -s and -es to make plural nouns"],"studyNotes":["Current vocabulary words: language, culture, aside, invited, share, fair, plead, scurries."]},{"subject":"Religion","topics":["Unit 1: God Gives Us Life & Love","Chapter 2: Jesus is God’s Best Gift","Chapter 1: God is the Giver of Gifts"],"studyNotes":["Jesus is God’s greatest gift to us; he tells us about God and teaches us how to live.","Jesus gave us the new life of grace.","We are made in God’s image and likeness; we can think, choose, and love.","Trinity: 3 persons in one God — Father, Son, Holy Spirit.","We use our senses to enjoy God’s gifts.","It is our responsibility to take care of God’s gifts of creation.","We thank God for His gift of creation."]},{"subject":"Specials","topics":["Monday: Computer","Tuesday: Music, Art, Guidance","Wednesday: Mass","Thursday: Gym","Friday: Library"],"studyNotes":[]}],"vocabulary":[{"subject":"Reading / ELA","term":"language","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"culture","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"aside","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"invited","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"share","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"fair","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"plead","meaning":"Current reading vocabulary word."},{"subject":"Reading / ELA","term":"scurries","meaning":"Current reading vocabulary word."}],"questions":[{"id":"bootstrap-q1","subject":"Spelling","format":"multiple_choice","prompt":"Which word is one of this week’s basic spelling words?","choices":["tug","rain","chair"],"answer":"tug","hint":"Look for the short-u word.","explanation":"“tug” is listed as a basic spelling word.","difficulty":"easy"},{"id":"bootstrap-q2","subject":"Spelling","format":"multiple_choice","prompt":"Which word is a review word this week?","choices":["fix","fog","bun"],"answer":"fix","hint":"It is listed in the Review Words column.","explanation":"“fix” is one of the review words.","difficulty":"easy"},{"id":"bootstrap-q3","subject":"Spelling","format":"multiple_choice","prompt":"Which word is a high-frequency word this week?","choices":["see","pet","hut"],"answer":"see","hint":"It appears in the High Frequency Words list.","explanation":"“see” is listed as a high-frequency word.","difficulty":"easy"},{"id":"bootstrap-q4","subject":"Spelling","format":"multiple_choice","prompt":"Which word from the list has the short-o sound?","choices":["fog","tell","tug"],"answer":"fog","hint":"Think about the vowel sound in “fog.”","explanation":"“fog” practices the short-o sound.","difficulty":"easy"},{"id":"bootstrap-q5","subject":"Spelling","format":"multiple_choice","prompt":"Which word from the list has the short-u sound?","choices":["bun","pet","job"],"answer":"bun","hint":"Think about the vowel sound in “bun.”","explanation":"“bun” practices the short-u sound.","difficulty":"easy"},{"id":"bootstrap-q6","subject":"Reading / ELA","format":"multiple_choice","prompt":"Which title is one of the current reading stories?","choices":["Big Red Lollipop","The Very Hungry Caterpillar","Charlotte’s Web"],"answer":"Big Red Lollipop","hint":"It is one of the three titles shown on the reading page.","explanation":"“Big Red Lollipop” is one of the current stories.","difficulty":"easy"},{"id":"bootstrap-q7","subject":"Reading / ELA","format":"multiple_choice","prompt":"Which word is listed as a sight word?","choices":["yellow","rabbit","window"],"answer":"yellow","hint":"It appears in the Sight Words list.","explanation":"“yellow” is one of the current sight words.","difficulty":"easy"},{"id":"bootstrap-q8","subject":"Reading / ELA","format":"multiple_choice","prompt":"What three parts of plot are listed for reading comprehension?","choices":["beginning, middle, end","first, second, third","who, what, where"],"answer":"beginning, middle, end","hint":"Think about the order of a story.","explanation":"The page lists plot as beginning, middle, and end.","difficulty":"easy"},{"id":"bootstrap-q9","subject":"Reading / ELA","format":"multiple_choice","prompt":"Which skill is listed under Reading Comprehension?","choices":["visualize","multiply","measure"],"answer":"visualize","hint":"It means making a picture in your mind while reading.","explanation":"“visualize” is listed as a reading-comprehension skill.","difficulty":"easy"},{"id":"bootstrap-q10","subject":"Reading / ELA","format":"multiple_choice","prompt":"What do -s and -es make, according to the Word Structure section?","choices":["plural nouns","past-tense verbs","questions"],"answer":"plural nouns","hint":"Think about making more than one noun.","explanation":"The page says -s and -es are used to make plural nouns.","difficulty":"easy"},{"id":"bootstrap-q11","subject":"Reading / ELA","format":"multiple_choice","prompt":"Which word is on the current vocabulary list?","choices":["culture","planet","triangle"],"answer":"culture","hint":"It appears under Vocab Words.","explanation":"“culture” is one of the listed vocabulary words.","difficulty":"easy"},{"id":"bootstrap-q12","subject":"Reading / ELA","format":"multiple_choice","prompt":"Which phonics sound is listed for practice?","choices":["short i","long oo only","silent e only"],"answer":"short i","hint":"The page lists several short-vowel sounds.","explanation":"Short i is one of the phonics skills listed.","difficulty":"easy"},{"id":"bootstrap-q13","subject":"Religion","format":"multiple_choice","prompt":"What is the title of Unit 1?","choices":["God Gives Us Life & Love","People Build Cities","The Seasons Change"],"answer":"God Gives Us Life & Love","hint":"It appears at the top of the Religion study page.","explanation":"Unit 1 is “God Gives Us Life & Love.”","difficulty":"easy"},{"id":"bootstrap-q14","subject":"Religion","format":"multiple_choice","prompt":"Who is described as God’s greatest gift to us?","choices":["Jesus","Moses","David"],"answer":"Jesus","hint":"Look at Chapter 2: God’s Best Gift.","explanation":"The study guide says Jesus is God’s greatest gift to us.","difficulty":"easy"},{"id":"bootstrap-q15","subject":"Religion","format":"multiple_choice","prompt":"What new life did Jesus give us?","choices":["the new life of grace","a new school year","a new language"],"answer":"the new life of grace","hint":"The word begins with g.","explanation":"The study guide says Jesus gave us the new life of grace.","difficulty":"easy"},{"id":"bootstrap-q16","subject":"Religion","format":"multiple_choice","prompt":"Being made in God’s image and likeness means we can…","choices":["think, choose, and love","fly, swim, and dig","sleep, eat, and run"],"answer":"think, choose, and love","hint":"The study guide lists three abilities.","explanation":"It says we can think, choose, and love.","difficulty":"easy"},{"id":"bootstrap-q17","subject":"Religion","format":"multiple_choice","prompt":"How many persons are in the Trinity?","choices":["3","2","4"],"answer":"3","hint":"Father, Son, and Holy Spirit.","explanation":"The study guide says the Trinity is 3 persons in one God.","difficulty":"easy"},{"id":"bootstrap-q18","subject":"Religion","format":"multiple_choice","prompt":"Which three persons are named in the Trinity?","choices":["Father, Son, Holy Spirit","Abraham, Isaac, Jacob","Peter, James, John"],"answer":"Father, Son, Holy Spirit","hint":"They are the three persons in one God.","explanation":"The page names Father, Son, and Holy Spirit.","difficulty":"easy"},{"id":"bootstrap-q19","subject":"Religion","format":"multiple_choice","prompt":"What do we use to enjoy God’s gifts?","choices":["our senses","only our eyes","a computer"],"answer":"our senses","hint":"Think about sight, hearing, touch, smell, and taste.","explanation":"The study guide says we use our senses to enjoy God’s gifts.","difficulty":"easy"},{"id":"bootstrap-q20","subject":"Religion","format":"multiple_choice","prompt":"What responsibility is listed in the study guide?","choices":["take care of God’s gifts of creation","own every gift","never go outside"],"answer":"take care of God’s gifts of creation","hint":"It is about caring for creation.","explanation":"The study guide says it is our responsibility to take care of God’s gifts of creation.","difficulty":"easy"},{"id":"bootstrap-q21","subject":"Religion","format":"multiple_choice","prompt":"What do we thank God for?","choices":["His gift of creation","homework folders","school buses"],"answer":"His gift of creation","hint":"It is the last point on the Religion study guide.","explanation":"The guide says we thank God for His gift of creation.","difficulty":"easy"}],"sourceSufficient":true,"gaps":["The automatic private-site sync is still preferred when it completes cleanly. This bootstrap contains only school material directly verified from the saved ABVM homework data and the current screenshots."]}};

  const DEFAULT_STATE = {
    version:VERSION,
    firstRun:true,
    coins:100,
    leagueStars:0,
    lifetimeCoins:100,
    ownedItemIds:[],
    equippedBySlot:{},
    favoriteItemIds:[],
    wishItemId:null,
    savedLooks:[],
    avatar:{skin:1,hairStyle:0,hairColor:0,bodyShape:0},
    companionBase:'sprout',
    sound:{tts:true,sfx:true,autoAdvance:true},
    homeworkDone:{},
    stats:{attempts:0,independent:0,supported:0,modeled:0,correct:0,comebackWins:0,bySubject:{}},
    questionHistory:{},
    comebackQueue:[],
    zoneProgress:{garden:0,story:0,lantern:0},
    roomPlacements:{},
    deliveryQueue:[],
    questSession:null,
    migration:{legacyTickets:0,legacyOwnedIds:[],done:false},
  };

  let state = structuredClone(DEFAULT_STATE);
  let packEnvelope = null;
  let pack = null;
  let currentTab = 'home';
  let activeCatalogCollection = 'tops';
  let activeCatalogFilter = 'all';
  let questRuntime = null;
  let autoTimer = null;
  let autoTick = null;
  let gateAnswer = 56;
  let audioContext = null;

  function clone(v){ return JSON.parse(JSON.stringify(v)); }
  function usableEnvelope(envelope){ return Boolean(envelope?.pack && envelope.pack.sourceSufficient===true && Array.isArray(envelope.pack.questions) && envelope.pack.questions.some(q=>q&&q.prompt&&q.answer)); }
  function safe(v){ return typeof v === 'string' ? v : ''; }
  function catalogItem(id){ return CATALOG.items.find(item => item.id === id) || null; }
  function itemOwned(id){ return state.ownedItemIds.includes(id); }
  function pct(n,d){ return d > 0 ? Math.max(0,Math.min(100,(n/d)*100)) : 0; }
  function escapeXml(value){ return String(value ?? '').replace(/[<>&"']/g,ch=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[ch])); }

  function openDb(){
    return new Promise((resolve,reject)=>{
      if(!('indexedDB' in window)) return reject(new Error('IndexedDB unavailable'));
      const req=indexedDB.open(DB_NAME,1);
      req.onupgradeneeded=()=>{ if(!req.result.objectStoreNames.contains(DB_STORE)) req.result.createObjectStore(DB_STORE); };
      req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error);
    });
  }
  async function dbGet(key){
    try{ const db=await openDb(); return await new Promise((resolve,reject)=>{const tx=db.transaction(DB_STORE,'readonly');const req=tx.objectStore(DB_STORE).get(key);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);}); }
    catch{ try{return JSON.parse(localStorage.getItem(`abvm-v4-${key}`)||'null');}catch{return null;} }
  }
  async function dbSet(key,value){
    try{ const db=await openDb(); await new Promise((resolve,reject)=>{const tx=db.transaction(DB_STORE,'readwrite');tx.objectStore(DB_STORE).put(value,key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);}); }
    catch{ localStorage.setItem(`abvm-v4-${key}`,JSON.stringify(value)); }
  }
  async function saveState(){ await dbSet(STATE_KEY,state); updateWallet(); }

  function migrateCandidate(raw){
    if(!raw || typeof raw !== 'object') return null;
    const migrated=clone(DEFAULT_STATE);
    migrated.firstRun = false;
    if(Number.isFinite(raw.coins)) migrated.coins=Math.max(0,raw.coins);
    if(Number.isFinite(raw.stars)) migrated.leagueStars=Math.max(0,raw.stars);
    if(Number.isFinite(raw.leagueStars)) migrated.leagueStars=Math.max(0,raw.leagueStars);
    if(Number.isFinite(raw.ticketBalance)){
      migrated.migration.legacyTickets=Math.max(0,raw.ticketBalance);
      migrated.coins += Math.max(0,raw.ticketBalance) * 20;
      migrated.lifetimeCoins += Math.max(0,raw.ticketBalance) * 20;
    }
    const knownIds=new Set(CATALOG.items.map(i=>i.id));
    const owned=Array.isArray(raw.ownedItemIds)?raw.ownedItemIds:(Array.isArray(raw.owned)?raw.owned:[]);
    migrated.ownedItemIds=owned.filter(id=>knownIds.has(id));
    migrated.migration.legacyOwnedIds=owned.filter(id=>!knownIds.has(id));
    if(raw.equippedBySlot && typeof raw.equippedBySlot==='object'){
      for(const [slot,id] of Object.entries(raw.equippedBySlot)) if(knownIds.has(id)) migrated.equippedBySlot[slot]=id;
    }
    if(Array.isArray(raw.favoriteItemIds)) migrated.favoriteItemIds=raw.favoriteItemIds.filter(id=>knownIds.has(id));
    if(typeof raw.wishItemId==='string' && knownIds.has(raw.wishItemId)) migrated.wishItemId=raw.wishItemId;
    if(Array.isArray(raw.savedLooks)) migrated.savedLooks=raw.savedLooks.slice(0,8);
    if(raw.avatar && typeof raw.avatar==='object') migrated.avatar={...migrated.avatar,...raw.avatar};
    if(raw.sound && typeof raw.sound==='object') migrated.sound={...migrated.sound,...raw.sound};
    migrated.migration.done=true;
    return migrated;
  }

  async function loadState(){
    const stored=await dbGet(STATE_KEY);
    if(stored && stored.version===VERSION){ state={...clone(DEFAULT_STATE),...stored}; return; }
    const legacyKeys=['abvm_school_star_world_v2','abvm_school_star_world_v1','abvm-grade2-player-v3'];
    for(const key of legacyKeys){
      try{
        const raw=JSON.parse(localStorage.getItem(key)||'null');
        const migrated=migrateCandidate(raw);
        if(migrated){ state=migrated; await saveState(); return; }
      }catch{}
    }
    state=clone(DEFAULT_STATE); await saveState();
  }

  function updateWallet(){
    ['coinCount','catalogCoins'].forEach(id=>{ if($(id)) $(id).textContent=state.coins.toLocaleString(); });
    if($('starCount')) $('starCount').textContent=state.leagueStars.toLocaleString();
  }
  function toast(message){ const el=$('toast'); el.textContent=message; el.classList.add('show'); clearTimeout(el._timer); el._timer=setTimeout(()=>el.classList.remove('show'),1900); }
  function beep(kind='good'){
    if(!state.sound.sfx) return;
    try{
      audioContext ||= new (window.AudioContext||window.webkitAudioContext)();
      const o=audioContext.createOscillator(), g=audioContext.createGain();
      o.type='sine'; o.frequency.value=kind==='good'?660:330; g.gain.setValueAtTime(.0001,audioContext.currentTime);g.gain.exponentialRampToValueAtTime(.08,audioContext.currentTime+.01);g.gain.exponentialRampToValueAtTime(.0001,audioContext.currentTime+.18);o.connect(g).connect(audioContext.destination);o.start();o.stop(audioContext.currentTime+.2);
    }catch{}
  }

  async function fetchPack(){
    $('sourceStrip').className='source-strip loading';
    $('sourceHeadline').textContent='Checking the latest ABVM school pack…';
    $('sourceSubline').textContent='Homework, study material, dates, and reminders.';
    let envelope=null;
    try{
      const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),8000);
      const res=await fetch('../data/study-pack.json',{cache:'no-store',signal:controller.signal}); clearTimeout(timer);
      const data=await res.json().catch(()=>null);
      if(!res.ok || !usableEnvelope(data)) throw new Error(data?.error||`Source ${res.status}`);
      envelope=data;
      await dbSet(PACK_KEY,envelope);
    }catch{
      envelope=await dbGet(PACK_KEY);
      if(!usableEnvelope(envelope)) envelope=clone(FALLBACK_ENVELOPE);
      if(!envelope.delivery) envelope.delivery='cache';
    }
    setPack(envelope);
  }

  function setPack(envelope){
    packEnvelope=envelope; pack=envelope.pack;
    const live=envelope.delivery==='live' || envelope.delivery==='upstream';
    const cached=envelope.delivery==='cache' || envelope.delivery==='cached';
    $('sourceStrip').className=`source-strip ${live?'ready':cached?'cached':'fallback'}`;
    $('sourceHeadline').textContent=live?'Live ABVM school pack':cached?'Last good ABVM school pack':'Verified fallback school pack';
    const when=envelope.sourceLastSeenAt||pack.sourceCapturedAt||pack.generatedAt;
    $('sourceSubline').textContent=`${pack.weekLabel||'Current week'}${when?` · checked ${timeAgo(when)}`:''}`;
    if(state.packHash && state.packHash!==pack.sourceHash) state.homeworkDone={};
    state.packHash=pack.sourceHash; saveState(); renderAll();
  }

  function timeAgo(v){
    const t=new Date(v).getTime(); if(!Number.isFinite(t)) return '';
    const mins=Math.max(0,Math.floor((Date.now()-t)/60000));
    if(mins<1)return'just now'; if(mins<60)return`${mins}m ago`; const hrs=Math.floor(mins/60); return hrs<24?`${hrs}h ago`:`${Math.floor(hrs/24)}d ago`;
  }

  function zoneForSubject(subject=''){
    const s=subject.toLowerCase();
    if(/religion|creation|trinity|sense/.test(s)) return 'garden';
    if(/sight|spell|word|phon|vocab/.test(s)) return 'lantern';
    return 'story';
  }
  function zoneInfo(zone){
    return {
      garden:{name:'Creation Garden',icon:'✿',sub:'Religion & creation',gradient:'garden'},
      story:{name:'Story Trail',icon:'▰',sub:'Reading & vocabulary',gradient:'story'},
      lantern:{name:'Lantern Path',icon:'✦',sub:'Sight words & spelling',gradient:'lantern'},
    }[zone];
  }

  function hairMarkup(style,color){
    const c=escapeXml(color), s=style%10;
    if(s===0) return `<path d="M51 46q3-31 29-31t30 31v30H99V43q-4-17-19-17T61 43v33H51z" fill="${c}"/>`;
    if(s===1) return `<path d="M57 48q4-28 23-28t23 28" fill="none" stroke="${c}" stroke-width="16" stroke-linecap="round"/><circle cx="49" cy="32" r="14" fill="${c}"/><circle cx="111" cy="32" r="14" fill="${c}"/>`;
    if(s===2) return Array.from({length:9},(_,i)=>`<circle cx="${56+(i%5)*12}" cy="${22+Math.floor(i/5)*11}" r="10" fill="${c}"/>`).join('');
    if(s===3) return `<path d="M50 49l8-32 10 13 9-22 10 22 14-18 7 37z" fill="${c}"/>`;
    if(s===4) return `<path d="M53 50q3-30 27-30t27 30" fill="none" stroke="${c}" stroke-width="14"/><path d="M58 45q-8 24 2 47M102 45q8 24-2 47" stroke="${c}" stroke-width="7" stroke-linecap="round" stroke-dasharray="3 4"/>`;
    if(s===5) return `<path d="M52 48q4-29 28-29t28 29" fill="none" stroke="${c}" stroke-width="15"/>${[58,68,78,88,98].map((x,i)=>`<path d="M${x} 38v${46+(i%2)*8}" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`).join('')}`;
    if(s===6) return `<path d="M52 49q4-30 28-30t28 30" fill="none" stroke="${c}" stroke-width="15"/><path d="M102 31q28 8 18 38q-4 11-19 9" fill="none" stroke="${c}" stroke-width="13" stroke-linecap="round"/>`;
    if(s===7) return `<path d="M52 49q4-30 28-30t28 30" fill="none" stroke="${c}" stroke-width="15"/><circle cx="80" cy="14" r="14" fill="${c}"/>`;
    if(s===8) return `<path d="M55 45q7-24 25-24t25 24v5H55z" fill="${c}"/><path d="M58 36h44" stroke="#fff" stroke-opacity=".12" stroke-width="2"/>`;
    return `<path d="M52 48q5-27 27-27q17 0 29 20l-15-4-8-9-8 9-15 5z" fill="${c}"/>`;
  }

  function itemLayer(item,slot){
    if(!item) return '';
    const p=escapeXml(item.primary), s=escapeXml(item.secondary), i=item.index;
    if(slot==='top'){
      const neck=i%3===0?`<path d="M69 87q11 10 22 0" fill="none" stroke="${s}" stroke-width="5"/>`:'';
      const pocket=i%4===0?`<rect x="69" y="111" width="22" height="15" rx="5" fill="${s}"/>`:'';
      const zip=i%5===0?`<path d="M80 91v54" stroke="${s}" stroke-width="3"/>`:'';
      return `<path d="M51 99q12-17 29-17t29 17l-6 48H57z" fill="${p}"/>${neck}${pocket}${zip}`;
    }
    if(slot==='bottom'){
      if(i===1||i===7) return `<path d="M57 140h46l10 34H47z" fill="${p}"/><path d="M54 154h52" stroke="${s}" stroke-width="4"/>`;
      if(i===4) return `<path d="M57 136h46v46H57z" fill="${p}"/><path d="M64 136v-28h32v28" fill="none" stroke="${s}" stroke-width="7"/>`;
      return `<path d="M58 139h44l-4 49H81l-1-33-1 33H62z" fill="${p}"/><path d="M80 141v46" stroke="${s}" stroke-width="2"/>`;
    }
    if(slot==='shoes') return `<path d="M55 184q13 0 25 1v11H51q-4-8 4-12zM80 185q13-1 25-1q8 4 4 12H80z" fill="${p}"/><path d="M53 190h25M83 190h25" stroke="${s}" stroke-width="3"/>`;
    if(slot==='head'){
      const shapes=[
        `<path d="M54 34q26-18 52 0" fill="none" stroke="${p}" stroke-width="7"/><path d="M70 26l10 10 10-10" fill="none" stroke="${s}" stroke-width="5"/>`,
        `<path d="M53 35q27-22 55 0v9H53z" fill="${p}"/><path d="M80 36q16 0 28 4" stroke="${s}" stroke-width="5"/>`,
        `<path d="M56 34l9-18 14 12 13-16 12 22z" fill="${p}" stroke="${s}" stroke-width="3"/>`,
        `<path d="M58 35l7-22 11 12 8-19 10 20 10-13 2 22z" fill="${p}" stroke="${s}" stroke-width="3"/>`,
        `<path d="M52 42q4-31 28-31t28 31z" fill="${p}"/><path d="M56 33h48" stroke="${s}" stroke-width="5"/>`,
        `<path d="M56 34q24-16 48 0" fill="none" stroke="${p}" stroke-width="7"/><circle cx="80" cy="24" r="9" fill="${s}"/>`,
        `<path d="M53 31q27-15 54 0v16H53z" fill="${p}"/><circle cx="80" cy="26" r="6" fill="${s}"/>`,
        `<path d="M52 37q28-12 56 0" stroke="${p}" stroke-width="8"/><path d="M80 34v15" stroke="${s}" stroke-width="4"/>`,
        `<path d="M52 34q28-11 56 0" stroke="${p}" stroke-width="7"/><rect x="52" y="35" width="13" height="21" rx="6" fill="${s}"/><rect x="95" y="35" width="13" height="21" rx="6" fill="${s}"/>`,
        `<path d="M54 33q26-13 52 0" stroke="${p}" stroke-width="6"/>${[62,74,86,98].map((x,j)=>`<circle cx="${x}" cy="29" r="4" fill="${j%2?s:p}"/>`).join('')}`,
      ]; return shapes[i%shapes.length];
    }
    if(slot==='face'){
      if(i<6) return `<rect x="57" y="51" width="20" height="13" rx="6" fill="none" stroke="${p}" stroke-width="4"/><rect x="83" y="51" width="20" height="13" rx="6" fill="none" stroke="${p}" stroke-width="4"/><path d="M77 56h6" stroke="${s}" stroke-width="3"/>`;
      return `<circle cx="60" cy="69" r="3" fill="${p}"/><circle cx="66" cy="72" r="2" fill="${s}"/><circle cx="100" cy="69" r="3" fill="${p}"/><circle cx="94" cy="72" r="2" fill="${s}"/>`;
    }
    if(slot==='back') return `<path d="M42 103q0-17 13-17h9v57H50q-9 0-9-11z" fill="${p}" stroke="${s}" stroke-width="3"/><path d="M45 105h17" stroke="${s}" stroke-width="4"/>`;
    if(slot==='hand'){
      const shapes=[`<path d="M110 117l17-30" stroke="${p}" stroke-width="5"/><path d="M127 82l4 8 9 1-7 6 2 9-8-5-8 5 2-9-7-6 9-1z" fill="${s}"/>`,`<rect x="110" y="103" width="22" height="22" rx="4" fill="${p}"/><path d="M117 103v22M125 103v22M110 111h22M110 118h22" stroke="${s}" stroke-width="2"/>`,`<path d="M111 111q11-18 22 0q-11 18-22 0z" fill="none" stroke="${p}" stroke-width="5"/>`,`<circle cx="122" cy="115" r="11" fill="${p}"/><circle cx="118" cy="112" r="2"/><circle cx="126" cy="112" r="2"/><path d="M117 119q5 5 10 0" fill="none" stroke="#fff" stroke-width="2"/>`];
      return shapes[i%shapes.length];
    }
    if(slot==='aura'){
      if(i===8) return `<path d="M43 100q-14 25 4 50" fill="none" stroke="${p}" stroke-width="4" stroke-dasharray="2 8" stroke-linecap="round"/><path d="M117 100q14 25-4 50" fill="none" stroke="${s}" stroke-width="4" stroke-dasharray="2 8" stroke-linecap="round"/>`;
      if(i===9) return `<ellipse cx="80" cy="118" rx="57" ry="88" fill="none" stroke="${p}" stroke-width="5" stroke-dasharray="12 8"/>`;
      return `<ellipse cx="80" cy="118" rx="57" ry="88" fill="none" stroke="${p}" stroke-width="5" opacity=".65"/>${[[-1,-1],[1,-1],[-1,1],[1,1]].map(([x,y],j)=>`<circle cx="${80+x*(42+j*2)}" cy="${118+y*(55-j*5)}" r="3" fill="${j%2?p:s}"/>`).join('')}`;
    }
    return '';
  }

  function avatarSvg(override={}, small=false){
    const av={...state.avatar,...(override.avatar||{})};
    const eq={...state.equippedBySlot,...(override.equippedBySlot||{})};
    const skin=SKIN_TONES[Number(av.skin)%SKIN_TONES.length];
    const hair=HAIR_COLORS[Number(av.hairColor)%HAIR_COLORS.length];
    const shape=Number(av.bodyShape)%BODY_SHAPES.length;
    const scale=shape===1?'scale(0.94 1.06) translate(5 -7)':shape===2?'scale(1.06 0.98) translate(-5 2)':'';
    const item=s=>catalogItem(eq[s]);
    const starterTop=item('top')?'':`<path d="M51 99q12-17 29-17t29 17l-6 48H57z" fill="#6255dd"/><path d="M69 110h22" stroke="#b9b2ff" stroke-width="4"/>`;
    const starterBottom=item('bottom')?'':`<path d="M58 139h44l-4 49H81l-1-33-1 33H62z" fill="#29324f"/>`;
    const starterShoes=item('shoes')?'':`<path d="M55 184q13 0 25 1v11H51q-4-8 4-12zM80 185q13-1 25-1q8 4 4 12H80z" fill="#fff" stroke="#cfd2df" stroke-width="2"/>`;
    return `<svg class="avatar-svg${small?' small':''}" viewBox="0 0 160 210" role="img" aria-label="Avatar preview">
      <g transform="${scale}">
        ${itemLayer(item('aura'),'aura')}
        ${itemLayer(item('back'),'back')}
        <circle cx="80" cy="56" r="30" fill="${skin}"/>
        ${hairMarkup(Number(av.hairStyle),hair)}
        <circle cx="69" cy="57" r="3.4" fill="#25243a"/><circle cx="91" cy="57" r="3.4" fill="#25243a"/>
        <path d="M69 72q11 9 22 0" fill="none" stroke="#9f5f5a" stroke-width="3" stroke-linecap="round"/>
        <rect x="68" y="82" width="24" height="18" rx="8" fill="${skin}"/>
        <path d="M55 101q-13 7-15 29" stroke="${skin}" stroke-width="13" stroke-linecap="round"/><path d="M105 101q13 7 15 29" stroke="${skin}" stroke-width="13" stroke-linecap="round"/>
        ${starterTop}${itemLayer(item('top'),'top')}
        ${starterBottom}${itemLayer(item('bottom'),'bottom')}
        ${starterShoes}${itemLayer(item('shoes'),'shoes')}
        ${itemLayer(item('face'),'face')}
        ${itemLayer(item('head'),'head')}
        ${itemLayer(item('hand'),'hand')}
      </g>
    </svg>`;
  }

  function companionMarkup(id){
    const item=catalogItem(id); if(item?.slot==='companion') return premiumCompanionSvg(item);
    const base=BUDDIES.find(b=>b.id===id)||BUDDIES[0];
    return `<div class="buddy-avatar" aria-label="${escapeXml(base.name)}">${base.emoji}</div>`;
  }
  function premiumCompanionSvg(item){
    const p=escapeXml(item.primary), s=escapeXml(item.secondary), i=item.index;
    const ears=i%3===0?`<path d="M18 22L10 5l19 10M62 22L70 5 51 15" fill="${p}"/>`:i%3===1?`<path d="M20 17q-10-16-14-4t13 16M60 17q10-16 14-4T61 29" fill="${p}"/>`:'';
    return `<svg class="buddy-svg" viewBox="0 0 80 80" role="img" aria-label="${escapeXml(item.name)}">${ears}<ellipse cx="40" cy="45" rx="28" ry="25" fill="${p}"/><circle cx="31" cy="42" r="3"/><circle cx="49" cy="42" r="3"/><path d="M34 53q6 5 12 0" fill="none" stroke="${s}" stroke-width="3"/><circle cx="40" cy="33" r="6" fill="${s}" opacity=".75"/></svg>`;
  }

  function currentCompanion(){ return state.equippedBySlot.companion || state.companionBase; }

  function roomObjectSvg(item){
    const p=escapeXml(item.primary), s=escapeXml(item.secondary), i=item.index;
    if(item.collectionId==='wall'){
      const motif=['★','☁','✿','☾','◷','▣','♫','✦','♥','A+'][i];
      return `<svg viewBox="0 0 90 90"><rect x="10" y="12" width="70" height="62" rx="8" fill="${p}"/><rect x="16" y="18" width="58" height="50" rx="6" fill="${s}"/><text x="45" y="53" text-anchor="middle" font-size="28" fill="#fff">${motif}</text></svg>`;
    }
    if(item.collectionId==='furniture'){
      const shapes=[`<path d="M34 72V38M54 72V38" stroke="${s}" stroke-width="6"/><circle cx="44" cy="30" r="20" fill="${p}"/>`,`<path d="M31 70V31h26v39" fill="${p}"/><path d="M44 18v15" stroke="${s}" stroke-width="5"/><circle cx="44" cy="14" r="9" fill="${s}"/>`,`<path d="M20 60q3-27 24-27t24 27v14H20z" fill="${p}"/><rect x="27" y="48" width="34" height="18" rx="7" fill="${s}"/>`,`<rect x="18" y="45" width="54" height="12" rx="5" fill="${p}"/><path d="M25 56v24M65 56v24" stroke="${s}" stroke-width="6"/>`,`<rect x="18" y="22" width="54" height="58" rx="5" fill="${p}"/><path d="M20 42h50M20 61h50" stroke="${s}" stroke-width="5"/>`];
      return `<svg viewBox="0 0 90 90">${shapes[i%shapes.length]}</svg>`;
    }
    const bedShapes=[`<ellipse cx="45" cy="59" rx="32" ry="16" fill="${p}"/><ellipse cx="45" cy="55" rx="23" ry="9" fill="${s}"/>`,`<path d="M10 62q35-22 70 0v18H10z" fill="${p}"/><path d="M18 62q27-14 54 0" stroke="${s}" stroke-width="6"/>`,`<rect x="13" y="28" width="64" height="45" rx="8" fill="${p}"/><path d="M18 40h54M18 55h54" stroke="${s}" stroke-width="5"/>`];
    return `<svg viewBox="0 0 90 90">${bedShapes[i%bedShapes.length]}</svg>`;
  }

  function itemPreviewSvg(item){
    if(item.type==='room') return `<div class="room-thumb">${roomObjectSvg(item)}</div>`;
    if(item.type==='companion') return `<div class="avatar-thumb buddy-thumb">${premiumCompanionSvg(item)}</div>`;
    const override={equippedBySlot:{[item.slot]:item.id}};
    return `<div class="avatar-thumb">${avatarSvg(override,true)}</div>`;
  }

  function renderAll(){
    if(!pack) return;
    updateWallet(); renderHome(); renderQuestLobby(); renderStudy(); renderAvatar(); renderCatalog();
  }

  function renderHome(){
    $('homeGreeting').textContent='Ready for your school world!';
    $('homeWeek').textContent=`${pack.weekLabel||'Current week'} · ${pack.summary||'Practice the latest ABVM material.'}`;
    renderDream(); renderHomeScene(); renderPortals(); renderHomework(); renderReminders(); renderDelivery();
    $('playQuestButton').disabled=!(pack.questions?.length);
  }

  function renderDream(){
    const item=catalogItem(state.wishItemId);
    if(!item){ $('dreamName').textContent='Pick something in the Catalog'; $('dreamFill').style.width='0%'; $('dreamProgress').textContent='No goal yet'; return; }
    const progress=Math.min(state.coins,item.priceCoins);
    $('dreamName').textContent=item.name; $('dreamFill').style.width=`${pct(progress,item.priceCoins)}%`; $('dreamProgress').textContent=`${progress} / ${item.priceCoins} coins`;
    if($('questDreamFill')) $('questDreamFill').style.width=`${pct(progress,item.priceCoins)}%`;
    if($('questDreamText')) $('questDreamText').textContent=`${Math.round(pct(progress,item.priceCoins))}%`;
  }

  function renderHomeScene(){
    const placements=Object.entries(state.roomPlacements||{}).map(([slot,id])=>({slot,item:catalogItem(id)})).filter(x=>x.item);
    $('homeScene').innerHTML=`<div class="room-backdrop"><div class="window-shape"><span></span><span></span><span></span><span></span></div><div class="base-bed"><span></span></div><div class="base-rug"></div><div class="room-avatar">${avatarSvg()}</div><div class="room-buddy">${companionMarkup(currentCompanion())}</div>${placements.map(({slot,item})=>`<div class="placed-item slot-${slot}" title="${escapeXml(item.name)}">${roomObjectSvg(item)}</div>`).join('')}</div>`;
  }

  function renderPortals(){
    const root=$('portalRow'); root.replaceChildren();
    ['garden','story','lantern'].forEach(zone=>{
      const info=zoneInfo(zone), xp=state.zoneProgress[zone]||0, level=Math.floor(xp/5)+1, within=xp%5;
      const b=document.createElement('button');b.type='button';b.className=`portal-card ${info.gradient}`;
      b.innerHTML=`<span class="portal-icon">${info.icon}</span><span><b>${info.name}</b><small>${info.sub}</small></span><span class="portal-level">Lv ${level}<i><em style="width:${(within/5)*100}%"></em></i></span>`;
      b.addEventListener('click',()=>{showTab('quest');startQuest(zone);}); root.append(b);
    });
  }

  function renderHomework(){
    const root=$('homeworkList'); root.replaceChildren(); const list=Array.isArray(pack.homework)?pack.homework:[];
    if(!list.length){ const d=document.createElement('div');d.className='empty';d.textContent='No homework is explicitly listed in the current source.';root.append(d);$('homeworkProgress').textContent='0 listed';return; }
    let done=0;
    list.forEach((h,i)=>{
      const key=`${pack.sourceHash}:${i}:${h.task}`; const row=document.createElement('label');row.className='task-row';
      const input=document.createElement('input');input.type='checkbox';input.checked=!!state.homeworkDone[key]; if(input.checked)done++;
      const content=document.createElement('span'); const main=document.createElement('strong');main.textContent=h.task; const meta=document.createElement('small');meta.textContent=[h.subject,h.day,h.due].filter(Boolean).join(' · ');content.append(main,meta);row.append(input,content);root.append(row);
      input.addEventListener('change',async()=>{state.homeworkDone[key]=input.checked;await saveState();renderHomework();});
    });
    $('homeworkProgress').textContent=`${done}/${list.length} done`;
  }

  function renderReminders(){
    const root=$('reminderList'); root.replaceChildren(); const list=Array.isArray(pack.reminders)?pack.reminders:[];
    if(!list.length){const d=document.createElement('div');d.className='empty';d.textContent='No reminders are listed.';root.append(d);return;}
    list.forEach(text=>{const d=document.createElement('div');d.className='reminder-row';d.innerHTML='<span>•</span>';const p=document.createElement('p');p.textContent=text;d.append(p);root.append(d);});
  }

  function renderDelivery(){
    const root=$('deliveryArea');root.replaceChildren();
    const queue=(state.deliveryQueue||[]).map(catalogItem).filter(Boolean);
    if(!queue.length){const d=document.createElement('div');d.className='delivery-empty';d.innerHTML='<span>✓</span><p>No packages waiting. Room items you buy will arrive here.</p>';root.append(d);return;}
    queue.slice(0,3).forEach(item=>{const b=document.createElement('button');b.className='package-row';b.type='button';b.innerHTML=`<span>📦</span><span><b>${escapeXml(item.name)}</b><small>Tap to open</small></span>`;b.addEventListener('click',()=>openDelivery(item));root.append(b);});
  }

  function renderQuestLobby(){
    const root=$('questModes');root.replaceChildren();
    [
      {id:'mixed',icon:'★',name:'School Star Quest',sub:'A smart mix from this week'},
      {id:'story',icon:'▰',name:'Story Trail',sub:'Reading-themed adventure'},
      {id:'garden',icon:'✿',name:'Creation Garden',sub:'Religion-themed adventure'},
      {id:'lantern',icon:'✦',name:'Lantern Path',sub:'Words-themed adventure'},
    ].forEach(mode=>{const b=document.createElement('button');b.type='button';b.className=`quest-mode ${mode.id}`;b.innerHTML=`<span>${mode.icon}</span><div><b>${mode.name}</b><small>${mode.sub}</small></div><em>Play →</em>`;b.addEventListener('click',()=>startQuest(mode.id));root.append(b);});
    const tests=(pack.importantDates||[]).filter(d=>/test|quiz|assessment/i.test(`${d.kind} ${d.label}`));
    const card=$('testReadyCard');
    if(tests.length){card.classList.remove('hidden');card.innerHTML=`<div><span class="eyebrow">TEST-READY QUEST</span><b>${escapeXml(tests[0].label)}</b><small>${escapeXml(tests[0].date)}</small></div><button id="startTestReady" class="button primary" type="button">Practice</button>`;$('startTestReady').addEventListener('click',()=>startQuest('test-ready'));}
    else card.classList.add('hidden');
    if(state.questSession && !state.questSession.complete){$('resumeQuestCard').classList.remove('hidden');$('resumeQuestText').textContent=`Question ${state.questSession.index+1} of ${state.questSession.questionIds.length}`;} else $('resumeQuestCard').classList.add('hidden');
  }

  function historyFor(qid){ return state.questionHistory[qid] || {attempts:0,correct:0,independent:0,lastAt:0}; }
  function scoreQuestion(q,mode){
    const h=historyFor(q.id), subject=state.stats.bySubject[q.subject]||{attempts:0,independent:0};
    const accuracy=subject.attempts?subject.independent/subject.attempts:.45;
    let score=(1-accuracy)*6 + Math.min(3,h.attempts===0?2:0) + Math.min(2,(Date.now()-(h.lastAt||0))/(1000*60*60*24));
    if(state.comebackQueue.includes(q.id)) score+=6;
    const zone=zoneForSubject(q.subject);
    if(['garden','story','lantern'].includes(mode) && zone===mode) score+=2;
    if(mode==='test-ready') score+=1;
    return score;
  }
  function chooseQuest(mode='mixed'){
    const all=(pack.questions||[]).filter(q=>q && q.id && q.prompt && q.answer);
    const unique=[...new Map(all.map(q=>[q.id,q])).values()];
    unique.sort((a,b)=>scoreQuestion(b,mode)-scoreQuestion(a,mode));
    const selected=[]; const skillCounts={};
    for(const q of unique){
      const key=q.subject||'Practice', count=skillCounts[key]||0;
      const max=unique.length>=3?2:5; if(count>=max && selected.length<4) continue;
      selected.push(q);skillCounts[key]=count+1;if(selected.length===5)break;
    }
    if(selected.length<5){for(const q of unique){if(!selected.some(x=>x.id===q.id))selected.push(q);if(selected.length===5)break;}}
    return selected;
  }

  async function startQuest(mode='mixed'){
    const qs=chooseQuest(mode); if(!qs.length){toast('No safe practice questions are available yet.');return;}
    questRuntime={mode,questions:qs,index:0,attempts:0,hintLevel:0,ttsUsed:false,resolved:false,rewards:0,independent:0,supported:0,modeled:0,startAt:Date.now(),interaction:null};
    state.questSession={mode,questionIds:qs.map(q=>q.id),index:0,complete:false}; await saveState();
    showTab('quest');showQuestStage();renderQuestion();
  }

  async function resumeQuest(){
    if(!state.questSession)return;
    const ids=state.questSession.questionIds||[]; const lookup=new Map((pack.questions||[]).map(q=>[q.id,q])); const qs=ids.map(id=>lookup.get(id)).filter(Boolean);
    if(!qs.length){state.questSession=null;await saveState();renderQuestLobby();return;}
    questRuntime={mode:state.questSession.mode||'mixed',questions:qs,index:Math.min(state.questSession.index||0,qs.length-1),attempts:0,hintLevel:0,ttsUsed:false,resolved:false,rewards:0,independent:0,supported:0,modeled:0,startAt:Date.now(),interaction:null};
    showTab('quest');showQuestStage();renderQuestion();
  }

  function showQuestStage(){ $('questLobby').classList.add('hidden');$('questComplete').classList.add('hidden');$('questStage').classList.remove('hidden'); }
  function currentQuestion(){ return questRuntime?.questions?.[questRuntime.index]||null; }

  function renderQuestion(){
    clearAuto(); const q=currentQuestion(); if(!q){finishQuest();return;}
    questRuntime.attempts=0;questRuntime.hintLevel=0;questRuntime.ttsUsed=false;questRuntime.resolved=false;questRuntime.interaction=null;
    $('questCounter').textContent=`${questRuntime.index+1} of ${questRuntime.questions.length}`;$('questProgressFill').style.width=`${(questRuntime.index/questRuntime.questions.length)*100}%`;
    $('questionSubject').textContent=(q.subject||'Practice').toUpperCase();$('questionPrompt').textContent=q.prompt;$('feedbackBox').classList.add('hidden');$('autoAdvanceRow').classList.add('hidden');$('interactionHelp').classList.add('hidden');$('hintButton').disabled=false;$('checkButton').classList.add('hidden');
    const area=$('answerArea');area.replaceChildren();
    const format=q.format||'multiple_choice';
    if(format==='multiple_choice'||format==='true_false') renderChoice(q,area,format);
    else if(format==='short_answer'||format==='word_build') renderTextAnswer(q,area);
    else if(format==='order') renderOrder(q,area);
    else if(format==='match') renderMatch(q,area);
    else renderTextAnswer(q,area);
    renderDream();
  }

  function renderChoice(q,area,format){
    const choices=(q.choices?.length?q.choices:(format==='true_false'?['True','False']:[]));
    choices.forEach(choice=>{const b=document.createElement('button');b.type='button';b.className='answer-choice';b.textContent=choice;b.addEventListener('click',()=>submitAnswer(choice,b));area.append(b);});
  }
  function renderTextAnswer(q,area){
    const form=document.createElement('form');form.className='answer-form';const input=document.createElement('input');input.className='text-input';input.autocomplete='off';input.placeholder=q.format==='word_build'?'Build or type the word':'Type your answer';const b=document.createElement('button');b.type='submit';b.className='button primary';b.textContent='Check';form.append(input,b);form.addEventListener('submit',e=>{e.preventDefault();submitAnswer(input.value,b);});area.append(form);setTimeout(()=>input.focus(),20);
  }
  function renderOrder(q,area){
    const items=Array.isArray(q.items)?q.items.slice():[];questRuntime.interaction={order:items};$('interactionHelp').textContent='Put them in order, then tap Check.';$('interactionHelp').classList.remove('hidden');
    const list=document.createElement('div');list.className='order-list';
    const repaint=()=>{list.replaceChildren();questRuntime.interaction.order.forEach((text,i)=>{const row=document.createElement('div');row.className='order-row';const label=document.createElement('span');label.textContent=text;const controls=document.createElement('span');const up=document.createElement('button');up.type='button';up.textContent='↑';up.disabled=i===0;const down=document.createElement('button');down.type='button';down.textContent='↓';down.disabled=i===questRuntime.interaction.order.length-1;up.addEventListener('click',()=>{[questRuntime.interaction.order[i-1],questRuntime.interaction.order[i]]=[questRuntime.interaction.order[i],questRuntime.interaction.order[i-1]];repaint();});down.addEventListener('click',()=>{[questRuntime.interaction.order[i+1],questRuntime.interaction.order[i]]=[questRuntime.interaction.order[i],questRuntime.interaction.order[i+1]];repaint();});controls.append(up,down);row.append(label,controls);list.append(row);});};repaint();area.append(list);$('checkButton').classList.remove('hidden');
  }
  function renderMatch(q,area){
    const pairs=Array.isArray(q.pairs)?q.pairs:[];questRuntime.interaction={matches:{}};$('interactionHelp').textContent='Match each pair, then tap Check.';$('interactionHelp').classList.remove('hidden');
    const rights=pairs.map(p=>Array.isArray(p)?p[1]:p.right);pairs.forEach((pair,i)=>{const left=Array.isArray(pair)?pair[0]:pair.left;const row=document.createElement('label');row.className='match-row';const span=document.createElement('span');span.textContent=left;const sel=document.createElement('select');sel.className='select-input';const blank=document.createElement('option');blank.value='';blank.textContent='Choose…';sel.append(blank);rights.forEach(r=>{const o=document.createElement('option');o.value=r;o.textContent=r;sel.append(o);});sel.addEventListener('change',()=>questRuntime.interaction.matches[i]=sel.value);row.append(span,sel);area.append(row);});$('checkButton').classList.remove('hidden');
  }

  function normalize(v){ return String(v??'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim(); }
  function evaluateCurrentAnswer(){
    const q=currentQuestion(); if(!q)return'';
    if(q.format==='order') return (questRuntime.interaction?.order||[]).join(' | ');
    if(q.format==='match') return Object.values(questRuntime.interaction?.matches||{}).join(' | ');
    return '';
  }
  function correctFor(value){
    const q=currentQuestion();
    if(q.format==='order') return JSON.stringify(questRuntime.interaction?.order||[])===JSON.stringify(q.correctOrder||[]);
    if(q.format==='match'){
      const pairs=Array.isArray(q.pairs)?q.pairs:[];return pairs.every((pair,i)=>normalize(questRuntime.interaction?.matches?.[i])===normalize(Array.isArray(pair)?pair[1]:pair.right));
    }
    return normalize(value)===normalize(q.answer);
  }

  async function submitAnswer(value,control){
    if(!questRuntime || questRuntime.resolved)return;
    const q=currentQuestion(); const correct=correctFor(value); questRuntime.attempts++;
    $$('.answer-choice').forEach(b=>b.disabled=true);$('checkButton').disabled=true;
    if(correct){if(control?.classList)control.classList.add('correct');await resolveQuestion(true,false);return;}
    if(control?.classList)control.classList.add('wrong');beep('soft');
    if(questRuntime.attempts===1){
      showFeedback('Not yet',q.hint||'Try one more time with a clue.','encourage');questRuntime.hintLevel=Math.max(1,questRuntime.hintLevel);setTimeout(()=>unlockQuestionForRetry(),650);
    }else if(questRuntime.attempts===2){
      showFeedback('Try this clue',q.hint?`${q.hint} Look at the choices or parts again.`:'Look for the part that best matches the question.','encourage');questRuntime.hintLevel=Math.max(2,questRuntime.hintLevel);setTimeout(()=>unlockQuestionForRetry(),750);
    }else{
      await resolveQuestion(false,true);
    }
  }
  function unlockQuestionForRetry(){
    if(questRuntime?.resolved)return;$$('.answer-choice').forEach(b=>{b.disabled=false;b.classList.remove('wrong');});$('checkButton').disabled=false;$('feedbackBox').classList.add('hidden');
  }

  async function useHint(){
    if(!questRuntime||questRuntime.resolved)return;const q=currentQuestion();questRuntime.hintLevel=Math.min(2,questRuntime.hintLevel+1);showFeedback('Here’s a clue',q.hint||'Look for the answer that best matches the prompt.','hint');$('hintButton').disabled=questRuntime.hintLevel>=2;await saveQuestCheckpoint();
  }
  function useTts(){
    const q=currentQuestion(); if(!q||!state.sound.tts||!('speechSynthesis'in window))return;questRuntime.ttsUsed=true;window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(q.prompt);u.rate=.88;window.speechSynthesis.speak(u);showFeedback('Read aloud on','You can still answer normally.','hint');
  }

  function independentEvidence(q,correct){
    if(!correct || questRuntime.attempts!==1 || questRuntime.hintLevel>0)return false;
    if(questRuntime.ttsUsed && /sight|spell|word/i.test(q.subject||''))return false;
    return true;
  }

  async function resolveQuestion(correct,modeled){
    const q=currentQuestion();questRuntime.resolved=true;$('hintButton').disabled=true;$('checkButton').disabled=true;$$('.answer-choice').forEach(b=>b.disabled=true);
    const independent=independentEvidence(q,correct); const supported=correct&&!independent; const comeback=state.comebackQueue.includes(q.id)&&correct;
    let reward=2; if(independent)reward+=2; if(comeback)reward+=2;
    state.coins+=reward;state.lifetimeCoins+=reward;questRuntime.rewards+=reward;state.stats.attempts++; if(correct)state.stats.correct++; if(independent){state.stats.independent++;questRuntime.independent++;} else if(correct){state.stats.supported++;questRuntime.supported++;} if(modeled){state.stats.modeled++;questRuntime.modeled++;}
    const sub=state.stats.bySubject[q.subject]||(state.stats.bySubject[q.subject]={attempts:0,independent:0,correct:0});sub.attempts++;if(correct)sub.correct++;if(independent)sub.independent++;
    const hist=state.questionHistory[q.id]||(state.questionHistory[q.id]={attempts:0,correct:0,independent:0,lastAt:0});hist.attempts++;if(correct)hist.correct++;if(independent)hist.independent++;hist.lastAt=Date.now();
    if(!correct||modeled){if(!state.comebackQueue.includes(q.id))state.comebackQueue.push(q.id);}else if(comeback){state.comebackQueue=state.comebackQueue.filter(id=>id!==q.id);state.stats.comebackWins++;}
    const zone=zoneForSubject(q.subject);state.zoneProgress[zone]=(state.zoneProgress[zone]||0)+1;
    await saveState();renderPortals();renderDream();updateWallet();
    const title=correct?(comeback?'Comeback win!':'Nice work!'):'Here’s the model answer';
    const text=correct?`${q.explanation||`The answer is ${q.answer}.`} +${reward} Coins`:`The answer is ${q.answer}. ${q.explanation||''} +${reward} Coins for finishing the learning step.`;
    showFeedback(title,text,correct?'success':'model');beep(correct?'good':'soft');startAutoAdvance();
  }

  function showFeedback(title,text,type){
    $('feedbackTitle').textContent=title;$('feedbackText').textContent=text;$('companionReaction').innerHTML=companionMarkup(currentCompanion());$('feedbackBox').className=`feedback-box ${type}`;
  }

  function clearAuto(){clearTimeout(autoTimer);clearInterval(autoTick);autoTimer=null;autoTick=null;}
  function startAutoAdvance(){
    $('autoAdvanceRow').classList.remove('hidden');
    if(!state.sound.autoAdvance){$('autoAdvanceText').textContent='Take your time.';return;}
    let seconds=2;$('autoAdvanceText').textContent=`Next in ${seconds}…`;
    autoTick=setInterval(()=>{seconds--;if(seconds>0)$('autoAdvanceText').textContent=`Next in ${seconds}…`;},1000);
    autoTimer=setTimeout(()=>advanceQuest(),2100);
  }
  function moreTime(){clearAuto();$('autoAdvanceText').textContent='More time added.';autoTimer=setTimeout(()=>advanceQuest(),8000);}
  async function advanceQuest(){
    clearAuto();if(!questRuntime)return;questRuntime.index++;state.questSession.index=questRuntime.index;await saveState();if(questRuntime.index>=questRuntime.questions.length)finishQuest();else renderQuestion();
  }
  async function saveQuestCheckpoint(){if(state.questSession){state.questSession.index=questRuntime?.index||0;await saveState();}}
  async function pauseQuest(){clearAuto();await saveQuestCheckpoint();questRuntime=null;$('questStage').classList.add('hidden');$('questLobby').classList.remove('hidden');renderQuestLobby();toast('Quest saved.');}

  async function finishQuest(){
    clearAuto();if(!questRuntime)return;state.coins+=5;state.lifetimeCoins+=5;state.leagueStars+=1;questRuntime.rewards+=5;state.questSession.complete=true;await saveState();
    $('questStage').classList.add('hidden');$('questLobby').classList.add('hidden');$('questComplete').classList.remove('hidden');
    $('questCompleteSummary').textContent=`You finished ${questRuntime.questions.length} learning steps and earned ${questRuntime.rewards} Coins.`;
    const highlights=$('questHighlights');highlights.replaceChildren();[
      ['★','Independent',questRuntime.independent],['↗','Supported',questRuntime.supported],['↺','Modeled',questRuntime.modeled],['●','Coins',questRuntime.rewards]
    ].forEach(([icon,label,value])=>{const d=document.createElement('div');d.className='highlight';d.innerHTML=`<span>${icon}</span><b>${value}</b><small>${label}</small>`;highlights.append(d);});
    state.questSession=null;await saveState();renderAll();
  }

  function renderStudy(){
    $('studyTitle').textContent=pack.weekLabel||'Current week';$('studyFreshness').textContent=packEnvelope.delivery==='fallback'?'Verified fallback':'Current';
    renderAssessments(); const root=$('subjectGuides');root.replaceChildren();
    (pack.subjects||[]).forEach((s,i)=>{const card=document.createElement('article');card.className='study-guide-card';const topics=[...(s.topics||[]),...(s.studyNotes||[])];card.innerHTML=`<div class="guide-icon">${['Aa','123','✿','★'][i%4]}</div><div><h2>${escapeXml(s.subject||'Study')}</h2><ul>${topics.map(t=>`<li>${escapeXml(t)}</li>`).join('')}</ul></div>`;root.append(card);});
    if(!(pack.subjects||[]).length){const d=document.createElement('div');d.className='empty';d.textContent='No study topics are available in the current source.';root.append(d);}
    const vocab=$('vocabList');vocab.replaceChildren();(pack.vocabulary||[]).forEach(v=>{const d=document.createElement('div');d.className='vocab-card-item';const b=document.createElement('b');b.textContent=v.term;const s=document.createElement('span');s.textContent=v.meaning;const m=document.createElement('small');m.textContent=v.subject||'';d.append(b,s,m);vocab.append(d);});if(!(pack.vocabulary||[]).length){const d=document.createElement('div');d.className='empty';d.textContent='No vocabulary is explicitly listed.';vocab.append(d);}
    renderStudyPractice();
  }
  function renderAssessments(){
    const root=$('assessmentArea');root.replaceChildren();const tests=(pack.importantDates||[]).filter(d=>/test|quiz|assessment/i.test(`${d.kind} ${d.label}`));
    if(!tests.length){const d=document.createElement('div');d.className='assessment-none';d.innerHTML='<span>✓</span><div><b>No upcoming test is identified in the current source.</b><small>Study Guides still follow the current school material.</small></div>';root.append(d);return;}
    tests.slice(0,3).forEach((t,i)=>{const d=document.createElement('article');d.className=`assessment-card ${i===0?'nearest':''}`;d.innerHTML=`<div class="eyebrow">${i===0?'NEXT ASSESSMENT':'UPCOMING'}</div><h2>${escapeXml(t.label)}</h2><p>${escapeXml(t.date)}</p><button class="button soft" type="button">Practice Test-Ready Quest</button>`;d.querySelector('button').addEventListener('click',()=>{showTab('quest');startQuest('test-ready');});root.append(d);});
  }
  function renderStudyPractice(){
    const root=$('studyPractice');root.replaceChildren();const qs=(pack.questions||[]).slice(0,6);if(!qs.length){const d=document.createElement('div');d.className='empty';d.textContent='No practice questions are available.';root.append(d);return;}
    qs.forEach((q,i)=>{const d=document.createElement('article');d.className='practice-row';const top=document.createElement('div');top.innerHTML=`<span>${i+1}</span><b>${escapeXml(q.prompt)}</b>`;const answer=document.createElement('div');answer.className='practice-answer hidden';answer.textContent=`Answer: ${q.answer}${q.explanation?` — ${q.explanation}`:''}`;const b=document.createElement('button');b.type='button';b.className='text-button';b.textContent='Reveal answer';b.addEventListener('click',()=>{answer.classList.toggle('hidden');b.textContent=answer.classList.contains('hidden')?'Reveal answer':'Hide answer';});d.append(top,b,answer);root.append(d);});
  }

  function renderAvatar(){
    $('avatarStage').innerHTML=`<div class="avatar-stage-inner">${avatarSvg()}<div class="stage-buddy">${companionMarkup(currentCompanion())}</div></div>`;
    renderAvatarChoices();renderEquipped();renderSavedLooks();
  }
  function renderAvatarChoices(){
    const hair=$('hairChoices');hair.replaceChildren();HAIR_STYLES.forEach((name,i)=>{const b=document.createElement('button');b.type='button';b.className=`mini-choice ${state.avatar.hairStyle===i?'active':''}`;b.innerHTML=`<span class="hair-mini">${avatarSvg({avatar:{...state.avatar,hairStyle:i}},true)}</span><small>${name}</small>`;b.addEventListener('click',async()=>{state.avatar.hairStyle=i;await saveState();renderAvatar();renderHomeScene();renderCatalog();});hair.append(b);});
    renderSwatches('hairColorChoices',HAIR_COLORS,state.avatar.hairColor,async i=>{state.avatar.hairColor=i;await saveState();renderAvatar();renderHomeScene();renderCatalog();});
    renderSwatches('skinChoices',SKIN_TONES,state.avatar.skin,async i=>{state.avatar.skin=i;await saveState();renderAvatar();renderHomeScene();renderCatalog();});
    const body=$('bodyChoices');body.replaceChildren();BODY_SHAPES.forEach((name,i)=>{const b=document.createElement('button');b.type='button';b.className=`text-choice ${state.avatar.bodyShape===i?'active':''}`;b.textContent=name;b.addEventListener('click',async()=>{state.avatar.bodyShape=i;await saveState();renderAvatar();renderHomeScene();renderCatalog();});body.append(b);});
    const buddies=$('buddyChoices');buddies.replaceChildren();BUDDIES.forEach(bu=>{const b=document.createElement('button');b.type='button';b.className=`buddy-choice ${currentCompanion()===bu.id?'active':''}`;b.innerHTML=`<span>${bu.emoji}</span><small>${bu.name}</small>`;b.addEventListener('click',async()=>{delete state.equippedBySlot.companion;state.companionBase=bu.id;await saveState();renderAvatar();renderHomeScene();});buddies.append(b);});
  }
  function renderSwatches(rootId,colors,selected,onPick){const root=$(rootId);root.replaceChildren();colors.forEach((color,i)=>{const b=document.createElement('button');b.type='button';b.className=`swatch ${selected===i?'active':''}`;b.style.background=color;b.setAttribute('aria-label',`Color ${i+1}`);b.addEventListener('click',()=>onPick(i));root.append(b);});}
  function renderEquipped(){
    const root=$('equippedList');root.replaceChildren();const slots=['top','bottom','shoes','head','face','back','hand','aura','companion'];let any=false;slots.forEach(slot=>{const item=catalogItem(state.equippedBySlot[slot]);if(!item)return;any=true;const d=document.createElement('div');d.className='equipped-card';d.innerHTML=`${itemPreviewSvg(item)}<b>${escapeXml(item.name)}</b><small>${escapeXml(item.collectionName)}</small><button type="button">Remove</button>`;d.querySelector('button').addEventListener('click',async()=>{delete state.equippedBySlot[slot];await saveState();renderAvatar();renderHomeScene();renderCatalog();});root.append(d);});if(!any){const d=document.createElement('div');d.className='empty';d.textContent='Starter outfit equipped.';root.append(d);}
  }
  async function saveLook(){const look={id:`look-${Date.now()}`,name:`Look ${state.savedLooks.length+1}`,avatar:clone(state.avatar),equippedBySlot:clone(state.equippedBySlot),companionBase:state.companionBase};state.savedLooks=[look,...state.savedLooks].slice(0,6);await saveState();renderSavedLooks();toast('Look saved!');}
  function renderSavedLooks(){const root=$('savedLooks');root.replaceChildren();if(!state.savedLooks.length){const d=document.createElement('div');d.className='empty';d.textContent='Save an outfit to bring it back with one tap.';root.append(d);return;}state.savedLooks.forEach(look=>{const d=document.createElement('div');d.className='look-card';d.innerHTML=`<div>${avatarSvg({avatar:look.avatar,equippedBySlot:look.equippedBySlot},true)}</div><b>${escapeXml(look.name)}</b><button class="button soft" type="button">Wear</button>`;d.querySelector('button').addEventListener('click',async()=>{state.avatar=clone(look.avatar);state.equippedBySlot=clone(look.equippedBySlot);state.companionBase=look.companionBase||state.companionBase;await saveState();renderAll();toast('Look restored.');});root.append(d);});}

  function renderCatalog(){
    updateWallet(); renderDreamGoalCard(); const cats=$('catalogCategories');cats.replaceChildren();CATALOG.collections.forEach(c=>{const b=document.createElement('button');b.type='button';b.className=`category-button ${activeCatalogCollection===c.id?'active':''}`;b.innerHTML=`<span>${c.icon}</span><small>${c.name}</small>`;b.addEventListener('click',()=>{activeCatalogCollection=c.id;renderCatalog();});cats.append(b);});
    $$('.filter-chip').forEach(b=>b.classList.toggle('active',b.dataset.filter===activeCatalogFilter));
    const grid=$('catalogGrid');grid.replaceChildren();let items=CATALOG.items.filter(i=>i.collectionId===activeCatalogCollection);
    if(activeCatalogFilter==='owned')items=items.filter(i=>itemOwned(i.id));if(activeCatalogFilter==='favorites')items=items.filter(i=>state.favoriteItemIds.includes(i.id));if(activeCatalogFilter==='dream')items=items.filter(i=>i.id===state.wishItemId);
    items.forEach(item=>grid.append(buildCatalogCard(item)));if(!items.length){const d=document.createElement('div');d.className='empty catalog-empty';d.textContent='Nothing in this view yet.';grid.append(d);}
  }
  function buildCatalogCard(item){
    const owned=itemOwned(item.id), fav=state.favoriteItemIds.includes(item.id), equipped=state.equippedBySlot[item.slot]===item.id, dream=state.wishItemId===item.id;
    const card=document.createElement('article');card.className=`catalog-card ${owned?'owned':''}`;card.innerHTML=`<div class="catalog-preview">${itemPreviewSvg(item)}<button class="favorite-button ${fav?'active':''}" type="button" aria-label="Favorite">♥</button></div><div class="catalog-copy"><span>${escapeXml(item.collectionName)}</span><h3>${escapeXml(item.name)}</h3><div class="price-row"><b>${owned?'OWNED':`${item.priceCoins} coins`}</b><button class="dream-button ${dream?'active':''}" type="button">${dream?'★ Goal':'☆ Goal'}</button></div></div><button class="catalog-action button ${owned?'soft':'primary'}" type="button"></button>`;
    const favBtn=card.querySelector('.favorite-button');favBtn.addEventListener('click',async e=>{e.stopPropagation();if(fav)state.favoriteItemIds=state.favoriteItemIds.filter(id=>id!==item.id);else state.favoriteItemIds.push(item.id);await saveState();renderCatalog();});
    card.querySelector('.dream-button').addEventListener('click',async()=>{state.wishItemId=dream?null:item.id;await saveState();renderHome();renderCatalog();toast(dream?'Dream Goal cleared.':`${item.name} is your Dream Goal!`);});
    const action=card.querySelector('.catalog-action');
    if(!owned){action.textContent=state.coins>=item.priceCoins?'Buy':'Need more Coins';action.disabled=state.coins<item.priceCoins;action.addEventListener('click',()=>buyItem(item));}
    else if(item.type==='room'){action.textContent=Object.values(state.roomPlacements).includes(item.id)?'Move':'Place';action.addEventListener('click',()=>openDelivery(item,true));}
    else{action.textContent=equipped?'Equipped':'Equip';action.disabled=equipped;action.addEventListener('click',()=>equipItem(item));}
    return card;
  }
  async function buyItem(item){if(itemOwned(item.id)||state.coins<item.priceCoins)return;state.coins-=item.priceCoins;state.ownedItemIds.push(item.id);if(item.type==='room')state.deliveryQueue.push(item.id);else state.equippedBySlot[item.slot]=item.id;await saveState();renderAll();beep('good');toast(`${item.name} is yours!`);if(item.type==='room')showTab('home');}
  async function equipItem(item){state.equippedBySlot[item.slot]=item.id;await saveState();renderAll();toast(`${item.name} equipped.`);}
  function renderDreamGoalCard(){const root=$('dreamGoalCard');const item=catalogItem(state.wishItemId);if(!item){root.innerHTML='<div><span class="eyebrow">DREAM GOAL</span><b>Pick any Catalog item as your goal.</b><small>Your progress stays visible in the Room.</small></div>';return;}root.innerHTML=`${itemPreviewSvg(item)}<div><span class="eyebrow">DREAM GOAL</span><b>${escapeXml(item.name)}</b><div class="catalog-dream-meter"><i style="width:${pct(state.coins,item.priceCoins)}%"></i></div><small>${Math.min(state.coins,item.priceCoins)} / ${item.priceCoins} Coins</small></div>`;}

  function openDelivery(item,move=false){
    $('deliveryItemName').textContent=item.name;$('placementChoices').replaceChildren();const slots=item.slot==='wall'?['wall-left','wall-right']:item.slot==='bed'?['bed','floor-center']:['floor-left','floor-right','floor-center','bedside'];
    slots.forEach(slot=>{const b=document.createElement('button');b.type='button';b.className='placement-choice';b.innerHTML=`<span>${roomObjectSvg(item)}</span><b>${slot.replaceAll('-',' ')}</b>`;b.addEventListener('click',async()=>{for(const [k,v] of Object.entries(state.roomPlacements))if(v===item.id)delete state.roomPlacements[k];state.roomPlacements[slot]=item.id;state.deliveryQueue=state.deliveryQueue.filter(id=>id!==item.id);await saveState();closeModal('deliveryModal');renderAll();toast(`${item.name} placed!`);});$('placementChoices').append(b);});openModal('deliveryModal');
  }

  function renderParentPulse(){
    const root=$('parentPulse');root.replaceChildren();const stats=state.stats;const cards=[['Resolved learning steps',stats.attempts],['Independent',stats.independent],['Supported',stats.supported],['Comeback wins',stats.comebackWins],['Lifetime Coins',state.lifetimeCoins],['Owned items',state.ownedItemIds.length]];cards.forEach(([label,value])=>{const d=document.createElement('div');d.className='pulse-card';d.innerHTML=`<b>${value}</b><span>${label}</span>`;root.append(d);});
    $('settingTts').checked=!!state.sound.tts;$('settingSfx').checked=!!state.sound.sfx;$('settingAuto').checked=!!state.sound.autoAdvance;
    const legacy=state.migration;$('legacyStatus').textContent=legacy.done?`Legacy migration preserved ${legacy.legacyTickets||0} Star Tickets (${(legacy.legacyTickets||0)*20} Coins) and ${legacy.legacyOwnedIds?.length||0} unmatched legacy item IDs for recovery.`:'No legacy import has been applied on this device.';
  }

  function openParentGate(){gateAnswer=[42,48,54,56,63][Math.floor(Math.random()*5)];const pairs={42:'6 × 7',48:'6 × 8',54:'6 × 9',56:'7 × 8',63:'7 × 9'};$('gateQuestion').textContent=pairs[gateAnswer];$('gateAnswer').value='';$('gateError').textContent='';openModal('parentGate');setTimeout(()=>$('gateAnswer').focus(),100);}
  function openModal(id){$(id).classList.remove('hidden');$(id).setAttribute('aria-hidden','false');document.body.classList.add('modal-open');}
  function closeModal(id){$(id).classList.add('hidden');$(id).setAttribute('aria-hidden','true');if(!$$('.modal:not(.hidden)').length)document.body.classList.remove('modal-open');}

  function showTab(name){currentTab=name;$$('.bottom-item').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$$('.panel').forEach(p=>p.classList.remove('active'));$(`${name}Panel`).classList.add('active');if(name==='quest'){if(!questRuntime){$('questStage').classList.add('hidden');$('questComplete').classList.add('hidden');$('questLobby').classList.remove('hidden');renderQuestLobby();}}window.scrollTo({top:0,behavior:'smooth'});}

  async function clearStarterOutfit(){for(const slot of ['top','bottom','shoes','head','face','back','hand','aura'])delete state.equippedBySlot[slot];await saveState();renderAll();}

  function setupOnboarding(){
    const looks=$('starterLooks');looks.replaceChildren();STARTER_LOOKS.forEach((look,i)=>{const b=document.createElement('button');b.type='button';b.className=`starter-look ${i===0?'active':''}`;b.innerHTML=`${avatarSvg({avatar:look},true)}<b>${look.label}</b>`;b.addEventListener('click',()=>{$$('.starter-look').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.avatar={skin:look.skin,hairStyle:look.hairStyle,hairColor:look.hairColor,bodyShape:look.bodyShape};});looks.append(b);});
    const buddies=$('starterBuddies');buddies.replaceChildren();BUDDIES.forEach((bu,i)=>{const b=document.createElement('button');b.type='button';b.className=`starter-buddy ${i===0?'active':''}`;b.innerHTML=`<span>${bu.emoji}</span><b>${bu.name}</b>`;b.addEventListener('click',()=>{$$('.starter-buddy').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.companionBase=bu.id;});buddies.append(b);});
  }

  async function finishOnboarding(){state.firstRun=false;await saveState();$('onboarding').classList.add('hidden');$('onboarding').setAttribute('aria-hidden','true');$('app').classList.remove('hidden');renderAll();}

  async function exportBackup(){const payload={type:'ABVM School Star World Backup',version:VERSION,exportedAt:new Date().toISOString(),state,pack};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`abvm-school-star-backup-${new Date().toISOString().slice(0,10)}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function importBackup(file){try{const data=JSON.parse(await file.text());const candidate=data.state||data;const migrated=candidate.version===VERSION?candidate:migrateCandidate(candidate);if(!migrated)throw new Error('Unsupported backup');state={...clone(DEFAULT_STATE),...migrated,version:VERSION};await saveState();closeModal('parentModal');renderAll();toast('Game backup imported.');}catch{toast('That backup could not be imported.');}}

  function bindEvents(){
    $('refreshButton').addEventListener('click',fetchPack);$('playQuestButton').addEventListener('click',()=>{showTab('quest');startQuest('mixed');});
    $$('.bottom-item').forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
    $('resumeQuestButton').addEventListener('click',resumeQuest);$('pauseQuestButton').addEventListener('click',pauseQuest);$('ttsButton').addEventListener('click',useTts);$('hintButton').addEventListener('click',useHint);$('checkButton').addEventListener('click',()=>submitAnswer(evaluateCurrentAnswer(),$('checkButton')));$('moreTimeButton').addEventListener('click',moreTime);$('nextNowButton').addEventListener('click',advanceQuest);$('backHomeAfterQuest').addEventListener('click',()=>showTab('home'));$('anotherQuestButton').addEventListener('click',()=>{questRuntime=null;showTab('quest');});
    $('saveLookButton').addEventListener('click',saveLook);$('clearOutfitButton').addEventListener('click',clearStarterOutfit);
    $$('.filter-chip').forEach(b=>b.addEventListener('click',()=>{activeCatalogFilter=b.dataset.filter;renderCatalog();}));
    $('parentButton').addEventListener('click',openParentGate);$('parentGateForm').addEventListener('submit',e=>{e.preventDefault();if(Number($('gateAnswer').value)===gateAnswer){closeModal('parentGate');renderParentPulse();openModal('parentModal');}else $('gateError').textContent='Try again.';});
    $$('[data-close-modal]').forEach(b=>b.addEventListener('click',()=>closeModal(b.dataset.closeModal)));
    $('settingTts').addEventListener('change',async e=>{state.sound.tts=e.target.checked;await saveState();});$('settingSfx').addEventListener('change',async e=>{state.sound.sfx=e.target.checked;await saveState();});$('settingAuto').addEventListener('change',async e=>{state.sound.autoAdvance=e.target.checked;await saveState();});
    $('exportButton').addEventListener('click',exportBackup);$('importInput').addEventListener('change',e=>{const f=e.target.files?.[0];if(f)importBackup(f);e.target.value='';});$('finishOnboarding').addEventListener('click',finishOnboarding);
  }

  async function init(){
    await loadState();updateWallet();setupOnboarding();bindEvents();await fetchPack();$('boot').classList.add('hidden');
    if(state.firstRun){$('onboarding').classList.remove('hidden');$('onboarding').setAttribute('aria-hidden','false');$('app').classList.add('hidden');}
    else{$('app').classList.remove('hidden');renderAll();}
    if('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});
    setInterval(()=>fetchPack(),5*60*1000);
  }

  init().catch(err=>{console.error(err);$('boot').innerHTML='<strong>School Star World needs a refresh.</strong><span>Please reload the page.</span>';});
})();
