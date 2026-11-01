/* CaptureBrief 3.0 decision desk. Local only: no network, storage, or submission. */
(() => {
  'use strict';
  const desk = document.getElementById('v3-question-desk');
  const form = document.getElementById('request-builder');
  const type = document.getElementById('purchase-status');
  const assumptions = document.getElementById('assumptions');
  const meter = document.getElementById('v3-question-meter');
  if (!desk || !form || !type || !assumptions || !meter || form.hidden) return;
  // Preserve manually edited buyer wording when free-check templates are clicked.
  let lastFreeTemplate = null;

  const templates = Object.freeze({
    deadline: 'The response deadline has not changed in the latest public notice or amendment.',
    amendment: 'The solicitation instructions we are using are the latest controlling public version.',
    eligibility: 'The public notice confirms that our intended competition pool is eligible to respond.',
    submission: 'The current public instructions allow our planned response length and submission method.',
    rule: 'The cited public rule edition applies to this opportunity as written.'
  });
  const entries = () => assumptions.value.split(/\r?\n/)
    .map(line => line.replace(/^\s*(?:[-*]|[1-5][.)])\s+/, '').trim()).filter(Boolean);
  const fingerprint = line => line.toLowerCase().replace(/\s+/g, ' ').trim();
  const render = () => {
    const count = entries().length;
    const limit = type.value === 'FREE_CHECK' ? 1 : 5;
    meter.textContent = count + ' of ' + limit + ' question' + (limit === 1 ? '' : 's') +
      ' entered. ' + (count > limit ? 'Narrow to the permitted number before drafting.' :
      'Edit the wording to match your own public-source assumption.');
  };
  for (const button of desk.querySelectorAll('[data-assumption-template]')) {
    button.addEventListener('click', () => {
      const suggested = templates[button.getAttribute('data-assumption-template')];
      if (!suggested) return;
      const before = entries();
      if (type.value === 'FREE_CHECK') {
        const current = assumptions.value.trim();
        if (current && current !== lastFreeTemplate) {
          meter.textContent = 'Your question was kept. Clear it before choosing a suggested question.';
          return;
        }
        assumptions.value = suggested;
        lastFreeTemplate = suggested;
      } else if (before.some(line => fingerprint(line) === fingerprint(suggested))) {
        meter.textContent = 'This question is already in your draft; edit it below if needed.';
        return;
      } else if (before.length >= 5) {
        meter.textContent = 'Five questions is the limit. Remove one before adding another.';
        return;
      } else {
        assumptions.value = assumptions.value.trim()
          ? assumptions.value.trimEnd() + '\n' + suggested : suggested;
      }
      // Dispatch input so the canonical request composer invalidates stale copies.
      assumptions.dispatchEvent(new Event('input', { bubbles: true }));
      render();
    });
  }
  type.addEventListener('change', render);
  assumptions.addEventListener('input', render);
  desk.hidden = false;
  render();
})();