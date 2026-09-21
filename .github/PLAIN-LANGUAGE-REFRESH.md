# Plain-language and photography refresh

Release marker: 2026-09-21-clarity-3
Scope: the three existing homepages on the CaptureBrief gh-pages branch. No product-engine, pricing, customer-data, outreach or scheduled-task changes.

## Copy
Replace internal vocabulary with buyer questions: what changed, what needs checking, what the buyer receives, and what happens next. Keep government bid scope, missing-record limits, no guaranteed opening/sale/refund, scope-before-payment, confidential-data boundaries and prior freight sample terms. Examples are visibly invented, not proof of customer outcomes.

## Photography
Seven distinct photos per page (21 placements; one desk photo shared across two brands). The previous release had five placements but only three unique photos per page. Photographic cards explain the deliverable, and a separate three-photo section illustrates the buyer context. No repeating an image within a page to inflate the count.

Images are ordinary photographs, not generated webpage mockups. Each has alt text, width/height attributes, source sets with requested crop dimensions, one prioritized hero and lazy loading for the other six. Source paths and licensing references are recorded in PHOTO-SOURCES.md. People, businesses and locations depicted are illustrative, not customers, endorsements or live leads.

## Verification contract
The quality workflow runs the committed build in Chromium and WebKit at 1440, 1024, 768, 390 and 320px. It checks photo count and uniqueness, actual decoding, image visibility, CSS application, horizontal overflow, anchors, menu selection/Escape/focus, FAQs, clipboard behavior, no-JavaScript navigation, targeted text contrast and offer boundaries. Opening explanations are limited to 50 words and a small list of unexplained internal terms is blocked.

Publishing verification waits for exact HTML/CSS bytes, not just a reused marker. On gh-pages the browser checks repeat against the public URLs. Screenshots/reports are retained as workflow artifacts. Read the workflow outcome; this note does not claim a future run has passed. WebKit on Linux is not an iPhone-device or full Safari certification. Targeted contrast tests are not a complete accessibility audit.
