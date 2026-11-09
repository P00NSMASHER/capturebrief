/* Fantasy HQ private PWA bootstrap. Never sends league data or unlock secrets to a server. */
const ROOT=document.getElementById('root');
const STORAGE_KEY='fantasy-hq-phone-unlock-v1';
const AAD=new TextEncoder().encode('FantasyHQ-Phone-2026-v1');
const TEAM_KEYS=['brock','quick','highlight'];
const codec=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4)),c=>c.charCodeAt(0));
const saved=()=>{try{return localStorage.getItem(STORAGE_KEY)}catch{return null}};
const save=s=>{try{localStorage.setItem(STORAGE_KEY,s)}catch{}};
const passFromLink=()=>location.hash.match(/^#unlock=([A-Z2-9]{22})$/i)?.[1]?.toUpperCase()||null;
const escape=s=>String(s||'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
function renderLock(explanation='This dashboard is encrypted. Open the private link from ChatGPT or enter the recovery code.'){
 ROOT.innerHTML='<main class="private-gate"><div class="private-monogram">F<span>.</span></div><div class="label">PRIVATE FANTASY HQ</div><h1>Unlock your<br>fantasy dashboard.</h1><p>'+escape(explanation)+'</p><form id="privateUnlock"><label for="privateKey">RECOVERY CODE</label><input id="privateKey" type="password" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="22" placeholder="22-character code" required><button type="submit" class="private-submit">Unlock my leagues</button></form><small>Protected with AES-256-GCM. League data is decrypted only on your phone. This is a dated Flaim Fantasy snapshot, not a live connection.</small></main>';
}
function validateSnapshot(x){
 if(!x||x.schemaVersion!==3||x.week!==9||x.season!==2026||!x.syncedAtIso||!x.teams||!TEAM_KEYS.every(k=>x.teams[k]))throw Error('Invalid league snapshot');
 const leagues=TEAM_KEYS.map(k=>x.teams[k].leagueId);
 if(new Set(leagues).size!==3)throw Error('Duplicate league identities');
 return x;
}
async function unlock(pass){
 const password=String(pass||'').trim().toUpperCase().replace(/[ -]/g,'');
 if(!/^[A-Z2-9]{22}$/.test(password))throw Error('Invalid recovery code format');
 if(!crypto?.subtle||typeof DecompressionStream==='undefined')throw Error('Use an updated Safari browser');
 const res=await fetch(new URL('../vault.json',import.meta.url),{cache:'no-store'});
 if(!res.ok)throw Error('Encrypted snapshot temporarily unavailable');
 const v=await res.json();
 if(v.v!==1||v.cipher!=='AES-256-GCM'||v.encoding!=='gzip'||v.iterations<200000||v.iterations>1000000)throw Error('Unsupported encrypted snapshot');
 const keymaterial=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
 const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:codec(v.salt),iterations:v.iterations,hash:'SHA-256'},keymaterial,{name:'AES-GCM',length:256},false,['decrypt']);
 const compressed=await crypto.subtle.decrypt({name:'AES-GCM',iv:codec(v.nonce),additionalData:AAD},key,codec(v.data));
 const unzipped=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
 return {snapshot:validateSnapshot(JSON.parse(new TextDecoder().decode(unzipped))),password};
}
async function launch(pass){
 try{
  const {snapshot,password}=await unlock(pass);
  save(password);
  window.__FHQ_UNLOCKED_SNAPSHOT=JSON.stringify(snapshot);
  await import('./app-v2.mjs');
  if('serviceWorker' in navigator && (location.protocol==='https:'||location.hostname==='localhost')){
   navigator.serviceWorker.register(new URL('../sw.js',import.meta.url),{scope:'../'}).catch(()=>{});
  }
 }catch(error){renderLock(error.message==='Use an updated Safari browser'?error.message:'Could not unlock. Open your private link again or enter the correct recovery code.');}
}
document.addEventListener('submit',event=>{
 if(event.target?.id!=='privateUnlock')return;
 event.preventDefault();
 const code=document.getElementById('privateKey')?.value||'';
 const btn=event.target.querySelector('button');if(btn){btn.disabled=true;btn.textContent='Decrypting…'}
 launch(code);
});
launch(passFromLink()||saved());
