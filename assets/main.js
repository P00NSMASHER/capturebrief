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
