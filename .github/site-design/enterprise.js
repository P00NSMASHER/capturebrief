/* Navigation enhancement only. No tracking, storage, or form submission. */
(() => {
  'use strict';
  const header = document.querySelector('.ed-header');
  const button = header?.querySelector('.ed-menu');
  const nav = header?.querySelector('.ed-nav');
  if (!header || !button || !nav) return;
  header.dataset.enhanced = 'true';
  function close(returnFocus = false) {
    nav.removeAttribute('data-open');
    button.setAttribute('aria-expanded', 'false');
    button.textContent = 'Menu';
    if (returnFocus) button.focus();
  }
  button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? 'Close' : 'Menu';
    if (open) nav.setAttribute('data-open', '');
    else nav.removeAttribute('data-open');
  });
  nav.addEventListener('click', event => {
    if (event.target.closest('a')) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') close(true);
  });
  document.addEventListener('click', event => {
    if (!header.contains(event.target)) close();
  });
  const desktop = window.matchMedia('(min-width: 851px)');
  desktop.addEventListener('change', () => close());
})();
