'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=name=>fs.readFileSync(path.join(root,name),'utf8');
const page=read('index.html'),terms=read('terms.html');
for(const phrase of ['Within two business days of complete intake','no later than five business days after the written scope is accepted','may request a full refund','at least two separately recorded checks','within one business day after human verification','No hidden or later-added terms shorten these refund rights'])
 assert(terms.includes(phrase),phrase);
assert(page.includes('within two business days of complete intake'));
assert(page.includes('at least twice again, around days 7 and 14'));
assert(page.includes('missed delivery deadlines qualify for a full refund'));
assert(page.includes('https://buy.stripe.com/cNi4gB55KgFPd7ceRtb7y00'));
assert(page.includes('$149')&&terms.includes('$149'));
const {plan}=require('./service-obligations');
assert.deepEqual(plan({intakeDate:'2026-10-23',acceptanceDate:'2026-10-26',deliveryDate:'2026-10-30'}),
 {responseDue:'2026-10-27',briefDue:'2026-11-02',checkpoints:['2026-11-06','2026-11-13']});
assert.deepEqual(plan({intakeDate:'2026-10-23',acceptanceDate:'2026-10-26',deliveryDate:'2026-10-30',holidays:['2026-11-02']}),
 {responseDue:'2026-10-27',briefDue:'2026-11-03',checkpoints:['2026-11-06','2026-11-13']});
console.log('CaptureBrief customer SLA, watch checkpoints, refunds and checkout continuity PASS');