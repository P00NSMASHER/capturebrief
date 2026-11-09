/* GitHub CI ONLY: generates fictional AES-GCM packet in the runner checkout. */
import {webcrypto} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {writeFileSync} from 'node:fs';
const toUrl=bytes=>Buffer.from(bytes).toString('base64url');
const salt=webcrypto.getRandomValues(new Uint8Array(16)),iv=webcrypto.getRandomValues(new Uint8Array(12));
const password='AAAAAAAAAAAAAAAAAAAAAA';
const material=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
const key=await webcrypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:420000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt']);
const teams=Object.fromEntries(['brock','quick','highlight'].map((id,i)=>[id,{
 name:'Fictional '+id+' Test Team',short:'Fictional '+id,accent:['cyan','purple','green'][i],
 leagueId:'TEST.'+id,teamId:'1',provider:'yahoo',source:'Flaim Fantasy SYNTHETIC',
 record:'4–3',rank:'2 of 8',waiver:'#3',score:'25.5–21.1',
 nextMove:'No verified transaction',nextDetail:'Synthetic test data',
 roster:[{id:'f-1',name:'Fictional Runner',position:'RB',slot:'RB',
   eligiblePositions:['RB','W/R/T'],nflTeam:'FIX',injury:null,actualPoints:8.5,projection:null,locked:false}],
 availablePlayers:[{id:'f-a',name:'Fictional Waiver Player',position:'WR',team:'FIX',
   acquisitionState:'free_agent',percentOwned:20,projection:null}],
 projectionCoverage:'none',transactions:[],
 matchup:{home:{teamId:'1',teamName:'Fictional '+id,points:25.5,projectedPoints:100,winProbability:.6},
 away:{teamId:'2',teamName:'Fictional Opponent',points:21.1,projectedPoints:95,winProbability:.4}}
}]));
const fixture={schemaVersion:3,source:'Flaim Fantasy - SYNTHETIC QA',provider:'Yahoo',season:2026,week:9,syncedAtIso:new Date().toISOString(),teams};
const zipped=gzipSync(Buffer.from(JSON.stringify(fixture)));
const encrypted=await webcrypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:new TextEncoder().encode('FantasyHQ-Phone-2026-v1')},key,zipped);
const packet={v:1,cipher:'AES-256-GCM',kdf:'PBKDF2-SHA256',encoding:'gzip',iterations:420000,salt:toUrl(salt),nonce:toUrl(iv),data:toUrl(new Uint8Array(encrypted))};
writeFileSync('fantasy/phone/vault.json',JSON.stringify(packet)+'\n');
console.log('Verified synthetic-only browser fixture generated; production ciphertext not published in CI artifacts.');
