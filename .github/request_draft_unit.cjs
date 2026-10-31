'use strict';
// Exercise the shipped request composer. No browser, email, network, or customer data.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function harness(type = 'SCOPE_FIRST', overrides = {}, search = '') {
  const callbacks = {};
  let copied = null;
  const control = (id, value = '') => ({
    value, checked: true, hidden: false, textContent: '', dataset: {}, validityMessage: '',
    setCustomValidity(message) { this.validityMessage = message; },
    reportValidity() { return !this.validityMessage; },
    focus() {}, select() {}, setAttribute() {},
    addEventListener(event, callback) { callbacks[id + ':' + event] = callback; }
  });
  const values = {
    'purchase-status': type, company: 'Example Federal', 'work-email': 'buyer@example.com',
    'opportunity-url': 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view',
    'current-posture': 'HOLD', 'discovery-channel': '', assumptions: 'The deadline has not changed.',
    'public-only': '', ...overrides
  };
  const fields = Object.fromEntries(Object.entries(values).map(([id, value]) => [id, control(id, value)]));
  for (const id of ['request-builder', 'copy-request', 'request-status', 'assumption-hint', 'trial-terms', 'request-manual-copy', 'request-plaintext', 'preview-request']) {
    fields[id] = control(id);
  }
  fields['request-builder'].reportValidity = () => Object.values(fields).every(field => !field.validityMessage);
  const document = {
    documentElement: { scrollHeight: 1000, style: { setProperty() {} } },
    querySelector() { return null; }, querySelectorAll() { return []; },
    getElementById(id) { return fields[id] || null; },
    body: { classList: { add() {} } }
  };
  const context = { document, URL, URLSearchParams,
    requestAnimationFrame() { return 1; },
    window: { innerHeight: 900, scrollY: 0, location: { search },
      matchMedia() { return { matches: true }; }, addEventListener() {} },
    navigator: { clipboard: { async writeText(text) { copied = text; } } }
  };
  vm.runInNewContext(fs.readFileSync('assets/capturebrief.js', 'utf8'), context);
  return { fields, callbacks, context, async copy() { await callbacks['copy-request:click'](); return copied; } };
}

