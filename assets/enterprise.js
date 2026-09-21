/* Progressive enhancement only. Navigation and FAQ work without JavaScript. */
(() => {
  const menu = document.querySelector('.menu');
  if (menu) {
    menu.addEventListener('click', event => {
      if (event.target.closest('a')) menu.open = false;
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
    document.addEventListener('click', event => {
      if (!menu.contains(event.target)) menu.open = false;
    });
    matchMedia('(min-width:801px)').addEventListener('change', event => {
      if (event.matches) menu.open = false;
    });
  }
  document.querySelectorAll('[data-copy-email]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', async () => {
      const address = document.getElementById(button.dataset.copyEmail);
      const status = document.getElementById(button.getAttribute('aria-describedby'));
      if (!address || !status) return;
      try {
        if (!navigator.clipboard) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(address.textContent.trim());
        status.textContent = 'Email address copied. Nothing has been sent.';
      } catch (_) {
        const range = document.createRange();
        range.selectNodeContents(address);
        const selection = window.getSelection();
        if (selection) { selection.removeAllRanges(); selection.addRange(range); }
        status.textContent = 'Copy the selected address using your device’s copy command.';
      }
    });
  });
})();
