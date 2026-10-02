import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';

const port = 43127;
const base = 'http://127.0.0.1:' + port;
const samples = [
  ['/api/pa-entity-one?q=OpenAI', '1000'],
  ['/api/pa-business?q=OpenAI&limit=1', '5000'],
  ['/api/vendor-intake-gate?name=OpenAI&address=600%20North%20Second%20Street%2C%20Suite%20401%2C%20Harrisburg%2C%20PA%2017101&domain=openai.com', '20000'],
  ['/api/sec-filings?ticker=AAPL&form=10-K&limit=1', '5000'],
  ['/api/us-address-geocode?address=4600%20Silver%20Hill%20Rd%2C%20Washington%2C%20DC%2020233', '5000'],
  ['/api/ofac-sdn-screen?name=OPENAI&limit=1&minScore=90', '5000'],
  ['/api/domain-rdap?domain=example.com', '5000'],
  ['/api/treasury-average-rates?security=Total%20Marketable', '5000'],
];

function decode(value) {
  return JSON.parse(Buffer.from(value, 'base64').toString('utf8'));
}

const child = spawn(process.execPath, ['server.mjs'], {
  env: { ...process.env, PORT: String(port) },
  stdio: ['ignore', 'pipe', 'pipe'],
});

let stderr = '';
child.stderr.on('data', chunk => { stderr += String(chunk); });

async function waitForServer() {
  for (let i = 0; i < 50; i += 1) {
    try {
      const r = await fetch(base + '/health');
      if (r.ok) return;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server did not start: ' + stderr);
}

try {
  await waitForServer();

  const health = await fetch(base + '/health');
  assert.equal(health.status, 200);
  const hj = await health.json();
  assert.equal(hj.routes, 8);

  const openapi = await fetch(base + '/openapi.json');
  assert.equal(openapi.status, 200);
  const oj = await openapi.json();
  assert.equal(Object.keys(oj.paths).length, 8);

  const manifest = await fetch(base + '/.well-known/x402');
  assert.equal(manifest.status, 200);
  const mj = await manifest.json();
  assert.equal(mj.resources.length, 8);

  for (const [path, amount] of samples) {
    const res = await fetch(base + path);
    assert.equal(res.status, 402, path + ' must challenge before input/source work');
    const header = res.headers.get('payment-required');
    assert.ok(header, path + ' missing PAYMENT-REQUIRED');
    const doc = decode(header);
    assert.equal(doc.x402Version, 2);
    assert.equal(doc.accepts.length, 1);
    assert.equal(doc.accepts[0].network, 'eip155:8453');
    assert.equal(doc.accepts[0].asset.toLowerCase(), '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913');
    assert.equal(doc.accepts[0].payTo.toLowerCase(), '0x708f7b52b56eafd7fc1de65fc7752ed732914021');
    assert.equal(doc.accepts[0].amount, amount);
    assert.equal(doc.accepts[0].extra.name, 'USD Coin');
    assert.equal(doc.accepts[0].extra.version, '2');
    assert.ok(doc.resource.url.startsWith(base + '/api/'));
    assert.ok(doc.extensions?.bazaar?.info);
  }

  console.log('runtime x402 challenge smoke checks passed');
} finally {
  child.kill('SIGTERM');
}
