# Website quality upgrade — September 21, 2026

## CaptureBrief glossy direct-sale revision — September 23, 2026

CaptureBrief now uses a custom editorial visual system: deep petroleum, lacquered
oxblood, acid chartreuse, bone paper and chrome highlights. Newsreader, Familjen
Grotesk and Azeret Mono replace the generic SaaS typography. Five high-quality
images are hosted locally: four original project images and one attributed
Unsplash architecture photograph. PermitPlate and FreightRecovery remain unchanged.

The CaptureBrief buyer path now includes a concrete deliverable preview, five
plain-language evidence states, the exact $149 scope, a named founder/operator,
full privacy/data-handling/terms pages, and a browser-local request builder. The
builder has no network action, storage, or file upload; it only prepares an email
draft or clipboard copy after the buyer confirms the public/non-sensitive data
boundary. Buyers can now use the $149 Stripe checkout directly, while the free
scope-check route remains available. The purchase-status field distinguishes paid
order intake from pre-purchase questions, and out-of-scope paid requests are
promised a full refund before work begins.

Website QA separately enforces the five-image contract, direct-checkout count,
local request behavior, legal links, no-JavaScript fallback, responsive layout,
and unchanged PermitPlate/FreightRecovery offers.

Scope: the existing CaptureBrief, PermitPlate and FreightRecovery GitHub Pages homepages on gh-pages. Product code and the default branch are untouched.

## Changes
- Isolate the three-site design in assets/enterprise.css and restore the original assets/site.css for the unrelated portfolio pages.
- Replace dense hero copy with concise product explanations; retain $149 CaptureBrief, $79/month PermitPlate and scoped FreightRecovery pricing.
- Use five photographic placements per page with responsive source sets, explicit image dimensions, lazy secondary images and one prioritized hero.
- Add native-details mobile navigation and FAQ; add Escape/focus handling and close-on-selection as progressive enhancement.
- Fix narrow-grid intrinsic sizing and explicitly give white cards dark text.
- Make illustrative sample status prominent; no fabricated customer logos, endorsements or results.
- Provide visible email, an honest copy fallback and explicit email-app behavior. No fake form-success state and no confidential uploads.
- Restore scope-first CaptureBrief inquiries while retaining the existing checkout link for confirmed scopes.
- Preserve earlier freight sample terms explicitly.
- Add canonical and social-preview metadata.

## Verification
The local offline Chromium layout pass covered 1440, 1024, 768, 390 and 320 pixels on all three pages, mobile menu interaction, FAQ interaction, clipboard-unavailable behavior and no-JavaScript navigation. After repairing intrinsic image sizing, it reported no horizontal overflow or JavaScript exceptions. External image loading was not available in the local environment and is not represented as locally verified.

The Website quality workflow tests the actual committed HTML/CSS/JS with live image requests in Chromium. On gh-pages it additionally waits for the public release marker and runs the same checks against the published URLs. Consult the actual workflow result; this document does not pre-assert that a future run has passed.

Screenshots and JSON reports are retained as workflow artifacts for seven days. Solid-color controls and badges are checked for contrast; this is not a full accessibility conformance claim or an iOS/Safari certification.

No scheduled tasks, outreach, payments or customer-data operations are part of this change.
