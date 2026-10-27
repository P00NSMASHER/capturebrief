"""Rendered clipboard failure recovery; no mail, checkout or actual clipboard writes."""
from __future__ import annotations
import functools
import hashlib
import json
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

root = Path(os.environ.get('SITE_ROOT', '.')).resolve()
out = Path(os.environ.get('QA_OUTPUT', 'qa-output/clipboard')).resolve()
out.mkdir(parents=True, exist_ok=True)
base = os.environ.get('QA_BASE_URL', '').rstrip('/')
browser_name = os.environ.get('QA_BROWSER', 'chromium')
if browser_name not in ('chromium', 'webkit'):
    raise SystemExit('Unreviewed browser')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass
server = None
if not base:
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
base += '/'
origin = urlsplit(base).netloc
report = {'mode': 'live' if os.environ.get('QA_BASE_URL') else 'build',
          'browser': browser_name, 'base': base, 'cases': [],
          'email_sent': False, 'payment_actions': 0, 'clipboard_writes': 0}
try:
    with sync_playwright() as pw:
        options = {'headless': True}
        if os.name == 'nt' and browser_name == 'chromium':
            options['channel'] = 'msedge'
        browser = getattr(pw, browser_name).launch(**options)
        try:
            for mode in ('throws', 'false', 'missing', 'success'):
                context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
                context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).netloc == origin else route.abort())
                page = context.new_page()
                page.set_default_timeout(4000)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script('''(() => {
                    Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{
                        writeText: async () => {throw new Error('Permission denied by test');}
                    }});
                    document.execCommand = MODE === 'missing' ? undefined : () => {
                        if (MODE === 'throws') throw new Error('Legacy clipboard blocked by test');
                        return MODE === 'success';
                    };
                })();'''.replace('MODE', json.dumps(mode)))
                result = {'case': mode, 'passed': False}
                try:
                    response = page.goto(base, wait_until='domcontentloaded', timeout=30000)
                    assert response is not None and response.status == 200
                    page.locator('#purchase-status').select_option('SCOPE_FIRST')
                    page.locator('#company').fill('Example Federal')
                    page.locator('#work-email').fill('buyer@example.com')
                    page.locator('#opportunity-url').fill('https://example.org/public-notice')
                    page.locator('#current-posture').select_option('HOLD')
                    page.locator('#assumptions').fill('Confirm the published deadline.')
                    page.locator('#public-only').check()
                    page.locator('#copy-request').click()
                    expected = 'Request copied.' if mode == 'success' else 'Copy was unavailable.'
                    expect(page.locator('#request-status')).to_contain_text(expected)
                    assert page.locator('body > textarea[readonly]').count() == 0, 'temporary draft field retained'
                    if mode == 'success':
                        expect(page.locator('#copy-request')).to_be_focused()
                        expect(page.locator('#request-manual-copy')).to_be_hidden()
                    else:
                        expect(page.locator('#request-plaintext')).to_be_focused()
                        expect(page.locator('#request-plaintext')).to_have_value(re.compile('Company: Example Federal'))
                    assert not errors, 'unhandled page error: ' + repr(errors)
                    result['passed'] = True
                    result['status_text'] = page.locator('#request-status').inner_text()
                except Exception as exc:
                    result['error'] = str(exc)[:700]
                    result['page_errors'] = errors
                report['cases'].append(result)
                context.close()
            request = browser.new_context()
            response = request.request.get(base + 'assets/capturebrief.js')
            assert response.status == 200
            report['served_script_sha256'] = hashlib.sha256(response.body()).hexdigest()
            request.close()
        finally:
            browser.close()
finally:
    if server is not None:
        server.shutdown()
report['passed'] = len(report['cases']) == 4 and all(case['passed'] for case in report['cases'])
(out / 'clipboard-recovery.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
if not report['passed']:
    raise SystemExit('Clipboard recovery regression failed')
