'use strict';
// Execute the actual website script with unavailable clipboard APIs. No network.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

async function exercise(mode) {
  const listeners = {};
  let temporary = 0;
  let focusRestored = false;
  const active = { isConnected: true, focus() { focusRestored = true; } };
  const field = value => ({ value, checked: true, setCustomValidity() {},
    reportValidity() { return true; }, addEventListener() {} });
  const controls = {
    'purchase-status': field('SCOPE'), 'opportunity-url': field('https://example.org/public-notice'),
    'current-posture': field('HOLD'), 'assumptions': field('Confirm the deadline.'),
    'public-only': field(''), 'request-status': { textContent: '', dataset: {} },
    'request-builder': { hidden: true, reportValidity() { return true; }, addEventListener() {} },
    'copy-request': { addEventListener(name, callback) { listeners[name] = callback; } }
  };
  const document = {
    documentElement: { scrollHeight: 1000, style: { setProperty() {} } },
    querySelector() { return null; }, getElementById(id) { return controls[id]; },
    activeElement: active,
    body: { appendChild() { temporary += 1; } },
    createElement() { return { value: '', style: {}, setAttribute() {},
      select() {}, remove() { temporary -= 1; } }; },
    execCommand() { if (mode === 'throws') throw new Error('Browser disabled legacy clipboard'); return mode === 'success'; }
  };
  if (mode === 'missing') delete document.execCommand;
  const context = { document, URL, URLSearchParams, requestAnimationFrame() { return 1; },
    window: { innerHeight: 900, scrollY: 0, location: { search: '' },
      matchMedia() { return { matches: true }; }, addEventListener() {} },
    navigator: { clipboard: { async writeText() { throw new Error('Permission denied'); } } }
  };
  vm.runInNewContext(fs.readFileSync(process.argv[2] || 'assets/capturebrief.js', 'utf8'), context);
  await assert.doesNotReject(listeners.click(), 'A blocked fallback must not reject the click handler');
  assert.equal(temporary, 0, 'Temporary draft textarea must be removed');
  assert.equal(focusRestored, true, 'Keyboard focus must return to the triggering control');
  const status = controls['request-status'];
  if (mode === 'success') {
    assert.match(status.textContent, /Request copied/);
    assert.equal(status.dataset.state, 'ok');
  } else {
    assert.match(status.textContent, /Copy was unavailable/);
    assert.equal(status.dataset.state, 'error');
  }
}
(async () => {
  for (const mode of ['throws', 'false', 'missing', 'success']) {
    await exercise(mode);
    console.log('PASS clipboard fallback: ' + mode);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
