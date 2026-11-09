const CACHE='fantasy-phone-v1-20261108';
const URLS=['./','./index.html','./brock/','./quick/','./highlight/','./vault.json','./assets/bootstrap.mjs','./assets/app-v2.mjs','./assets/engine.mjs','./assets/styles-v2.css','./assets/icon.svg','./icon-180.png','./icon-192.png','./manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(URLS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(xs=>Promise.all(xs.filter(x=>x.startsWith('fantasy-phone-')&&x!==CACHE).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
 if(e.request.method!=='GET')return;
 const u=new URL(e.request.url);
 if(u.origin!==self.location.origin||!u.pathname.includes('/fantasy/phone/'))return;
 e.respondWith(fetch(e.request).then(r=>{
   if(r.ok){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy)).catch(()=>{})}
   return r;
 }).catch(()=>caches.match(e.request).then(r=>r||caches.match('./index.html'))));
});
