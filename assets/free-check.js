/* Local-only CaptureBrief FREE_ONE_ASSUMPTION_CHECK request. No fetch, storage, payment or send. */
(function (root) {
  'use strict';
  const SUBJECT = 'CaptureBrief free assumption check request';
  const CLAIM = 'Free assumption check requested';
  const RECIPIENT = 'jay@retallyrecovery.com';
  const END = 'Please confirm eligibility, source coverage, and delivery date for one free assumption check. I understand there is no charge, no automatic upgrade, and no included change watch.';

  function line(value, label, max) {
    if (typeof value !== 'string' || !value.trim() || value.length > max ||
        /[\u0000-\u001f\u007f]/.test(value)) {
      throw new Error(label + ' must be one nonempty line of at most ' + max + ' characters.');
    }
    return value.trim();
  }
  function publicOpportunity(value) {
    const input = line(value, 'Public opportunity URL', 2048);
    let parsed;
    try { parsed = new URL(input); }
    catch (_) { throw new Error('Use a complete public http or https opportunity URL.'); }
    const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password ||
        !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/.test(host) ||
        /\.(?:local|internal|invalid|test|localhost)$/.test(host) ||
        /^(?:\d{1,3}\.){3}\d{1,3}$/.test(host)) {
      throw new Error('Use a public, named opportunity website without credentials.');
    }
    return input;
  }
  function buildFreeCheckDraft(values) {
    if (!values || values.public_only_confirmation !== 'yes') {
      throw new Error('Please confirm that all information is public and non-sensitive.');
    }
    const company = line(values.company, 'Business name', 200);
    const email = line(values.email, 'Work email', 254);
    if (!/^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/.test(email)) {
      throw new Error('Enter a valid work email.');
    }
    const opportunity = publicOpportunity(values.public_opportunity);
    const posture = line(values.current_posture, 'Current posture', 6);
    if (!['GO', 'HOLD', 'PASS', 'UNSURE'].includes(posture)) {
      throw new Error('Select GO, HOLD, PASS, or UNSURE.');
    }
    const assumption = line(values.assumption, 'Assumption', 500);
    const body = [
      'Hello CaptureBrief,', '',
      'Purchase status (customer-reported, not verified): ' + CLAIM,
      'Company: ' + company,
      'Work email: ' + email,
      'Public opportunity link: ' + opportunity,
      'Current posture: ' + posture, '',
      'Assumptions to check:',
      '1. ' + assumption, '',
      'I confirm this request contains only public, non-sensitive information.', '',
      END
    ].join('\n');
    const envelope = 'To: ' + RECIPIENT + '\nSubject: ' + SUBJECT + '\n\n' + body;
    return {
      envelope: envelope,
      body: body,
      subject: SUBJECT,
      mailto: 'mailto:' + RECIPIENT + '?subject=' + encodeURIComponent(SUBJECT) +
              '&body=' + encodeURIComponent(body)
    };
  }
  if (typeof module === 'object' && module.exports) {
    module.exports = { buildFreeCheckDraft: buildFreeCheckDraft };
  }
  if (!root || !root.document) return;
  const form = root.document.querySelector('[data-free-check]');
  if (!form) return;
  const status = root.document.querySelector('[data-free-status]');
  const emailLink = root.document.querySelector('[data-free-email]');
  const copyPanel = root.document.querySelector('[data-free-fallback]');
  const copyText = root.document.querySelector('[data-free-copy]');
  form.addEventListener('input', function () {
    emailLink.hidden = true;
    emailLink.removeAttribute('href');
    copyPanel.hidden = true;
    copyText.value = '';
    status.textContent = 'The request has not been sent or enrolled.';
  });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!form.reportValidity()) return;
    try {
      const draft = buildFreeCheckDraft(Object.fromEntries(new FormData(form)));
      emailLink.setAttribute('href', draft.mailto);
      emailLink.hidden = false;
      copyText.value = draft.envelope;
      copyPanel.hidden = false;
      status.textContent = 'Draft prepared. Open your email app, review, and send it. Your request is not yet received or accepted.';
    } catch (err) {
      emailLink.hidden = true;
      emailLink.removeAttribute('href');
      copyPanel.hidden = true;
      copyText.value = '';
      status.textContent = err.message;
    }
  });
})(typeof globalThis === 'object' ? globalThis : this);
