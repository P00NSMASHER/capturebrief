'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const site=require('./build-standalone-site');
const key='capturebrief',label='CaptureBrief';
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'assets/brand/approved-brand-assets.json'),'utf8'));
const brand=manifest.brands[key];
assert.equal(brand.source_sha256,'b48b332918001972060bbabb0190ed577ca9ab6f1c2d49589fc273abc8b36b8c');
assert.deepEqual(brand.source_dimensions,[6144,4096]);
for(const [name,meta] of Object.entries(brand.files)){
 const relative='assets/brand/'+name;
 assert(site.PUBLIC_FILES.includes(relative),'Image must be explicitly publishable: '+relative);
 const data=fs.readFileSync(path.join(__dirname,relative));
 assert.equal(crypto.createHash('sha256').update(data).digest('hex'),meta.sha256);
 assert.equal(data.length,meta.bytes);
 if(name.endsWith('.webp'))assert(data.length<160000,'Web image is too heavy');
}
for(const page of site.PUBLIC_FILES.filter(n=>n.endsWith('.html'))){
 const html=fs.readFileSync(path.join(__dirname,page),'utf8');
 if(html.includes('class="brand'))assert(html.includes(key+'-emblem.webp'),'Missing approved header: '+page);
 assert(html.includes('approved-brand-20261022.css'),'Missing responsive brand rules: '+page);
}
const home=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
assert(home.includes(key+'-emblem.webp'));
assert(home.includes('native-hero-emblem'));
assert(home.includes(label+' by RETALLY'));
assert(home.includes(key+'-social-20261022.png'));
const css=fs.readFileSync(path.join(__dirname,'assets/brand/approved-brand-20261022.css'),'utf8');
assert(css.includes('object-fit:contain'));
assert(css.includes('background:transparent'));
assert(css.includes('@media'));
console.log(label+' approved master provenance, asset hashes, budgets and responsive branding passed.');

const native=JSON.parse(fs.readFileSync(path.join(__dirname,'assets/brand/native-brand-assets.json'),'utf8'))[key];
for(const typ of ['emblem.webp','favicon.png']){
 const name=key+'-'+typ, data=fs.readFileSync(path.join(__dirname,'assets/brand',name));
 assert(site.PUBLIC_FILES.includes('assets/brand/'+name));
 assert.equal(crypto.createHash('sha256').update(data).digest('hex'),native.sizes[name].sha256);
}
assert(!home.includes('class="approved-brand-hero"><img'),'White-backed hero is retired');
