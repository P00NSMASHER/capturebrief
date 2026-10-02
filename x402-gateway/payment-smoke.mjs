import assert from 'node:assert/strict';
import { settlePayment, verifyPayment } from './lib/payment.mjs';

const meta = { amount: '5000' };
const payload = { x402Version: 2, accepted: { scheme: 'exact' }, payload: { authorization: {} } };
const originalFetch = globalThis.fetch;

function response(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

try {
  {
    globalThis.fetch = async () => response(200, { success: true, isValid: false, invalidReason: 'bad_signature' });
    let caught;
    try { await verifyPayment(payload, meta); } catch (e) { caught = e; }
    assert.ok(caught?.paymentRejected, 'verify must fail closed unless isValid === true');
    assert.equal(caught.message, 'bad_signature');
  }

  {
    globalThis.fetch = async () => response(200, { isValid: true });
    const verified = await verifyPayment(payload, meta);
    assert.equal(verified.isValid, true);
  }

  {
    let calls = 0;
    globalThis.fetch = async (_url, options) => {
      calls += 1;
      const body = JSON.parse(options.body);
      assert.deepEqual(body.paymentPayload, payload, 'retries must reuse the exact same payment payload');
      assert.equal(body.paymentRequirements.amount, '5000');
      if (calls === 1) throw new TypeError('simulated transport failure');
      return response(200, { success: true, transaction: '0xabc' });
    };
    const settled = await settlePayment(payload, meta);
    assert.equal(settled.success, true);
    assert.equal(calls, 2, 'transient failure should retry once with same authorization');
  }

  {
    globalThis.fetch = async () => response(400, { success: false, errorReason: 'invalid_payment' });
    let caught;
    try { await settlePayment(payload, meta); } catch (e) { caught = e; }
    assert.ok(caught?.paymentRejected, 'terminal settlement failure must be rejected');
    assert.equal(caught.message, 'invalid_payment');
  }

  {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      throw new TypeError('simulated transport failure');
    };
    let caught;
    try { await settlePayment(payload, meta); } catch (e) { caught = e; }
    assert.ok(caught?.paymentUnresolved, 'repeated transport ambiguity must not be labelled unpaid');
    assert.equal(calls, 3);
  }

  console.log('payment lifecycle smoke checks passed');
} finally {
  globalThis.fetch = originalFetch;
}
