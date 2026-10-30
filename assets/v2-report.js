'use strict';
// Optional same-origin, no-network print enhancement. The report and all
// evidence links remain readable without JavaScript; no sends or tracking.
document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('print-v2');
  if (!button) return;
  button.addEventListener('click', () => {
    if (typeof window.print === 'function') window.print();
  });
});
