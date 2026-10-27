/* Local-only review/trial request composer. No field is sent, stored, or fetched here. */
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

  const recipient = 'jay@retallyrecovery.com';
  const purchaseStatus = document.getElementById('purchase-status');
  const company = document.getElementById('company');
  const email = document.getElementById('work-email');
  const opportunity = document.getElementById('opportunity-url');
  const posture = document.getElementById('current-posture');
  const assumptions = document.getElementById('assumptions');
  const publicOnly = document.getElementById('public-only');
  const copyButton = document.getElementById('copy-request');
  const status = document.getElementById('request-status');
  const hint = document.getElementById('assumption-hint');
  const trialTerms = document.getElementById('trial-terms');
  const manualCopy = document.getElementById('request-manual-copy');
  const manualText = document.getElementById('request-plaintext');

  const resetManualCopy = () => {
    manualText.value = '';
    manualCopy.hidden = true;
  };
  const revealManualCopy = plain => {
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

  const updateRequestType = () => {
    const free = purchaseStatus.value === 'FREE_CHECK';
    if (hint) hint.textContent = free ? 'One assumption, up to 500 characters' : 'One per line, up to five; 500 characters each';
    if (trialTerms) trialTerms.hidden = !free;
    assumptions.setCustomValidity('');
    purchaseStatus.setCustomValidity('');
    resetManualCopy();
  };

  const checkoutReturn = new URLSearchParams(window.location.search).get('checkout') === 'complete';
  if (checkoutReturn) {
    purchaseStatus.value = 'PAID';
    setStatus('Welcome back from Stripe. Complete this intake. Payment is verified separately before work begins.');
  } else if (new URLSearchParams(window.location.search).get('trial') === 'free') {
    purchaseStatus.value = 'FREE_CHECK';
  }
  updateRequestType();
  purchaseStatus.addEventListener('change', updateRequestType);
  document.querySelectorAll('[data-request-type]').forEach(link => {
    link.addEventListener('click', () => {
      purchaseStatus.value = link.dataset.requestType;
      updateRequestType();
      status.textContent = '';
    });
  });

  const compose = () => {
    assumptions.setCustomValidity('');
    const free = purchaseStatus.value === 'FREE_CHECK';
    const fail = (control, message) => {
      control.setCustomValidity(message);
      control.reportValidity();
      setStatus(message, true);
      return null;
    };
    if (!['PAID', 'SCOPE_FIRST', 'FREE_CHECK'].includes(purchaseStatus.value)) {
      return fail(purchaseStatus, 'Choose the kind of request you want to prepare.');
    }
    if (!company.value.trim() || company.value.trim().length > 200 || /[\r\n\x00-\x1f]/.test(company.value)) {
      return fail(company, 'Enter your company name on one line, up to 200 characters.');
    }
    const emailText = email.value.trim();
    if (emailText.length > 254 || !/^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/.test(emailText)) {
      return fail(email, 'Enter a valid work email address.');
    }
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
    const host = parsed.hostname.toLowerCase().replace(/\.$/, '');
    if (parsed.username || parsed.password || opportunity.value.trim().length > 2048 ||
        !host.includes('.') || /^\d+(?:\.\d+){3}$/.test(host) || host.includes(':') ||
        /(?:^localhost$|\.(?:local|localhost|internal|home\.arpa|invalid|test)$)/.test(host)) {
      return fail(opportunity, 'Use a named public website without credentials or a private/local address.');
    }

    const lines = assumptionLines();
    if (!lines.length || (free && lines.length !== 1) || lines.length > 5) {
      return fail(assumptions, free
        ? 'The free check covers exactly one assumption. Choose the question that matters most.'
        : 'Please include one to five assumptions; narrow the request to five assumptions or fewer.');
    }
    if (lines.some(line => line.length > 500)) {
      return fail(assumptions, 'Keep each assumption to 500 characters or fewer.');
    }
    if (new Set(lines.map(line => line.toLowerCase().replace(/\s+/g, ' '))).size !== lines.length) {
      return fail(assumptions, 'Each assumption must ask a different question. Remove duplicate lines.');
    }
    if (!publicOnly.checked) {
      publicOnly.reportValidity();
      setStatus('Confirm that the request contains only public, non-sensitive information.', true);
      return null;
    }

    const paid = purchaseStatus.value === 'PAID';
    const subject = free ? 'CaptureBrief free assumption check request'
      : paid ? 'CaptureBrief checkout-reported intake (payment verification needed)' : 'CaptureBrief scope request';
    const body = [
      'Hello CaptureBrief,',
      '',
      `Purchase status (customer-reported, not verified): ${free ? 'Free assumption check requested' : paid ? 'Already purchased' : 'Scope check before purchase'}`,
      `Company: ${company.value.trim()}`,
      `Work email: ${emailText}`,
      `Public opportunity link: ${opportunity.value.trim()}`,
      `Current posture: ${posture.value}`,
      '',
      'Assumptions to check:',
      ...lines.map((line, index) => `${index + 1}. ${line}`),
      '',
      'I confirm this request contains only public, non-sensitive information.',
      '',
      free
        ? 'Please confirm eligibility, source coverage, and delivery date for one free assumption check. I understand there is no charge, no automatic upgrade, and no included change watch.'
        : paid
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

  [purchaseStatus, company, email, opportunity, posture, assumptions, publicOnly].forEach(control => {
    control.addEventListener('input', () => {
      control.setCustomValidity('');
      status.textContent = '';
      delete status.dataset.state;
      resetManualCopy();
    });
  });

  form.addEventListener('submit', event => {
    event.preventDefault();
    const draft = compose();
    if (!draft) return;
    if (draft.href.length > 1900) {
      revealManualCopy(draft.plain);
      setStatus('This request is too long for a reliable email link. Your complete draft is selected below for manual copying. Nothing was sent.', true);
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
      const previousFocus = document.activeElement;
      let copied = false;
      try {
        helper.select();
        copied = typeof document.execCommand === 'function' && document.execCommand('copy') === true;
      } catch (_) {
        copied = false;
      } finally {
        helper.remove();
        if (previousFocus && previousFocus.isConnected && typeof previousFocus.focus === 'function') {
          previousFocus.focus({ preventScroll: true });
        }
      }
      if (copied) {
        resetManualCopy();
        setStatus('Request copied. Paste it into your email service and review it before sending.');
      } else {
        revealManualCopy(draft.plain);
        setStatus('Copy was unavailable. Your complete request is selected below for manual copying. Nothing was sent.', true);
      }
    }
  });
})();

