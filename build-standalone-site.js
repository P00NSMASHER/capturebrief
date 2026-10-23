'use strict';

// A separate static publication boundary for the CaptureBrief company site.
// The gh-pages branch also contains unrelated sites; never publish it wholesale.
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');

const ROOT=__dirname;
const OUT=path.join(ROOT,'dist');
const SITE_BASE='https://capturebrief.retallyrecovery.com/';
const LEGACY_SITE_BASE='https://p00nsmasher.github.io/capturebrief/';
const GROUP_URL='https://group.retallyrecovery.com/';

const PUBLIC_FILES=Object.freeze([
  "assets/brand/capturebrief-emblem.webp",
  "assets/brand/retally-wordmark-approved.png",
  "assets/brand/capturebrief-favicon.png",
  "assets/brand/native-brand-assets.json",
  "assets/brand/capturebrief-600-20261022.webp",
  "assets/brand/capturebrief-1200-20261022.webp",
  "assets/brand/capturebrief-wordmark-20261022.webp",
  "assets/brand/capturebrief-social-20261022.png",
  "assets/brand/capturebrief-icon-20261022.png",
  "assets/brand/approved-brand-assets.json",
  "assets/brand/approved-brand-20261022.css",
  "404.html",
  "data-handling.html",
  "decision-evidence.html",
  "favicon.svg",
  "index.html",
  "privacy.html",
  "terms.html",
  "assets/capturebrief.css",
  "assets/capturebrief.js",
  "assets/enterprise.css",
  "assets/enterprise.js",
  "assets/evidence.css",
  "assets/fonts/azeret-mono-latin-wght-normal.woff2",
  "assets/fonts/familjen-grotesk-latin-wght-normal.woff2",
  "assets/fonts/newsreader-latin-wght-italic.woff2",
  "assets/fonts/newsreader-latin-wght-normal.woff2",
  "assets/og-capturebrief.png",
  "assets/visuals/architecture-grid.webp",
  "assets/visuals/capturebrief-social.jpg",
  "assets/visuals/change-watch.webp",
  "assets/visuals/evidence-layers.webp",
  "assets/visuals/hero-council.webp",
  "assets/visuals/reviewer-desk.webp",
  "examples/amendment-02.txt",
  "examples/incorporation.txt",
  "examples/manifest.json",
  "examples/original.txt",
  "examples/rule-2025.txt",
  "examples/rule-2026.txt"
]);
const GENERATED_FILES=Object.freeze(['robots.txt','sitemap.xml','_headers']);
const STANDALONE_HEADERS="/*\n"+
  "  Strict-Transport-Security: max-age=86400\n"+
  "  X-Content-Type-Options: nosniff\n"+
  "  Referrer-Policy: strict-origin-when-cross-origin\n"+
  "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()\n"+
  "  X-Frame-Options: DENY\n"+
  "  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'none'; media-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests\n";
const RUNTIME_FILES=Object.freeze(['functions','_worker.js','wrangler.toml','wrangler.json','wrangler.jsonc']);

