'use strict';
// Offline, synthetic-only unit tests for the CaptureBrief 3.0 question builder.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('assets/v3-intake.js','utf8');
const keys=['deadline','amendment','eligibility','submission','rule'];
function page(type='FREE_CHECK',assumption='') {
  const listeners={};
  const control=(id,value='')=>({
    id,value,hidden:false,textContent:'',
    addEventListener(name,handler){(listeners[id+':'+name]??=[]).push(handler);},
    dispatchEvent(event){for(const f of listeners[id+':'+event.type]??[])f(event);}
  });
  const buttons=keys.map(key=>({
    key,getAttribute(name){return name==='data-assumption-template'?key:null;},
    addEventListener(name,handler){(listeners[key+':'+name]??=[]).push(handler);}
  }));
  const fields={
    'v3-question-desk':{hidden:true,querySelectorAll(){return buttons;}},
    'request-builder':{hidden:false},
    'purchase-status':control('purchase-status',type),
    assumptions:control('assumptions',assumption),
    'v3-question-meter':{textContent:''}
  };
  vm.runInNewContext(source,{
    document:{getElementById(id){return fields[id]??null;}},
    Event:class{constructor(type){this.type=type;}}
  },{timeout:500});
  return {
    fields,
    click(key){for(const fn of listeners[key+':click']??[])fn({});},
    type(value){fields['purchase-status'].value=value;for(const fn of listeners['purchase-status:change']??[])fn({});}
  };
}
function run(){
  const free=page();assert.equal(free.fields['v3-question-desk'].hidden,false);
  free.click('deadline');assert.match(free.fields.assumptions.value,/deadline/);
  free.click('rule');assert.match(free.fields.assumptions.value,/rule edition/);
  assert.equal(free.fields.assumptions.value.split('\n').length,1,'Free must never append a second question');
  assert.match(free.fields['v3-question-meter'].textContent,/1 of 1 question/);
  // Regression: one template click must not erase an original buyer question.
  const custom=page('FREE_CHECK','My exact public notice changes our deliverable deadline.');
  custom.click('deadline');
  assert.equal(custom.fields.assumptions.value,'My exact public notice changes our deliverable deadline.',
    'Selecting a template must not erase bespoke buyer context');
  assert.match(custom.fields['v3-question-meter'].textContent,/Your question was kept/);
  custom.fields.assumptions.value='';
  custom.click('deadline');
  const firstTemplate=custom.fields.assumptions.value;
  custom.click('rule');
  assert.notEqual(custom.fields.assumptions.value,firstTemplate,
    'Replacing one untouched canned suggestion with another remains easy');
  assert.match(custom.fields.assumptions.value,/rule edition/);
  const edited=custom.fields.assumptions.value+' — and our contract exception';
  custom.fields.assumptions.value=edited;
  custom.click('submission');
  assert.equal(custom.fields.assumptions.value,edited,
    'Editing a suggestion makes it buyer-authored again');
  const overflow=page('FREE_CHECK',['First question','Second question'].join(String.fromCharCode(10)));
  overflow.click('eligibility');
  assert.equal(overflow.fields.assumptions.value.split(String.fromCharCode(10)).length,2,
    'Template click must not erase an over-limit draft');
  assert.match(overflow.fields['v3-question-meter'].textContent,/Your question was kept/);
  const paid=page('SCOPE_FIRST');
  keys.forEach(key=>paid.click(key));assert.equal(paid.fields.assumptions.value.split('\n').length,5);
  paid.click('deadline');assert.equal(paid.fields.assumptions.value.split('\n').length,5,'Duplicate must not append');
  paid.fields.assumptions.value='One\nTwo\nThree\nFour\nFive';
  paid.click('rule');assert.equal(paid.fields.assumptions.value.split('\n').length,5,'Sixth question must not append');
  assert.match(paid.fields['v3-question-meter'].textContent,/Five questions is the limit/);
  paid.type('FREE_CHECK');
  assert.equal(paid.fields.assumptions.value.split('\n').length,5,'Mode change must not silently discard buyer text');
  assert.match(paid.fields['v3-question-meter'].textContent,/Narrow to the permitted number/);
  for(let i=0;i<1000;i++){
    const s=page(i%3?'SCOPE_FIRST':'FREE_CHECK');
    for(let j=0;j<6;j++)s.click(keys[(i+j)%keys.length]);
    const size=s.fields.assumptions.value.split('\n').filter(Boolean).length;
    assert(size<=(i%3?5:1),'Synthetic buyer exceeded the allowed assumption cap');
  }
  assert(!/\b(?:fetch|XMLHttpRequest|sendBeacon|localStorage|sessionStorage)\b/.test(source),'No network or persistence');
  console.log('CaptureBrief v3 decision desk: 1000 fictional users + no-send, dedupe, and cap tests passed.');
}
run();
