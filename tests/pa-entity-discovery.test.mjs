import fs from "node:fs";
import assert from "node:assert/strict";

const ROOT = new URL("../", import.meta.url);
const readJson = path =>
  JSON.parse(fs.readFileSync(new URL(path, ROOT), "utf8"));

const manifest = readJson("x402/pa-entity/.well-known/x402");
const openapi = readJson("x402/pa-entity/openapi.json");

const EXPECTED = {
  resource: "https://pa-entity-x402.floot.app/_api/pa-business",
  apiServer: "https://pa-entity-x402.floot.app/_api",
  price: "$0.005",
  amount: "5000",
  network: "eip155:8453",
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  payTo: "0x708f7b52b56eafd7fc1de65fc7752ed732914021"
};

assert.ok(fs.existsSync(new URL(".nojekyll", ROOT)),
  ".nojekyll is required so GitHub Pages serves .well-known verbatim");

assert.equal(manifest.x402Version, 2);
assert.equal(manifest.resources.length, 1);

const resource = manifest.resources[0];
assert.equal(resource.resource, EXPECTED.resource);
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

const operation = openapi.paths?.["/pa-business"]?.get;
assert.ok(operation, "OpenAPI must catalogue the existing /pa-business paid route");
assert.equal(operation.operationId, "searchPennsylvaniaBusinesses");
assert.equal(operation["x-payment-info"]?.price?.amount, "0.005000");
assert.equal(operation["x-payment-info"]?.price?.currency, "USD");
assert.deepEqual(operation["x-payment-info"]?.protocols, [{ x402: {} }]);

const serialized = JSON.stringify({ manifest, openapi });
assert.ok(!serialized.includes("api-v2.appdeploy.ai"),
  "discovery files must not silently switch the paid route to AppDeploy");
assert.ok(!serialized.includes("agent-data-tools-x402.netlify.app"),
  "discovery files must not silently switch the paid route to Netlify");

console.log("PA x402 discovery regression: PASS");
