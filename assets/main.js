const menus = document.querySelectorAll('[data-mobile-menu]');
menus.forEach((menu) => {
  const button = menu.querySelector('.menu-toggle');
  const panel = menu.querySelector('.mobile-panel');
  if (!button || !panel) return;

  const setOpen = (open) => {
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    button.textContent = open ? 'Close' : 'Menu';
    panel.hidden = !open;
  };

  setOpen(false);
  button.addEventListener('click', () => {
    setOpen(button.getAttribute('aria-expanded') !== 'true');
  });

  panel.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => setOpen(false));
  });

  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target) && button.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      button.focus();
    }
  });
});


// Capture acquisition context only when a visitor chooses to submit the intake form.
// Treat URL parameters as untrusted: never retain long, link-like, or contact-bearing
// values in Netlify's form queue. These labels are *self-reported*, not verified sales.
const intakeForm = document.querySelector('form[name="pursuit-qa-intake"]');
if (intakeForm) {
  const params = new URLSearchParams(window.location.search);
  const page = intakeForm.querySelector('input[name="source_page"]');
  const utmSource = intakeForm.querySelector('input[name="utm_source"]');
  const utmCampaign = intakeForm.querySelector('input[name="utm_campaign"]');
  const cleanTag = (input) => {
    if (typeof input !== 'string') return '';
    const token = input.trim();
    if (!token || token.length > 64 || !/^[A-Za-z0-9][A-Za-z0-9._+ -]*$/.test(token)) return '';
    return token;
  };
  // Public intake currently lives on the home page. Do not copy arbitrary
  // user-controlled URL paths, query strings, or fragments into form data.
  if (page) page.value = window.location.pathname === '/index.html' ? '/index.html' : '/';
  if (utmSource) utmSource.value = cleanTag(params.get('utm_source'));
  if (utmCampaign) utmCampaign.value = cleanTag(params.get('utm_campaign'));
}