function sha256File(file){
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}
function fingerprint(files){
  return crypto.createHash('sha256').update(files.slice()
    .sort((a,b)=>a.path.localeCompare(b.path))
    .map(item=>item.path+':'+item.sha256).join('\n')).digest('hex');
}
function listFilesRecursive(directory,prefix=''){
  const files=[];
  for(const entry of fs.readdirSync(directory,{withFileTypes:true})){
    const relative=prefix?prefix+'/'+entry.name:entry.name;
    if(entry.isDirectory()) files.push(...listFilesRecursive(path.join(directory,entry.name),relative));
    else if(entry.isFile()) files.push(relative);
    else throw new Error('NON_REGULAR_OUTPUT:'+relative);
  }
  return files.sort();
}
function validateSources(root=ROOT){
  const failures=[];
  for(const name of RUNTIME_FILES){
    if(fs.existsSync(path.join(root,name))) failures.push('UNEXPECTED_PAGES_RUNTIME:'+name);
  }
  const realRoot=fs.realpathSync(root);
  for(const name of PUBLIC_FILES){
    const source=path.join(realRoot,name);
    if(!fs.existsSync(source)||!fs.lstatSync(source).isFile()){
      failures.push('MISSING_PUBLIC_FILE:'+name);
    }else if(fs.realpathSync(source)!==source){
      failures.push('SYMLINK_IN_PUBLIC_ALLOWLIST:'+name);
    }
  }
  return failures;
}
function cleanHtmlUrl(value){
  return value.replace(/\/index\.html(?=[?#]|$)/,'/')
    .replace(/\.html(?=[?#]|$)/,'');
}
function rootReference(value){
  if(/^(?:[a-z][a-z0-9+.-]*:|\/\/|#|\?)/i.test(value)) return value;
  return cleanHtmlUrl('/'+value.replace(/^\.\//,'').replace(/^\//,''));
}
function plainAnchorLabel(label){
  // Inline approved logo preserves the same text-only affiliation routing.
  return label.replace(/<img\b[^>]*\balt=([\"'])RETALLY\1[^>]*>/gi,'RETALLY')
    .replace(/<[^>]*>/g,'').replace(/\s+/g,' ').trim();
}
function isGroupAffiliationLabel(label){
  return ['RETALLY Group','A RETALLY Group business','Part of RETALLY Group'].includes(plainAnchorLabel(label));
}
function rebaseGroupLinks(html){
  // PR72 added Group links to the old umbrella host. Match their labels and
  // known destinations so genuine Freight links retain their own destination.
  return html.replace(/(<a\b[^>]*?\bhref=)(["'])([^"']*)\2([^>]*>)([\s\S]*?)(<\/a>)/gi,
    (match,prefix,quote,href,suffix,label,close)=>{
      let destination=href;
      if(isGroupAffiliationLabel(label)&&[
        'https://www.retallyrecovery.com/',
        'https://www.retallyrecovery.com/capturebrief/'
      ].includes(href)){
        destination=GROUP_URL;
      }else if(plainAnchorLabel(label)==='RETALLY contact'){
        let old;
        try{old=new URL(href);}catch{return match;}
        if(old.origin==='https://www.retallyrecovery.com'&&old.pathname==='/contact/'){
          const next=new URL(GROUP_URL);
          next.search=old.search;
          next.hash='contact';
          destination=next.href;
        }
      }
      return prefix+quote+destination+quote+suffix+label+close;
    });
}
function hasGroupFooterAffiliation(footer){
  return Array.from(footer.matchAll(/<a\b[^>]*?\bhref=(["'])([^"']*)\1[^>]*>([\s\S]*?)<\/a>/gi))
    .some(match=>match[2]===GROUP_URL&&isGroupAffiliationLabel(match[3]));
}
function transformHtml(html,file=''){
  let text=html.split(LEGACY_SITE_BASE).join(SITE_BASE);
  if(file==='decision-evidence.html'){
    text=text.replace('$149, with scope and timing confirmed before payment.',
      '$149, with scope and timing confirmed before work begins.');
  }
  if(file==='privacy.html'){
    text=text.replace('GitHub Pages and its infrastructure may process',
      'Cloudflare Pages and its infrastructure may process')
      .replace('under GitHub’s own terms and privacy practices.',
        'under <a href="https://www.cloudflare.com/policies/privacy/">Cloudflare’s privacy policy</a> and applicable service terms.');
  }
  if(file==='data-handling.html'){
    text=text.replace('GitHub Pages hosts the public site. Google/Gmail processes direct email correspondence.',
      'Cloudflare Pages hosts the public site. RETALLY’s email service provider processes direct email correspondence.');
  }
  text=rebaseGroupLinks(text);
  const escapedBase=SITE_BASE.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  text=text.replace(new RegExp(escapedBase+'[^\\s"\'<>]*','g'),cleanHtmlUrl);
  // Root paths keep the same navigation and assets working on nested 404 routes.
  text=text.replace(/\b(href|src|action)=(["'])([^"']*)\2/g,
    (match,attribute,quote,value)=>attribute+'='+quote+rootReference(value)+quote);
  const footer=text.match(/<footer\b[^>]*>[\s\S]*?<\/footer>/i);
  if(!footer) throw new Error('MISSING_COMPANY_FOOTER');
  if(!hasGroupFooterAffiliation(footer[0])){
    const affiliation='<div class="wrap retally-affiliation"><a href="'+GROUP_URL+'">Part of RETALLY Group</a></div>';
    text=text.replace('</footer>',affiliation+'</footer>');
  }
  // Preserve existing public mailto links without Cloudflare's decode script.
  return text.replace(/<body\b[^>]*>/,'$&\n<!--email_off-->')
    .replace('</body>','<!--/email_off-->\n</body>');
}
function checkLocalReferences(out=OUT){
  const failures=[];
  function check(ref,from){
    if(!ref||/^(?:mailto|tel|data|javascript):/i.test(ref)||ref.startsWith('#')) return;
    let url;
    try{url=new URL(ref,new URL(from,SITE_BASE));}catch{
      failures.push('INVALID_PUBLIC_REFERENCE:'+from+':'+ref);return;
    }
    if(url.origin!==new URL(SITE_BASE).origin) return;
    const relative=decodeURIComponent(url.pathname).replace(/^\//,'');
    const candidates=relative?[relative,relative+'.html',relative+'/index.html']:['index.html'];
    if(!candidates.some(name=>fs.existsSync(path.join(out,name))&&fs.statSync(path.join(out,name)).isFile())){
      failures.push('MISSING_PUBLIC_REFERENCE:'+from+':'+ref);
    }
  }
  for(const name of PUBLIC_FILES){
    if(name.endsWith('.html')){
      const html=fs.readFileSync(path.join(out,name),'utf8');
      for(const match of html.matchAll(/\b(?:href|src|action)=(["'])([^"']*)\1/g)) check(match[2],name);
      for(const match of html.matchAll(/\bsrcset=(["'])([^"']*)\1/g)){
        for(const candidate of match[2].split(',')) check(candidate.trim().split(/\s+/)[0],name);
      }
    }else if(name.endsWith('.css')){
      const css=fs.readFileSync(path.join(out,name),'utf8');
      for(const match of css.matchAll(/url\(\s*["']?([^"'\s)]+)["']?\s*\)/g)) check(match[1],name);
    }
  }
  if(failures.length) throw new Error(failures.join('\n'));
}
function build(options={}){
  const root=options.root||ROOT;
  const out=options.out||path.join(root,'dist');
  // Refuse a publication directory that could erase the source tree.
  if(path.resolve(out)===path.resolve(root)||!path.resolve(out).startsWith(path.resolve(root)+path.sep)){
    throw new Error('OUTPUT_MUST_BE_INSIDE_SOURCE_ROOT');
  }
  const failures=validateSources(root);
  if(failures.length) throw new Error(failures.join('\n'));
  fs.rmSync(out,{recursive:true,force:true});
  fs.mkdirSync(out,{recursive:true});
  const inputs=[];
  for(const name of PUBLIC_FILES){
    const source=path.join(root,name);
    const target=path.join(out,name);
    inputs.push({path:name,sha256:sha256File(source),bytes:fs.statSync(source).size});
    fs.mkdirSync(path.dirname(target),{recursive:true});
    if(name.endsWith('.html')){
      fs.writeFileSync(target,transformHtml(fs.readFileSync(source,'utf8'),name));
    }else if(name==='assets/enterprise.css'){
      fs.writeFileSync(target,fs.readFileSync(source,'utf8')+
        '\n/* Company affiliation, shared by the standalone CaptureBrief pages. */\n'+
        '.retally-affiliation{padding-top:18px;margin-top:18px;font-size:14px}\n'+
        '.retally-affiliation a{display:inline-flex;align-items:center;min-height:44px;color:inherit;font-weight:700;text-underline-offset:4px}\n');
    }else{
      fs.copyFileSync(source,target);
    }
  }
  const pages=PUBLIC_FILES.filter(name=>name.endsWith('.html')&&name!=='404.html');
  fs.writeFileSync(path.join(out,'_headers'),STANDALONE_HEADERS);
  fs.writeFileSync(path.join(out,'robots.txt'),'User-agent: *\nAllow: /\nSitemap: '+SITE_BASE+'sitemap.xml\n');
  fs.writeFileSync(path.join(out,'sitemap.xml'),'<?xml version="1.0" encoding="UTF-8"?>\n'+
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+
    pages.map(name=>'  <url><loc>'+cleanHtmlUrl(SITE_BASE+name)+'</loc></url>').join('\n')+
    '\n</urlset>\n');
  checkLocalReferences(out);
  const files=PUBLIC_FILES.concat(GENERATED_FILES).sort().map(name=>({
    path:name,sha256:sha256File(path.join(out,name)),bytes:fs.statSync(path.join(out,name)).size
  }));
  const info={
    buildInfoVersion:'CaptureBrief-standalone-build-v1.0.0',
    company:'CaptureBrief',
    operator:'JP Enterprises',
    canonical:SITE_BASE,
    group:GROUP_URL,
    sourceRepository:'P00NSMASHER/capturebrief',
    sourceBranch:process.env.CF_PAGES_BRANCH||'gh-pages',
    sourceCommit:process.env.CF_PAGES_COMMIT_SHA||process.env.GITHUB_SHA||process.env.COMMIT_REF||'local',
    deployContext:'cloudflare-pages',
    builtAt:new Date().toISOString(),
    publicFileCount:files.length,
    sourceContentFingerprint:fingerprint(inputs),
    publicSourceFingerprint:fingerprint(files),
    files
  };
  fs.writeFileSync(path.join(out,'build-info.json'),JSON.stringify(info,null,2)+'\n');
  const expected=PUBLIC_FILES.concat(GENERATED_FILES,'build-info.json').sort();
  if(JSON.stringify(listFilesRecursive(out))!==JSON.stringify(expected)) throw new Error('DIST_CONTENT_MISMATCH');
  return info;
}

if(require.main===module){
  if(process.argv.length>2) throw new Error('Usage: node build-standalone-site.js');
  const info=build();
  console.log(JSON.stringify({
    company:info.company,canonical:info.canonical,sourceCommit:info.sourceCommit,
    publicFileCount:info.publicFileCount,output:'dist'
  },null,2));
}
module.exports={ROOT,OUT,SITE_BASE,LEGACY_SITE_BASE,GROUP_URL,PUBLIC_FILES,GENERATED_FILES,
  RUNTIME_FILES,sha256File,fingerprint,listFilesRecursive,validateSources,
  cleanHtmlUrl,rootReference,transformHtml,checkLocalReferences,build};

