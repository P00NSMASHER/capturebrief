"""Static public-brand regression checks; do not send email or alter payment routes."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import os

ROOT=Path(os.environ.get('SITE_ROOT','.')).resolve()
OUT=Path(os.environ.get('QA_OUTPUT','qa-output/brand')).resolve()
PAGES=['404.html','data-handling.html','decision-evidence.html','flagos/index.html','freightrecovery/index.html','index.html','permitplate/index.html','portfolio/index.html','privacy.html','rehabsignal/index.html','scopesignal/index.html','sheetharbor/index.html','starblox/index.html','terms.html']
PRIMARY_PHOTOS={'index.html':0,'permitplate/index.html':7,'freightrecovery/index.html':7}

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.authors=[]; self.marker=None; self.in_footer=False; self.footer=[]; self.links=[]; self.link=None; self.images=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta' and a.get('name')=='author': self.authors.append(a.get('content'))
        if tag=='meta' and a.get('name')=='site-brand': self.marker=a.get('content')
        if tag=='footer': self.in_footer=True
        if tag=='a': self.link={'href':a.get('href',''),'id':a.get('id'),'text':''}
        if tag=='img': self.images+=1
    def handle_data(self,data):
        if self.in_footer: self.footer.append(data)
        if self.link is not None: self.link['text']+=data
    def handle_endtag(self,tag):
        if tag=='footer': self.in_footer=False
        if tag=='a' and self.link is not None:
            self.links.append(self.link); self.link=None

report={'brand':'JP Enterprises','pages':[],'errors':[]}
for rel in PAGES:
    try:
        raw=(ROOT/rel).read_bytes(); p=Page(); p.feed(raw.decode('utf-8'))
        issues=[]
        if p.authors!=['JP Enterprises']: issues.append('author metadata must use the public brand')
        if p.marker!='jp-enterprises-1': issues.append('brand release marker missing')
        if 'JP Enterprises' not in ' '.join(p.footer): issues.append('public brand missing from footer')
        if rel!='portfolio/index.html' and any('portfolio/' in a['href'] for a in p.links): issues.append('cross-project navigation must stay removed')
        if rel in PRIMARY_PHOTOS:
            contact=[a for a in p.links if a['id']=='contact-email']
            if len(contact)!=1 or contact[0]['text']!='Email JP Enterprises': issues.append('visible contact label must use the brand')
            if any('@' in a['text'] for a in p.links if a['href'].startswith('mailto:')): issues.append('personal email must not be the default visible label')
            if p.images!=PRIMARY_PHOTOS[rel]: issues.append(f'expected {PRIMARY_PHOTOS[rel]} content-image placements')
        report['pages'].append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'brand_verified':not issues})
        report['errors'].extend(rel+': '+issue for issue in issues)
    except Exception as exc:
        report['errors'].append(rel+': '+str(exc))
report['passed']=not report['errors']
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
