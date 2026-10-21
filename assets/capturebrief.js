/* Local-only scope-request composer. No field is sent, stored, or fetched here. */
(() => {
  const root = document.documentElement;
  const header = document.querySelector('.header');
  let chromeFrame = 0;

  const updateChrome = () => {
    chromeFrame = 0;
    const scrollRange = Math.max(1, root.scrollHeight - window.innerHeight);
    root.style.setProperty('--page-progress', Math.min(1, window.scrollY / scrollRange).toFixed(4));
    if (header) header.classList.toggle('is-scrolled', window.scrollY > 18);
  };

  const requestChromeUpdate = () => {
    if (chromeFrame) return;
    chromeFrame = requestAnimationFrame(updateChrome);
  };

  updateChrome();
  window.addEventListener('scroll', requestChromeUpdate, { passive: true });
  window.addEventListener('resize', requestChromeUpdate, { passive: true });

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reducedMotion && 'IntersectionObserver' in window) {
    const revealTargets = document.querySelectorAll([
      '.value-grid > div', '.editorial-grid > *', '.feature-grid > *',
      '.process-layout > *', '.sample-grid > *', '.watch-grid > *',
      '.standards-grid > *', '.pricing-grid > *', '.faq-layout > *',
      '.request-grid > *'
    ].join(','));
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -9% 0px', threshold: 0.08 });

    revealTargets.forEach((element, index) => {
      element.dataset.reveal = '';
      element.style.setProperty('--reveal-delay', `${(index % 4) * 55}ms`);
      if (element.getBoundingClientRect().top < window.innerHeight * 0.92) {
        element.classList.add('is-visible');
      } else {
        revealObserver.observe(element);
      }
    });
    document.body.classList.add('reveal-ready');
  }

  if ('IntersectionObserver' in window) {
    const sectionLinks = new Map();
    document.querySelectorAll('.desktop a[href^="#"]').forEach(link => {
      const section = document.querySelector(link.getAttribute('href'));
      if (section) sectionLinks.set(section, link);
    });
    const sectionObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        sectionLinks.forEach(link => {
          link.classList.remove('is-current');
          link.removeAttribute('aria-current');
        });
        const current = sectionLinks.get(entry.target);
        if (current) {
          current.classList.add('is-current');
          current.setAttribute('aria-current', 'location');
        }
      });
    }, { rootMargin: '-22% 0px -68% 0px', threshold: 0 });
    sectionLinks.forEach((_link, section) => sectionObserver.observe(section));
  }

  const form = document.getElementById('request-builder');
  if (!form) return;

  const recipient = 'jayp19386@gmail.com';
  const purchaseStatus = document.getElementById('purchase-status');
  const company = document.getElementById('company-name');
  const workEmail = document.getElementById('work-email');
  const opportunity = document.getElementById('opportunity-url');
  const posture = document.getElementById('current-posture');
  const assumptions = document.getElementById('assumptions');
  const publicOnly = document.getElementById('public-only');
  const copyButton = document.getElementById('copy-request');
  const status = document.getElementById('request-status');
  const manualCopy = document.getElementById('request-manual-copy');
  const manualText = document.getElementById('request-plaintext');

  const resetManualCopy = () => {
    manualText.value = '';
    manualCopy.hidden = true;
  };

  const revealManualCopy = (plain) => {
    manualText.value = plain;
    manualCopy.hidden = false;
    manualText.focus();
    manualText.select();
  };

  form.hidden = false;

  const assumptionLines = () => assumptions.value
    .split(/\r?\n/)
    .map(line => line.replace(/^\s*(?:[-*]|[1-5][.)])\s+/, '').trim())
    .filter(Boolean);

  const setStatus = (message, error = false) => {
    status.textContent = message;
    status.dataset.state = error ? 'error' : 'ok';
  };

  const checkoutReturn = new URLSearchParams(window.location.search).get('checkout') === 'complete';
  if (checkoutReturn) {
    purchaseStatus.value = 'PAID';
    setStatus('Returned from checkout. This link does not verify a payment; CaptureBrief will check the Stripe payment record before work begins.');
  }

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
    const hostname = (parsed.hostname || '').toLowerCase().replace(/\.$/, '');
    const addressLiteral = /^\d+(?:\.\d+){3}$/.test(hostname)
      || hostname.startsWith('[') || /^\d+$/.test(hostname);
    const reservedDomain = hostname === 'localhost'
      || ['.localhost', '.local', '.internal', '.home.arpa', '.invalid', '.test']
        .some(suffix => hostname.endsWith(suffix));
    if (parsed.username || parsed.password || !hostname.includes('.') || addressLiteral || reservedDomain) {
      opportunity.setCustomValidity('Provide a public domain link without credentials or direct IP/private hosts.');
      opportunity.reportValidity();
      setStatus('The opportunity link must refer to a public website without embedded credentials or private addresses.', true);
      return null;
    }
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      opportunity.setCustomValidity('Use a public http:// or https:// link.');
      opportunity.reportValidity();
      setStatus('Use a public web link—not a private portal or local file.', true);
      return null;
    }

    if (!company.value.trim()) {
      company.setCustomValidity('Enter your company name.');
      company.reportValidity();
      setStatus('A company name is required to prepare the request.', true);
      return null;
    }
    if (!/^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/.test(workEmail.value.trim())) {
      workEmail.setCustomValidity('Enter a valid work email address.');
      workEmail.reportValidity();
      setStatus('A valid work email address is required.', true);
      return null;
    }
    const lines = assumptionLines();
    if (!lines.length) {
      assumptions.setCustomValidity('Enter at least one assumption.');
      assumptions.reportValidity();
      setStatus('Please include at least one assumption to check.', true);
      return null;
    }
    if (lines.some(line => line.length > 500)) {
      assumptions.setCustomValidity('Each assumption must be 500 characters or fewer.');
      assumptions.reportValidity();
      setStatus('Each assumption must be 500 characters or fewer.', true);
      return null;
    }
    if (new Set(lines.map(line => line.toLowerCase().replace(/\s+/g, ' ').trim())).size !== lines.length) {
      assumptions.setCustomValidity('Remove duplicate assumptions.');
      assumptions.reportValidity();
      setStatus('Remove duplicate assumptions before preparing the draft.', true);
      return null;
    }
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

    const paid = purchaseStatus.value === 'PAID';
    const subject = paid ? 'CaptureBrief checkout-reported intake (payment verification needed)' : 'CaptureBrief scope request';
    const body = [
      'Hello CaptureBrief,',
      '',
      `Purchase status (customer-reported, not verified): ${paid ? 'Already purchased' : 'Scope check before purchase'}`,
      `Company: ${company.value.trim()}`,
      `Work email: ${workEmail.value.trim()}`,
      `Public opportunity link: ${opportunity.value.trim()}`,
      `Current posture: ${posture.value}`,
      '',
      'Assumptions to check:',
      ...lines.map((line, index) => `${index + 1}. ${line}`),
      '',
      'I confirm this request contains only public, non-sensitive information.',
      '',
      paid
        ? 'Please independently verify payment in Stripe, then confirm fit, source coverage, and the delivery date. I understand an out-of-scope request will be refunded before work begins.'
        : 'Please confirm fit, source coverage, delivery date, and written terms before purchase.'
    ].join('\r\n');

    return {
      subject,
      body,
      href: `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
      plain: `To: ${recipient}\nSubject: ${subject}\n\n${body.replace(/\r\n/g, '\n')}`
    };
  };

  [purchaseStatus, company, workEmail, opportunity, posture, assumptions, publicOnly].forEach(control => {
    control.addEventListener('input', () => {
      control.setCustomValidity('');
      status.textContent = '';
      delete status.dataset.state;
      // A revised field invalidates any previously displayed manual draft.
      resetManualCopy();
    });
  });

  form.addEventListener('submit', event => {
    event.preventDefault();
    const draft = compose();
    if (!draft) return;
    // Email-client URL size limits vary; never risk truncating a full request.
    // The copy path keeps all five 500-character assumptions intact.
    if (draft.href.length > 1900) {
      setStatus('This request is too long for a reliable email-draft link. Use “Copy request” and paste the full text into your email instead. Nothing was sent.', true);
      return;
    }
    setStatus('Your browser was asked to open an email draft. Review it before sending. Nothing was sent by this page.');
    window.location.href = draft.href;
  });

  copyButton.addEventListener('click', async () => {
    const draft = compose();
    if (!draft) return;
    try {
      if (!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(draft.plain);
      resetManualCopy();
      setStatus('Request copied. Paste it into your email service and review it before sending.');
    } catch (_) {
      const helper = document.createElement('textarea');
      helper.value = draft.plain;
      helper.setAttribute('readonly', '');
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      let copied = false;
      try {
        helper.select();
        copied = !!(document.execCommand && document.execCommand('copy'));
      } catch (_) {
        // Some privacy configurations throw instead of returning false.
      } finally {
        helper.remove();
      }
      if (copied) {
        resetManualCopy();
        setStatus('Request copied. Paste it into your email service and review it before sending.');
      } else {
        // Never strand a complete five-assumption request just because both
        // clipboard APIs are unavailable; show only a local selectable draft.
        revealManualCopy(draft.plain);
        setStatus('Automatic copying is unavailable. Your complete request is selected below for manual copying. Nothing was sent.', true);
      }
    }
  });
})();
