'use strict';
// Exhaustive 1024-state, no-send, no-storage CaptureBrief 4.0 unit test.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const util=require('../assets/v4-preflight.js');
const states=['unchecked','found','conflict','unavailable'];
const keys=Object.keys(util.NAMES);
let counted=0;
for(let i=0;i<1024;i++){
 let t=i;const values={};
 for(const key of keys){values[key]=states[t%4];t=Math.floor(t/4);}
 const result=util.evaluate(values,'');
 assert.equal(result.found+result.missing+result.conflicted,5);
 assert.notEqual(result.label,'READY TO REQUEST HUMAN REVIEW', 'A missing notice must never appear review-ready');
 assert.match(result.report,/BUYER-MARKED, UNVERIFIED/);
 assert.match(result.report,/No sources were fetched or verified/);
 assert(!result.report.includes('Approved to bid'));
 assert(!result.report.includes('Purchase confirmed'));
 counted++;
}
assert.equal(counted,1024);
const missingNotice=util.evaluate(Object.fromEntries(keys.map(k=>[k,'found'])),'   ');
assert.equal(missingNotice.url,'');
assert.equal(missingNotice.label,'EVIDENCE GAPS TO CHECK');
assert.match(missingNotice.detail,/public SAM\.gov opportunity link/);
assert.match(missingNotice.report,/Public notice: Not provided/);
const all=util.evaluate(Object.fromEntries(keys.map(k=>[k,'found'])),
  'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view');
assert.equal(all.found,5);
assert.match(all.label,/HUMAN REVIEW/);
assert.match(all.report,/No sources were fetched or verified/);
const red=util.evaluate({...Object.fromEntries(keys.map(k=>[k,'found'])),rules:'conflict'});
assert.match(red.label,/HOLD/);
for(const url of [
 'https://sam.gov.evil.example/opp/c20a138049b94add92f0f32a41856585/view',
 'http://sam.gov/opp/c20a138049b94add92f0f32a41856585/view',
 'https://user:password@sam.gov/opp/c20a138049b94add92f0f32a41856585/view',
 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view?tracking=1',
 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view#fragment',
 'file:///etc/passwd','https://localhost/opp/a/view',
 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view\nBcc:bad@example.com'
])assert.throws(()=>util.noticeUrl(url),'Unsafe public link should be rejected: '+url);
assert.throws(()=>util.evaluate({notice:'approved'}));
const script=fs.readFileSync('assets/v4-preflight.js','utf8');
assert(!/\b(?:fetch|XMLHttpRequest|sendBeacon|localStorage|sessionStorage)\s*\(/.test(script));
const home=fs.readFileSync('index.html','utf8');
assert(home.includes('name="capturebrief-product-version" content="4.0"'));
assert(home.includes('data-v4-preflight hidden'));
assert(home.includes('data-v4-copy'));
assert(!/<form[^>]*data-v4-preflight/.test(home));
console.log('CaptureBrief v4: 1,024 state combinations, restricted links, and offline/no-send tests passed.');
