"""Buyer-path checks. Never activate mailto, checkout, uploads, or submissions."""
from __future__ import annotations
import functools
import hashlib
import json
import os
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get('SITE_ROOT', '.')).resolve()
OUT = Path(os.environ.get('QA_OUTPUT', '.qa-output/buyer')).resolve()
OUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get('QA_BASE_URL', '').rstrip('/')
WIDTHS = [1440, 1024, 768, 390, 320]
REPORT = {'mode': 'live' if BASE else 'build', 'assertions': 0, 'errors': [], 'viewports': [], 'actions_sent': 0}

def check(condition, message):
    REPORT['assertions'] += 1
    if not condition:
        REPORT['errors'].append(message)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
base = BASE + '/' if BASE else f'http://127.0.0.1:{server.server_port}/'

def navigate(page, path):
    response = page.goto(base + path, wait_until='domcontentloaded', timeout=30000)
    check(response is not None and response.status == 200, f'{path}: HTTP 200')

try:
    manifest = json.loads((ROOT / 'examples/manifest.json').read_text())
    check(manifest['fictional'] is True and manifest['government_source'] is False, 'Manifest must label invented evidence')
    expected_paths = {'examples/original.txt','examples/amendment-02.txt','examples/incorporation.txt','examples/rule-2025.txt','examples/rule-2026.txt'}
    check({r['path'] for r in manifest['files']} == expected_paths, 'Exactly five example files')
    hashes = {}
    for row in manifest['files']:
        data = (ROOT / row['path']).read_bytes()
        hashes[row['path']] = hashlib.sha256(data).hexdigest()
        check(hashes[row['path']] == row['sha256'] and len(data) == row['bytes'], row['path'] + ': hash and length match')
        check(data.decode().startswith('FICTIONAL EXAMPLE ONLY'), row['path'] + ': fictional label')

    with sync_playwright() as pw:
        options = {'headless': True}
        if os.environ.get('QA_CHROMIUM_PATH'):
            options['executable_path'] = os.environ['QA_CHROMIUM_PATH']
        browser = pw.chromium.launch(**options)
        try:
            for enabled in [True, False]:
                context = browser.new_context(java_script_enabled=enabled, viewport={'width':1440,'height':900}, reduced_motion='reduce')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                navigate(page, 'index.html')
                check(page.locator('a[href="decision-evidence.html"]').count() >= 2, 'Home has prominent full-example links')
                mail = page.locator('#scope-request-draft')
                href = urlsplit(mail.get_attribute('href'))
                query = parse_qs(href.query)
                check(href.scheme == 'mailto' and href.path == 'jayp19386@gmail.com', 'Draft recipient preserved')
                check(set(query) == {'subject', 'body'}, 'Draft includes only subject/body, not extra recipients')
                body = query.get('body', [''])[0]
                for field in ['Public opportunity link:', 'Current decision (GO / HOLD / PASS):', 'Assumption to check:']:
                    check(field in body, 'Prefilled draft includes '+field)
                check('Nothing is submitted here' in page.locator('#draft-note').inner_text(), 'Honest email-draft status')
                check(page.locator('form, input[type="file"]').count() == 0, 'No form or upload added')
                check(page.locator('a[href="https://book.stripe.com/cNi7sLbRp95BbpR7Pb9sk01"]').count() == 1, 'Existing checkout unchanged')
                # Read href only. Do not click draft/checkout or transmit a message.
                page.locator('#full-evidence-link').click()
                check(urlsplit(page.url).path.endswith('/decision-evidence.html'), 'Full sample navigation works')
                check(page.locator('h1').count() == 1, 'Example has one H1')
                check('Fictional example' in page.locator('.fiction-label').inner_text(), 'Fictional warning visible')
                check(page.locator('form, input, script').count() == 0, 'Example has no submission inputs or scripts')
                # Inspect actual visible text, not innerText of closed disclosures.
                for details in page.locator('details').all():
                    if details.get_attribute('open') is None:
                        details.locator(':scope > summary').click()
                for quote in page.locator('blockquote[data-source]').all():
                    check(quote.is_visible(), 'Quoted passage is visible after disclosure')
                    source = quote.get_attribute('data-source')
                    line = int(quote.get_attribute('data-line'))
                    check(quote.inner_text() == (ROOT/source).read_text().splitlines()[line-1], 'Exact quote '+source+':'+str(line))
                for code in page.locator('[data-hash-for]').all():
                    check(code.is_visible(), 'Fingerprint is visible after disclosure')
                    check(code.inner_text() == hashes[code.get_attribute('data-hash-for')], 'Displayed fingerprint matches file')
                check(page.locator('.finding-card').count() == 3, 'Three bounded example findings')
                for width in WIDTHS:
                    page.set_viewport_size({'width':width,'height':900})
                    for details in page.locator('details').all():
                        if details.get_attribute('open') is None:
                            details.locator(':scope > summary').click()
                    dims = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth})')
                    check(dims['scroll'] <= width+1 and dims['body'] <= width+1, f'{width}/JS={enabled}: no overflow with every source/hash expanded')
                    REPORT['viewports'].append({**dims,'javascript_enabled':enabled})
                    if enabled and width in [1440,768,390,320]:
                        page.evaluate('window.scrollTo(0,0)')
                        page.screenshot(path=str(OUT/f'evidence-expanded-{width}.png'),full_page=True)
                    for details in reversed(page.locator('details').all()):
                        if details.get_attribute('open') is not None:
                            details.locator(':scope > summary').click()
                    check(page.locator('details[open]').count() == 0, 'Disclosure controls close')
                if enabled:
                    summary = page.locator('#pages > details > summary')
                    summary.focus(); page.keyboard.press('Enter')
                    check(page.locator('#pages > details').get_attribute('open') is not None, 'Keyboard opens evidence')
                    page.keyboard.press('Enter')
                    check(page.locator('#pages > details').get_attribute('open') is None, 'Keyboard closes evidence')
                for path in sorted(expected_paths | {'examples/manifest.json'}):
                    response = context.request.get(base+path)
                    check(response.status == 200 and response.body() == (ROOT/path).read_bytes(), 'Served source bytes match '+path)
                page.locator('.evidence-cta a').click()
                check(urlsplit(page.url).fragment == 'request', 'Sample returns buyer to scope request')
                check(not errors, 'No browser errors: '+repr(errors))
                context.close()
        finally:
            browser.close()
except Exception as exc:
    REPORT['errors'].append(type(exc).__name__ + ': ' + str(exc))
finally:
    server.shutdown()
    REPORT['passed'] = not REPORT['errors']
    (OUT/'report.json').write_text(json.dumps(REPORT, indent=2)+'\n')
    print(json.dumps(REPORT, indent=2))
raise SystemExit(0 if REPORT['passed'] else 1)
