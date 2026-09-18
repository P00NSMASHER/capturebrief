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


// v5: capture acquisition context only when a visitor chooses to submit the intake form.
const intakeForm = document.querySelector('form[name="pursuit-qa-intake"]');
if (intakeForm) {
  const params = new URLSearchParams(window.location.search);
  const page = intakeForm.querySelector('input[name="source_page"]');
  const utmSource = intakeForm.querySelector('input[name="utm_source"]');
  const utmCampaign = intakeForm.querySelector('input[name="utm_campaign"]');
  if (page) page.value = window.location.pathname;
  if (utmSource) utmSource.value = params.get('utm_source') || '';
  if (utmCampaign) utmCampaign.value = params.get('utm_campaign') || '';
}
