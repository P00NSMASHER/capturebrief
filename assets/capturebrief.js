/* Local-only scope-request composer. No field is sent, stored, or fetched here. */
(() => {
  const form = document.getElementById('request-builder');
  if (!form) return;

  const recipient = 'jayp19386@gmail.com';
  const opportunity = document.getElementById('opportunity-url');
  const posture = document.getElementById('current-posture');
  const assumptions = document.getElementById('assumptions');
  const publicOnly = document.getElementById('public-only');
  const copyButton = document.getElementById('copy-request');
  const status = document.getElementById('request-status');

  form.hidden = false;

  const assumptionLines = () => assumptions.value
    .split(/\r?\n/)
    .map(line => line.replace(/^\s*(?:[-*]|\d+[.)])\s*/, '').trim())
    .filter(Boolean);

  const setStatus = (message, error = false) => {
    status.textContent = message;
    status.dataset.state = error ? 'error' : 'ok';
  };

  const compose = () => {
    assumptions.setCustomValidity('');
    if (!form.reportValidity()) {
      setStatus('Complete the required fields before preparing the draft.', true);
      return null;
    }

    let parsed;
    try { parsed = new URL(opportunity.value.trim()); }
    catch (_) {
      opportunity.setCustomValidity('Enter a complete public web link, including https://.');
      opportunity.reportValidity();
      setStatus('Enter a complete public opportunity link.', true);
      return null;
    }
    opportunity.setCustomValidity('');
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      opportunity.setCustomValidity('Use a public http:// or https:// link.');
      opportunity.reportValidity();
      setStatus('Use a public web link—not a private portal or local file.', true);
      return null;
    }

    const lines = assumptionLines();
    if (lines.length > 5) {
      assumptions.setCustomValidity('Include no more than five assumptions.');
      assumptions.reportValidity();
      setStatus('Please narrow the request to five assumptions or fewer.', true);
      return null;
    }
    if (!publicOnly.checked) {
      publicOnly.reportValidity();
      setStatus('Confirm that the request contains only public, non-sensitive information.', true);
      return null;
    }

    const subject = 'CaptureBrief scope request';
    const body = [
      'Hello CaptureBrief,',
      '',
      `Public opportunity link: ${opportunity.value.trim()}`,
      `Current posture: ${posture.value}`,
      '',
      'Assumptions to check:',
      ...lines.map((line, index) => `${index + 1}. ${line}`),
      '',
      'I confirm this request contains only public, non-sensitive information.',
      '',
      'Please confirm fit, source coverage, delivery date, and written terms before payment.'
    ].join('\r\n');

    return {
      subject,
      body,
      href: `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
      plain: `To: ${recipient}\nSubject: ${subject}\n\n${body.replace(/\r\n/g, '\n')}`
    };
  };

  [opportunity, posture, assumptions, publicOnly].forEach(control => {
    control.addEventListener('input', () => {
      control.setCustomValidity('');
      status.textContent = '';
      delete status.dataset.state;
    });
  });

  form.addEventListener('submit', event => {
    event.preventDefault();
    const draft = compose();
    if (!draft) return;
    setStatus('Your browser was asked to open an email draft. Review it before sending. Nothing was sent by this page.');
    window.location.href = draft.href;
  });

  copyButton.addEventListener('click', async () => {
    const draft = compose();
    if (!draft) return;
    try {
      if (!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(draft.plain);
      setStatus('Request copied. Paste it into your email service and review it before sending.');
    } catch (_) {
      const helper = document.createElement('textarea');
      helper.value = draft.plain;
      helper.setAttribute('readonly', '');
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      helper.select();
      const copied = document.execCommand && document.execCommand('copy');
      helper.remove();
      setStatus(
        copied
          ? 'Request copied. Paste it into your email service and review it before sending.'
          : 'Copy was unavailable. Use “Email JP Enterprises” below instead.',
        !copied
      );
    }
  });
})();
