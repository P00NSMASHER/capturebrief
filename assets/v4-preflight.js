/* CaptureBrief 4.0: no-source-fetch, no-storage, local evidence preflight. */
(function(root){
  'use strict';
  const NAMES=Object.freeze({
    notice:'Notice identity',amendments:'Amendment history',
    eligibility:'Competition and eligibility',submission:'Submission instructions',
    rules:'Applicable rule edition'
  });
  const STATUSES=Object.freeze({
    unchecked:'Not checked',found:'Buyer located a public reference (not verified)',
    conflict:'Conflicting versions to reconcile',unavailable:'Not publicly available'
  });
  function noticeUrl(value){
    const raw=String(value||'').trim();
    if(!raw)return '';
    if(raw.length>2048||/[\u0000-\u001f\u007f]/.test(raw))throw Error('Use only a complete public SAM.gov opportunity link.');
    let url;try{url=new URL(raw);}catch{throw Error('Use only a complete public SAM.gov opportunity link.');}
    if(url.protocol!=='https:'||url.hostname!=='sam.gov'||url.username||url.password||
      (url.port&&url.port!=='443')||url.search||url.hash||
      !/^\/opp\/[0-9a-f]{32}\/view\/?$/i.test(url.pathname))
      throw Error('Use the exact public SAM.gov /opp/…/view link without query parameters.');
    return url.href;
  }
  function evaluate(input,rawUrl){
    const state={};let found=0,missing=0,conflicted=0;
    for(const key of Object.keys(NAMES)){
      const v=input?.[key]??'unchecked';
      if(!Object.hasOwn(STATUSES,v))throw Error('Unknown source state');
      state[key]=v;
      if(v==='found')found++;else if(v==='conflict'||v==='unavailable')conflicted++;else missing++;
    }
    const url=noticeUrl(rawUrl);
    const label=conflicted?'HOLD FOR SOURCE RECONCILIATION':
      (!url||missing)?'EVIDENCE GAPS TO CHECK':'READY TO REQUEST HUMAN REVIEW';
    const detail=conflicted?'At least one public source is conflicting or unavailable. Resolve the basis before relying on it.':
      !url?'A complete public SAM.gov opportunity link is needed for a source-specific review. None was provided.':
      missing?'At least one source family has not been checked. Your next action is to locate and review it.':
      'You marked five public references as located; none was independently verified here.';
    const report=[
      'CaptureBrief 4.0 | BUYER-MARKED, UNVERIFIED EVIDENCE CHECKLIST',
      'Public notice: '+(url||'Not provided'), 'Status: '+label,'',
      ...Object.keys(NAMES).map(key=>NAMES[key]+': '+STATUSES[state[key]]),'',
      'References located (buyer-marked): '+found+'/5',
      'Unreviewed: '+missing+'; conflicting or unavailable: '+conflicted,'',
      'No sources were fetched or verified by CaptureBrief. No eligibility, legal, bid posture,',
      'deadline, amendment authority, payment or customer approval is established by this worksheet.'
    ].join('\n');
    return Object.freeze({state,url,found,missing,conflicted,label,detail,report});
  }
  if(typeof module==='object'&&module.exports)module.exports={evaluate,noticeUrl,NAMES,STATUSES};
  if(!root.document)return;
  const panel=root.document.querySelector('[data-v4-preflight]');
  if(!panel)return;
  const select=root.document.querySelectorAll('[data-v4-gate]');
  const url=root.document.getElementById('v4-notice-url');
  const title=root.document.querySelector('[data-v4-status]');
  const details=root.document.querySelector('[data-v4-details]');
  const copy=root.document.querySelector('[data-v4-copy]');
  const status=root.document.querySelector('[data-v4-copy-status]');
  const fallback=root.document.querySelector('[data-v4-fallback]');
  const text=root.document.getElementById('v4-copy-text');
  if(!url||!title||!details||!copy||!status||!fallback||!text||select.length!==5)return;
  let revision=0;let current=null;
  // Explicit, local-only handoff: never replace a buyer's existing intake.
  const reviewLink=root.document.querySelector('.v4-preflight-copy a[href="#request"]');
  const opportunityField=root.document.getElementById('opportunity-url');
  if(reviewLink&&opportunityField){
    reviewLink.addEventListener('click',()=>{
      if(!current?.url||opportunityField.value.trim())return;
      opportunityField.value=current.url;
      opportunityField.dispatchEvent(new root.Event('input',{bubbles:true}));
    });
  }
  function update(){
    revision++;status.textContent='';fallback.hidden=true;text.value='';
    const marks=Object.fromEntries(Array.from(select,field=>[field.dataset.v4Gate,field.value]));
    try{
      current=evaluate(marks,url.value);
      title.textContent=current.label;
      details.textContent=current.detail+' '+current.found+'/5 public references buyer-marked.';
      copy.disabled=false;
    }catch(e){
      current=null;title.textContent='INVALID PUBLIC LINK';
      details.textContent=e.message;copy.disabled=true;
    }
  }
  for(const field of select)field.addEventListener('change',update);
  url.addEventListener('input',update);
  copy.addEventListener('click',async()=>{
    if(!current)return;
    const previous=revision,report=current.report;
    try{
      if(!root.navigator?.clipboard?.writeText)throw Error('COPY_UNAVAILABLE');
      await root.navigator.clipboard.writeText(report);
      status.textContent=revision===previous
        ?'Checklist copied locally. Nothing was sent or saved.'
        :'Your checklist changed while copying. Review and copy again.';
    }catch{
      if(revision!==previous){status.textContent='Your checklist changed while copying. Copy again.';return;}
      text.value=report;fallback.hidden=false;text.focus();text.select();
      status.textContent='Clipboard unavailable. Select the full worksheet below and copy manually. Nothing was sent.';
    }
  });
  panel.hidden=false;
  update();
})(typeof window==='undefined'?globalThis:window);
