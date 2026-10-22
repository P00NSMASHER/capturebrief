import fs from "node:fs";
import assert from "node:assert/strict";

const workflow = fs.readFileSync(
  new URL("../.github/workflows/pa-entity-discovery.yml", import.meta.url), "utf8"
);

// This repository retains a legacy proxy compatibility fixture. It must not
// contact or register that retired origin during a source regression run.
assert.doesNotMatch(workflow, /verify-live-discovery|capturebrief\.netlify\.app/,
  "the retired Netlify origin must not be treated as a live CaptureBrief service");
assert.doesNotMatch(workflow, /agent402\.tools|\/api\/index\/register|\bcurl\b|\bwget\b|secrets\./,
  "offline compatibility CI must not perform discovery writes or use live credentials");
assert.match(workflow, /permissions:\s*\n\s+contents: read/,
  "legacy contract CI requires only read access");
assert.match(workflow, /persist-credentials: false/,
  "checkout credentials must not remain available to legacy tests");
for (const script of [
  "tests/pa-entity-discovery.test.mjs",
  "tests/pa-entity-proxy.test.mjs",
  "tests/pa-entity-workflow-policy.test.mjs"
]) {
  assert.ok(workflow.includes("node " + script),
    "the offline discovery, single-forward proxy and workflow boundary must remain tested");
}
console.log("PA x402 offline workflow boundary passed.");
