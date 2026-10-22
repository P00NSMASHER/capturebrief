'use strict';

const assert=require('assert/strict');
const fs=require('fs');
const os=require('os');
const path=require('path');
const site=require('./build-standalone-site');

const root=fs.mkdtempSync(path.join(os.tmpdir(),'capturebrief-publication-'));
const out=path.join(root,'dist');
const read=(file)=>fs.readFileSync(path.join(out,file),'utf8');
const originals=site.PUBLIC_FILES.map(name=>({path:name,sha256:site.sha256File(path.join(site.ROOT,name))}));
const env={CF_PAGES_COMMIT_SHA:process.env.CF_PAGES_COMMIT_SHA,GITHUB_SHA:process.env.GITHUB_SHA,COMMIT_REF:process.env.COMMIT_REF};
const checkoutReferences=(html)=>Array.from(html.matchAll(/href=(["'])((?:https:\/\/buy\.stripe\.com\/|mailto:)[^"']*)\1/g),match=>match[2]);

try{
  for(const name of site.PUBLIC_FILES){
    const target=path.join(root,name);
    fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.copyFileSync(path.join(site.ROOT,name),target);
  }
  // Unrelated projects, source tooling and state on gh-pages never enter dist.
  for(const name of ['abvm/index.html','fantasy/index.html','permitplate/index.html',
    'rehabsignal/index.html','scopesignal/index.html','private-state.json','.env',
    '.github/site_qa.py','build-standalone-site.js']){
    const target=path.join(root,name);
    fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.writeFileSync(target,'UNRELATED_SOURCE_CANARY');
  }
  process.env.CF_PAGES_COMMIT_SHA='a'.repeat(40);
  process.env.GITHUB_SHA='b'.repeat(40);
  process.env.COMMIT_REF='c'.repeat(40);
  const info=site.build({root});
  assert.equal(info.sourceCommit,'a'.repeat(40),'Cloudflare revision must win');
  assert.equal(info.company,'CaptureBrief');
  assert.equal(info.operator,'JP Enterprises');
  assert.equal(info.canonical,site.SITE_BASE);
  assert.equal(info.sourceBranch,process.env.CF_PAGES_BRANCH||'gh-pages');
  assert.deepEqual(site.listFilesRecursive(out),site.PUBLIC_FILES.concat(site.GENERATED_FILES,'build-info.json').sort());
  assert.equal(info.publicFileCount,site.PUBLIC_FILES.length+3);
  assert.equal(read('_headers'),"/*\n"+
    "  Strict-Transport-Security: max-age=86400\n"+
    "  X-Content-Type-Options: nosniff\n"+
    "  Referrer-Policy: strict-origin-when-cross-origin\n"+
    "  Content-Security-Policy: object-src 'none'; frame-ancestors 'none'; base-uri 'self'\n");
  assert(info.files.some(file=>file.path==='_headers'),'Header configuration must be fingerprinted');
  for(const name of site.listFilesRecursive(out)){
    assert(!fs.readFileSync(path.join(out,name)).includes('UNRELATED_SOURCE_CANARY'),name+' leaked unrelated content');
  }

  for(const file of site.PUBLIC_FILES.filter(name=>name.endsWith('.html'))){
    const html=read(file);
    const source=fs.readFileSync(path.join(site.ROOT,file),'utf8');
    assert.equal(html.split('Part of RETALLY Group').length-1,1,file+' needs one group affiliation');
    assert(html.includes('href="'+site.GROUP_URL+'"'));
    assert(!html.includes(site.LEGACY_SITE_BASE));
    assert(html.includes('<!--email_off-->')&&html.includes('<!--/email_off-->'));
    assert.deepEqual(checkoutReferences(html),checkoutReferences(source),'Payment or mail link changed: '+file);
    for(const match of html.matchAll(/\b(?:href|src|action)=(["'])([^"']*)\1/g)){
      if(!/^(?:[a-z][a-z0-9+.-]*:|\/\/|#|\?)/i.test(match[2])) assert(match[2].startsWith('/'),'Relative reference on standalone page '+file);
    }
    const canonical=html.match(/rel="canonical" href="([^"]+)"/);
    if(canonical){
      assert(canonical[1].startsWith(site.SITE_BASE));
      assert(!canonical[1].endsWith('.html'));
    }
  }
  site.checkLocalReferences(out);
  assert(read('404.html').includes('href="/assets/enterprise.css?v=2"'),'Nested 404 must load styles from root');
  assert(read('index.html').includes('$149'));
  assert(read('index.html').includes('JP Enterprises'));
  assert(read('decision-evidence.html').includes('$149, with scope and timing confirmed before work begins.'));
  assert(!read('decision-evidence.html').includes('scope and timing confirmed before payment.'));
  assert(read('sitemap.xml').includes(site.SITE_BASE+'decision-evidence</loc>'));
  assert(!read('sitemap.xml').includes('404'));
  assert(!read('sitemap.xml').includes('.html'));
  for(const name of ['assets/capturebrief.js','assets/capturebrief.css','assets/enterprise.js',...site.PUBLIC_FILES.filter(name=>name.startsWith('examples/'))]){
    assert.equal(site.sha256File(path.join(out,name)),site.sha256File(path.join(site.ROOT,name)),name+' should remain byte-identical');
  }
  const examples=JSON.parse(read('examples/manifest.json'));
  assert.equal(examples.fictional,true);
  for(const file of examples.files){
    assert.equal(site.sha256File(path.join(out,file.path)),file.sha256,'Example integrity changed');
    assert.equal(fs.statSync(path.join(out,file.path)).size,file.bytes);
  }
  for(const file of info.files){
    assert.equal(file.sha256,site.sha256File(path.join(out,file.path)));
    assert.equal(file.bytes,fs.statSync(path.join(out,file.path)).size);
  }
  assert.equal(info.publicSourceFingerprint,site.fingerprint(info.files));
  assert.match(info.sourceContentFingerprint,/^[a-f0-9]{64}$/);

  for(const name of site.RUNTIME_FILES){
    fs.writeFileSync(path.join(root,name),'runtime canary');
    assert.throws(()=>site.build({root}),/UNEXPECTED_PAGES_RUNTIME/,'Must block root runtime '+name);
    fs.unlinkSync(path.join(root,name));
  }
  fs.unlinkSync(path.join(root,'favicon.svg'));
  assert.throws(()=>site.build({root}),/MISSING_PUBLIC_FILE:favicon.svg/);
  for(const file of originals) assert.equal(site.sha256File(path.join(site.ROOT,file.path)),file.sha256,'Original shared source changed');
  console.log('CaptureBrief allowlist, runtime exclusion, source integrity, checkout continuity, clean routes and revision identity passed.');
}finally{
  for(const [name,value] of Object.entries(env)){
    if(value===undefined) delete process.env[name];
    else process.env[name]=value;
  }
  fs.rmSync(root,{recursive:true,force:true});
}

