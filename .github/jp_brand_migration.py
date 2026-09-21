"""One-time static branding edit; preserve real destinations and product content."""
from pathlib import Path
import hashlib
import json
import re
from html.parser import HTMLParser

ROOT = Path('.')
PAGES = ['404.html', 'decision-evidence.html', 'flagos/index.html', 'freightrecovery/index.html', 'index.html', 'permitplate/index.html', 'portfolio/index.html', 'rehabsignal/index.html', 'scopesignal/index.html', 'sheetharbor/index.html', 'starblox/index.html']
PRIMARY = {'index.html', 'permitplate/index.html', 'freightrecovery/index.html'}
REPORT = []

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.destinations=[]; self.images=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag == 'a': self.destinations.append(attrs.get('href',''))
        if tag == 'img': self.images.append(attrs)

for rel in PAGES:
    path = ROOT / rel
    old = path.read_text(encoding='utf-8')
    text = old.replace('</head>', '<meta name="author" content="JP Enterprises"><meta name="site-brand" content="jp-enterprises-1"></head>', 1)
    text = text.replace('Founder-operated service.', 'JP Enterprises.')
    text = re.sub(r'(id="contact-email"[^>]*>)[^<]+(?=</a>)', r'\1Email JP Enterprises', text)
    if rel == 'decision-evidence.html':
        text = text.replace('</p></div></footer>', '</p><p class="small">JP Enterprises</p></div></footer>')
    elif rel == 'portfolio/index.html':
        text = text.replace('<title>Project Index</title>', '<title>JP Enterprises — Project Index</title>')
        text = text.replace('>Project Index</a>', '>JP Enterprises</a>')
        text = text.replace('Hosted as static GitHub Pages content. No Netlify credits required.', 'JP Enterprises · Independent products and projects.')
    elif rel == '404.html':
        text = re.sub(r' or <a href="portfolio/">view the project index</a>', '', text)
        text = text.replace('</body>', '<footer class="wrap footer">JP Enterprises</footer></body>')
    elif rel not in PRIMARY:
        text = re.sub(r'<a\b[^>]*href="\.\./portfolio/"[^>]*>[^<]+</a>', '', text)
        text = text.replace(' · 2026 · </footer>', ' · 2026 · JP Enterprises</footer>')
    if rel in PRIMARY:
        text = text.replace('assets/enterprise.js?v=2', 'assets/enterprise.js?v=jp1')
    assert text != old, 'No changes: '+rel
    before=Links(); before.feed(old)
    after=Links(); after.feed(text)
    # All real contact and checkout destinations must remain exactly the same.
    select=lambda p:[u for u in p.destinations if u.startswith('mailto:') or 'stripe.com/' in u]
    assert select(before) == select(after), 'Contact/payment destination changed: '+rel
    assert before.images == after.images, 'Photography changed: '+rel
    if rel != 'portfolio/index.html':
        assert not any('portfolio/' in u for u in after.destinations), 'Cross-project navigation remains: '+rel
    assert '<meta name="author" content="JP Enterprises">' in text
    assert 'JP Enterprises' in re.search(r'<footer\b[\s\S]*?</footer>', text).group(0)
    path.write_text(text, encoding='utf-8')
    REPORT.append({'path':rel, 'before_sha256':hashlib.sha256(old.encode()).hexdigest(), 'after_sha256':hashlib.sha256(text.encode()).hexdigest(), 'destinations_preserved':True, 'photos_preserved':True})

script = ROOT/'assets/enterprise.js'
text=script.read_text(encoding='utf-8')
needle="      if (!address || !status) return;\n      try {"
assert needle in text, 'Unexpected clipboard implementation'
text=text.replace(needle, "      if (!address || !status) return;\n      const href = address.getAttribute('href') || '';\n      if (!href.toLowerCase().startsWith('mailto:')) return;\n      let email;\n      try { email = decodeURIComponent(href.slice(7).split('?')[0]); }\n      catch (_) { status.textContent = 'Please use the email link. Nothing has been sent.'; return; }\n      if (!email || !email.includes('@')) return;\n      try {")
text=text.replace('navigator.clipboard.writeText(address.textContent.trim())', 'navigator.clipboard.writeText(email)')
text=text.replace('      } catch (_) {\n        const range', "      } catch (_) {\n        // Reveal the existing inbox only when manual copying is needed.\n        address.textContent = email;\n        const range")
script.write_text(text,encoding='utf-8')
out=ROOT/'qa-output'; out.mkdir(exist_ok=True)
(out/'brand-migration.json').write_text(json.dumps({'brand':'JP Enterprises','pages':REPORT,'existing_email_routes_preserved':True,'legal_registration_claimed':False},indent=2)+'\n')
print(json.dumps({'brand':'JP Enterprises','pages_changed':len(REPORT),'contact_routes':'unchanged'},indent=2))
