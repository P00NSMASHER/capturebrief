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

  const checkoutReturn = new URLSearchParams(window.location.search).get('checkout') === 'complete';
  if (checkoutReturn) {
    purchaseStatus.value = 'PAID';
    setStatus('Welcome back from Stripe. Complete this intake. Payment is verified separately before work begins.');
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

    const paid = purchaseStatus.value === 'PAID';
    const subject = paid ? 'CaptureBrief paid order intake' : 'CaptureBrief scope request';
    const body = [
      'Hello CaptureBrief,',
      '',
      `Purchase status: ${paid ? 'Already purchased' : 'Scope check before purchase'}`,
      `Public opportunity link: ${opportunity.value.trim()}`,
      `Current posture: ${posture.value}`,
      '',
      'Assumptions to check:',
      ...lines.map((line, index) => `${index + 1}. ${line}`),
      '',
      'I confirm this request contains only public, non-sensitive information.',
      '',
      paid
        ? 'Please confirm fit, source coverage, and the delivery date. I understand an out-of-scope request will be refunded before work begins.'
        : 'Please confirm fit, source coverage, delivery date, and written terms before purchase.'
    ].join('\r\n');

    return {
      subject,
      body,
      href: `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
      plain: `To: ${recipient}\nSubject: ${subject}\n\n${body.replace(/\r\n/g, '\n')}`
    };
  };

  [purchaseStatus, opportunity, posture, assumptions, publicOnly].forEach(control => {
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
