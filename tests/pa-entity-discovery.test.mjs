import fs from "node:fs";
import assert from "node:assert/strict";

const ROOT = new URL("../", import.meta.url);
const read = path => fs.readFileSync(new URL(path, ROOT), "utf8");
const readJson = path => JSON.parse(read(path));

const manifest = readJson("x402/pa-entity/.well-known/x402");
const openapi = readJson("x402/pa-entity/openapi.json");
const build = read("netlify-build.sh");
const netlify = read("netlify.toml");
const proxy = read("netlify/functions/pa-business.mjs");

const EXPECTED = {
  canonicalOrigin: "https://capturebrief.netlify.app",
  resource: "https://capturebrief.netlify.app/api/pa-business",
  apiServer: "https://capturebrief.netlify.app/api",
  upstream: "https://pa-entity-x402.floot.app/_api/pa-business",
  price: "$0.005",
  amount: "5000",
  network: "eip155:8453",
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  payTo: "0x708f7b52b56eafd7fc1de65fc7752ed732914021"
};

assert.ok(fs.existsSync(new URL(".nojekyll", ROOT)),
  ".nojekyll is required so GitHub Pages can serve .well-known verbatim");

assert.equal(manifest.x402Version, 2);
assert.equal(manifest.resources.length, 1);

const resource = manifest.resources[0];
assert.equal(resource.resource, EXPECTED.resource);
assert.equal(new URL(resource.resource).origin, EXPECTED.canonicalOrigin);
assert.equal(resource.method, "GET");
assert.equal(resource.price, EXPECTED.price);
assert.equal(resource.accepts.length, 1);

const payment = resource.accepts[0];
assert.equal(payment.scheme, "exact");
assert.equal(payment.network, EXPECTED.network);
assert.equal(payment.amount, EXPECTED.amount);
assert.equal(payment.asset, EXPECTED.asset);
assert.equal(payment.payTo, EXPECTED.payTo);
assert.equal(payment.maxTimeoutSeconds, 60);
assert.deepEqual(payment.extra, { name: "USD Coin", version: "2" });

assert.equal(openapi.openapi, "3.1.0");
assert.equal(openapi.servers.length, 1);
assert.equal(openapi.servers[0].url, EXPECTED.apiServer);
assert.equal(new URL(openapi.servers[0].url).origin, EXPECTED.canonicalOrigin);

const operation = openapi.paths?.["/pa-business"]?.get;
assert.ok(operation, "OpenAPI must catalogue the existing /pa-business paid capability");
assert.equal(operation.operationId, "searchPennsylvaniaBusinesses");
assert.equal(operation["x-payment-info"]?.price?.amount, "0.005000");
assert.equal(operation["x-payment-info"]?.price?.currency, "USD");
assert.deepEqual(operation["x-payment-info"]?.protocols, [{ x402: {} }]);

assert.match(build, /cp "\$discovery_root\/\.well-known\/x402" dist\/\.well-known\/x402/);
assert.match(build, /cp "\$discovery_root\/openapi\.json" dist\/openapi\.json/);
assert.match(netlify, /from = "\/api\/pa-business"/);
assert.match(netlify, /to = "\/\.netlify\/functions\/pa-business"/);
assert.match(netlify, /for = "\/\.well-known\/x402"/);
assert.match(netlify, /for = "\/openapi\.json"/);
assert.match(netlify, /Content-Type = "application\/json; charset=utf-8"/);

assert.match(proxy, /https:\/\/pa-entity-x402\.floot\.app\/_api\/pa-business/);
assert.match(proxy, /payment-signature/);
assert.match(proxy, /x-payment/);
assert.match(proxy, /Exactly one upstream request/);
assert.ok(!proxy.includes("facilitator.payai.network"),
  "proxy must never duplicate payment verification or settlement");

const discoverySerialized = JSON.stringify({ manifest, openapi });
assert.ok(!discoverySerialized.includes("api-v2.appdeploy.ai"),
  "canonical discovery must not silently switch the seller to AppDeploy");
assert.ok(!discoverySerialized.includes("pa-entity-x402.floot.app"),
  "manifest/OpenAPI must stay same-origin; Floot belongs only behind the transparent proxy");

console.log("PA x402 discovery regression: PASS");