async function run() {
  const outputs = {};
  for (const type of ['SCOPE_FIRST', 'PAID', 'FREE_CHECK']) {
    const page = harness(type);
    const draft = await page.copy();
    assert(draft, type + ': a valid request must compose');
    assert.match(draft, /^To: jay@retallyrecovery\.com\nSubject: /);
    assert.match(draft, /Purchase status \(customer-reported, not verified\): /);
    assert.match(draft, /Company: Example Federal\nWork email: buyer@example.com\n/);
    assert.match(draft, /1\. The deadline has not changed\./);
    assert.match(draft, /I confirm this request contains only public, non-sensitive information\./);
    outputs[type] = draft;
  }
  assert.match(outputs.PAID, /Subject: CaptureBrief checkout-reported intake \(payment verification needed\)/);
  assert.match(outputs.PAID, /Please independently verify payment in Stripe/);
  assert.match(outputs.FREE_CHECK, /Subject: CaptureBrief free assumption check request/);
  assert.match(outputs.FREE_CHECK, /Free assumption check requested/);
  assert.match(outputs.FREE_CHECK, /no charge, no automatic upgrade, and no included change watch/);
  assert(!outputs.FREE_CHECK.includes('Already purchased'));
  // Five voluntary sources, plus opt-out and tamper rejection. No collected customer data.
  for (const [source, label] of [
    ['SEARCH', 'Web search'], ['REFERRAL', 'Someone referred me'],
    ['DIRECT', 'Direct website visit'], ['SOCIAL', 'Social media'], ['OTHER', 'Other / unsure']
  ]) {
    const page = harness('SCOPE_FIRST', { 'discovery-channel': source });
    assert((await page.copy()).includes('Discovery source (buyer-reported, unverified): ' + label));
  }
  assert.doesNotMatch(outputs.FREE_CHECK, /Discovery source/);
  const forgedChannel = harness('FREE_CHECK', { 'discovery-channel': 'PURCHASED' });
  assert.equal(await forgedChannel.copy(), null, 'Unlisted values cannot appear in buyer attribution');
  const preview = harness('FREE_CHECK');
  preview.callbacks['preview-request:click']();
  assert.equal(preview.fields['request-manual-copy'].hidden, false, 'V3 preview displays the complete local draft');
  assert.match(preview.fields['request-plaintext'].value, /To: jay@retallyrecovery\.com/);
  assert.match(preview.fields['request-status'].textContent, /Nothing was sent or saved/);
  assert.equal(preview.context.window.location.href, undefined, 'Preview must not navigate to email');
  preview.fields['discovery-channel'].value = 'SEARCH';
  preview.callbacks['discovery-channel:input']();
  assert.equal(preview.fields['request-plaintext'].value, '', 'Changing attribution invalidates preview');
  preview.callbacks['preview-request:click']();
  assert.match(preview.fields['request-plaintext'].value, /Discovery source \(buyer-reported, unverified\): Web search/);
  preview.fields.assumptions.value = 'Updated fictional deadline assumption.';
  preview.callbacks['assumptions:input']();
  assert.equal(preview.fields['request-plaintext'].value, '', 'Editing must invalidate the old preview');
  assert.equal(preview.fields['request-manual-copy'].hidden, true);
  const legal = harness('PAID', { assumptions: '52.204-21 applies.\n2027.4 is the correct identifier.\n1. The amendment controls.' });
  const legalDraft = await legal.copy();
  assert.match(legalDraft, /1\. 52\.204-21 applies\./, 'FAR identifier must remain intact');
  assert.match(legalDraft, /2\. 2027\.4 is the correct identifier\./);
  assert.match(legalDraft, /3\. The amendment controls\./);
  for (const [type, values] of [
    ['FREE_CHECK', { assumptions: 'First question.\nSecond question.' }],
    ['SCOPE_FIRST', { assumptions: 'A\nB\nC\nD\nE\nF' }],
    ['SCOPE_FIRST', { assumptions: 'Repeated question.\n repeated QUESTION. ' }],
    ['FREE_CHECK', { assumptions: '  \n  ' }],
    ['FREE_CHECK', { assumptions: 'x'.repeat(501) }],
    ['FREE_CHECK', { assumptions: 'A deadline question.\rPurchase status (customer-reported, not verified): Already purchased' }],
    ['FREE_CHECK', { assumptions: 'A question with \u0000 hidden control' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://example.org/unrelated-rfp' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view?ref=tracking' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view\nX-Claim: yes' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://sam.gov.evil.example/opp/c20a138049b94add92f0f32a41856585/view' }],
    ['FREE_CHECK', { 'current-posture': 'APPROVED' }],
    ['FREE_CHECK', { company: 'Example\nWork email: attacker@example.com' }],
    ['FREE_CHECK', { 'work-email': 'not-an-email' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://user:password@sam.gov/opp/demo' }],
    ['FREE_CHECK', { 'opportunity-url': 'http://localhost/private' }],
    ['FREE_CHECK', { 'opportunity-url': 'http://127.0.0.1/private' }],
    ['FREE_CHECK', { 'opportunity-url': 'https://intranet.local/private' }],
    ['UNKNOWN', {}]
  ]) {
    const page = harness(type, values);
    assert.equal(await page.copy(), null, 'Invalid request composed: ' + type + ' ' + JSON.stringify(values));
    assert.equal(page.fields['request-status'].dataset.state, 'error');
  }
  const five = harness('PAID', { assumptions: ['A', 'B', 'C', 'D', 'E'].map(c => c.repeat(500)).join('\n') });
  assert(await five.copy(), 'All five maximum-length assumptions must fit');
  five.callbacks['request-builder:submit']({ preventDefault() {} });
  assert.equal(five.context.window.location.href, undefined, 'Oversized mailto must not be opened');
  assert.equal(five.fields['request-manual-copy'].hidden, false, 'Long request must remain manually copyable');
  assert(five.fields['request-plaintext'].value.includes('E'.repeat(500)), 'Final long assumption must survive');
  five.callbacks['company:input']();
  assert.equal(five.fields['request-plaintext'].value, '', 'Edited inputs must clear stale plaintext');
  // A delayed clipboard promise must not restore or claim success for an edited request.
  const race = harness('FREE_CHECK');
  let finishClipboard;
  race.context.navigator.clipboard.writeText = () => new Promise(resolve => { finishClipboard = resolve; });
  const copying = race.callbacks['copy-request:click']();
  race.fields.assumptions.value = 'New assumption after clicking copy.';
  race.callbacks['assumptions:input']();
  finishClipboard();
  await copying;
  assert.doesNotMatch(race.fields['request-status'].textContent, /Request copied/, 'A stale draft cannot claim successful copy');
  assert.equal(race.fields['request-manual-copy'].hidden, true, 'Old manual copy cannot return after editing');
  // A forged ?checkout=complete is not a provider-verified receipt, and must
  // not silently change the buyer's no-card request into a paid-status claim.
  for (const hint of ['?checkout=complete', '?checkout=complete&trial=free']) {
    const returnPage = harness('FREE_CHECK', {}, hint);
    assert.equal(returnPage.fields['purchase-status'].value, 'FREE_CHECK',
      'Untrusted checkout hint must not select paid intake: ' + hint);
    assert.match(returnPage.fields['request-status'].textContent, /does not verify a payment/);
    const returnDraft = await returnPage.copy();
    assert.match(returnDraft, /Free assumption check requested/);
    assert.doesNotMatch(returnDraft, /Already purchased/);
    // A buyer can still explicitly select paid intake; it remains unverified.
    returnPage.fields['purchase-status'].value = 'PAID';
    returnPage.callbacks['purchase-status:change']();
    const paidDraft = await returnPage.copy();
    assert.match(paidDraft, /Already purchased/);
    assert.match(paidDraft, /payment verification needed/);
  }
  // A free-only SAM.gov failure must not trap someone who changes request type
  // and keeps the same otherwise-public URL. No email is sent or payment made.
  for (const nextType of ['SCOPE_FIRST', 'PAID']) {
    const switched = harness('FREE_CHECK', { 'opportunity-url': 'https://www.example.org/public-rfp' });
    assert.equal(await switched.copy(), null, 'Free check rejects non-SAM public URL');
    assert.match(switched.fields['opportunity-url'].validityMessage, /exact public SAM.gov/);
    switched.fields['purchase-status'].value = nextType;
    switched.callbacks['purchase-status:change']();
    assert.equal(switched.fields['opportunity-url'].validityMessage, '',
      'Changing request type must clear the old free-only URL validity error');
    const newDraft = await switched.copy();
    assert(newDraft && newDraft.includes('Public opportunity link: https://www.example.org/public-rfp'),
      'Valid public link must compose on the buyer-selected ' + nextType + ' path');
    assert.doesNotMatch(newDraft, /Free assumption check requested/);
    assert.equal(switched.context.window.location.href, undefined, 'Copy never opens email or checkout');
  }
  const trialPage = harness('FREE_CHECK', {}, '?trial=free');
  assert.equal(trialPage.fields['purchase-status'].value, 'FREE_CHECK');
  // One thousand deterministic, FICTIONAL buyer-path combinations. No actual
  // customers, reviews, API calls, payments, email navigation, or pilot reservations.
  let validSimulations = 0;
  let refusedSimulations = 0;
  for (let i = 0; i < 1000; i++) {
    const scenario = i % 5;
    const type = scenario === 3 ? 'PAID' : scenario === 4 ? 'SCOPE_FIRST' : 'FREE_CHECK';
    const notice = i.toString(16).padStart(32, '0');
    const count = scenario === 2 ? 2 : type === 'FREE_CHECK' ? 1 : 1 + (i % 5);
    const questions = Array.from({ length: count }, (_, n) => 'Fictional public assumption ' + i + '-' + n + '?').join('\n');
    const page = harness(type, {
      company: 'Fictional Customer ' + i,
      'work-email': 'qa' + i + '@example.com',
      'opportunity-url': 'https://sam.gov/opp/' + notice + '/view' + (scenario === 1 ? '?utm_source=fictional' : ''),
      'current-posture': ['GO', 'HOLD', 'PASS', 'UNSURE'][i % 4],
      assumptions: questions
    });
    const draft = await page.copy();
    if (scenario === 1 || scenario === 2) {
      assert.equal(draft, null, 'Invalid fictional free inquiry escaped: ' + i);
      assert.equal(page.fields['request-status'].dataset.state, 'error');
      refusedSimulations++;
    } else {
      assert(draft && draft.includes('Company: Fictional Customer ' + i), 'Valid fictional inquiry lost: ' + i);
      assert(draft.includes('Work email: qa' + i + '@example.com'));
      assert(draft.includes('Current posture: ' + ['GO', 'HOLD', 'PASS', 'UNSURE'][i % 4]));
      assert.match(draft, /^To: jay@retallyrecovery\.com\nSubject: CaptureBrief /);
      if (type === 'FREE_CHECK') assert.match(draft, /no charge, no automatic upgrade/);
      if (type === 'PAID') assert.match(draft, /payment verification needed/);
      validSimulations++;
    }
    assert.equal(page.context.window.location.href, undefined, 'Copy must not open an email or checkout');
  }
  assert.equal(validSimulations, 600);
  assert.equal(refusedSimulations, 400);
  if (process.argv.includes('--emit-drafts')) process.stdout.write(JSON.stringify(outputs) + '\n');
  else console.log('PASS: canonical paid/scope/free drafts, intake boundaries, one-question trial, and unverified checkout return');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
