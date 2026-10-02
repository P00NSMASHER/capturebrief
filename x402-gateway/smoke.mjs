import assert from 'node:assert/strict';
import { ROUTES, openApi, manifest } from './lib/discovery.mjs';
import { NETWORK, PAY_TO, USDC, paymentDocument } from './lib/payment.mjs';

assert.equal(Object.keys(ROUTES).length, 8, 'expected eight paid routes');
for (const [path, meta] of Object.entries(ROUTES)) {
  assert.match(path, /^\/api\//);
  assert.ok(Number(meta.amount) > 0);
  assert.match(meta.price, /^\$\d+\.\d{3}$/);
  assert.ok(meta.serviceName.length <= 32, path + ' serviceName too long');
  assert.ok(meta.tags.length <= 5, path + ' has too many tags');
  assert.equal(new Set(meta.tags).size, meta.tags.length, path + ' tags must be unique');
  const doc = paymentDocument({ ...meta, path }, 'https://example.test');
  assert.equal(doc.x402Version, 2);
  assert.equal(doc.accepts[0].network, NETWORK);
  assert.equal(doc.accepts[0].asset, USDC);
  assert.equal(doc.accepts[0].payTo, PAY_TO);
  assert.equal(doc.resource.url, 'https://example.test' + path);
  assert.equal(doc.accepts[0].extra.name, 'USD Coin');
  assert.equal(doc.accepts[0].extra.version, '2');
  assert.ok(doc.extensions?.bazaar?.info);
}
const api = openApi('https://example.test');
assert.equal(Object.keys(api.paths).length, 8);
for (const path of Object.keys(ROUTES)) {
  const op = api.paths[path].get;
  assert.equal(op['x-payment-info'].protocols[0].x402.constructor, Object);
  assert.match(op['x-payment-info'].price.amount, /^\d+\.\d{6}$/);
  assert.ok(op.responses['402']);
}
const mf = manifest('https://example.test');
assert.equal(mf.resources.length, 8);
console.log('x402 gateway smoke checks passed');
