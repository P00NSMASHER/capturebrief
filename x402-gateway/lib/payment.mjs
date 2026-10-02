export const PAY_TO = '0x708f7b52b56eafd7fc1de65fc7752ed732914021';
export const NETWORK = 'eip155:8453';
export const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
export const FACILITATOR = 'https://facilitator.payai.network';

export const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET, OPTIONS',
  'access-control-allow-headers': 'PAYMENT-SIGNATURE, X-PAYMENT, Content-Type, Accept',
  'access-control-expose-headers': 'PAYMENT-REQUIRED, PAYMENT-RESPONSE, x402-settled, x402-price, x402-network, x402-asset, x402-pay-to, Retry-After',
};

export function requirements(amount) {
  return {
    scheme: 'exact',
    network: NETWORK,
    amount: String(amount),
    asset: USDC,
    payTo: PAY_TO,
    maxTimeoutSeconds: 60,
    extra: { name: 'USD Coin', version: '2' },
  };
}

export function bazaarExtension(sampleQuery, outputExample) {
  const info = {
    input: { type: 'http', method: 'GET', queryParams: sampleQuery },
    output: { type: 'json', example: outputExample },
  };
  return {
    bazaar: {
      info,
      schema: {
        type: 'object',
        properties: {
          input: {
            type: 'object',
            properties: {
              type: { const: 'http' },
              method: { const: 'GET' },
              queryParams: { type: 'object' },
            },
            required: ['type', 'method', 'queryParams'],
            additionalProperties: true,
          },
          output: {
            type: 'object',
            properties: { type: { const: 'json' }, example: {} },
            required: ['type', 'example'],
            additionalProperties: true,
          },
        },
        required: ['input', 'output'],
        additionalProperties: false,
      },
    },
  };
}

export function paymentDocument(meta, baseUrl) {
  return {
    x402Version: 2,
    resource: {
      url: baseUrl + meta.path,
      description: meta.description,
      mimeType: 'application/json',
      serviceName: meta.serviceName,
      tags: meta.tags.slice(0, 5),
    },
    accepts: [requirements(meta.amount)],
    extensions: bazaarExtension(meta.sampleQuery, meta.sampleOutput),
  };
}

export function encodeHeader(value) {
  return Buffer.from(JSON.stringify(value), 'utf8').toString('base64');
}

export function decodePayment(value) {
  if (!value || value.length > 16384) throw new Error('invalid_payment_header');
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const parsed = JSON.parse(Buffer.from(normalized, 'base64').toString('utf8'));
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) || parsed.x402Version !== 2) {
    throw new Error('invalid_payment_payload');
  }
  return parsed;
}

export function getPaymentHeader(req) {
  const value = req.headers['payment-signature'] ?? req.headers['x-payment'];
  return Array.isArray(value) ? value[0] : value;
}

export async function facilitatorPost(kind, paymentPayload, paymentRequirements) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 7000);
  try {
    const response = await fetch(FACILITATOR + '/' + kind, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({
        x402Version: 2,
        paymentPayload,
        paymentRequirements,
      }),
      signal: controller.signal,
    });
    let body = null;
    try { body = await response.json(); } catch {}
    if (!response.ok) {
      const e = new Error('facilitator_' + kind + '_' + response.status);
      e.body = body;
      throw e;
    }
    return body ?? {};
  } finally {
    clearTimeout(timeout);
  }
}

export async function verifyPayment(paymentPayload, meta) {
  const result = await facilitatorPost('verify', paymentPayload, requirements(meta.amount));
  if (result.isValid !== true && result.success !== true) {
    const reason = result.invalidReason ?? result.errorReason ?? 'payment_verification_failed';
    const e = new Error(String(reason));
    e.paymentRejected = true;
    throw e;
  }
  return result;
}

export async function settlePayment(paymentPayload, meta) {
  const result = await facilitatorPost('settle', paymentPayload, requirements(meta.amount));
  if (result.success !== true) {
    const e = new Error(String(result.errorReason ?? 'payment_settlement_failed'));
    e.paymentRejected = true;
    throw e;
  }
  return result;
}

export function sendJson(res, status, body, headers = {}) {
  res.writeHead(status, {
    ...CORS,
    'content-type': 'application/json; charset=utf-8',
    'cache-control': status === 402 ? 'no-store' : 'no-store',
    ...headers,
  });
  res.end(JSON.stringify(body));
}

export function sendPaymentRequired(req, res, meta, reason = 'payment_required') {
  const host = req.headers.host || 'localhost';
  const proto = String(req.headers['x-forwarded-proto'] || 'https').split(',')[0].trim();
  const baseUrl = proto + '://' + host;
  const doc = paymentDocument(meta, baseUrl);
  sendJson(res, 402, {
    error: reason,
    ...doc,
    price: meta.price,
    currency: 'USDC',
    network: NETWORK,
    payTo: PAY_TO,
  }, {
    'PAYMENT-REQUIRED': encodeHeader(doc),
    'x402-price': meta.price,
    'x402-asset': 'USDC',
    'x402-network': NETWORK,
    'x402-pay-to': PAY_TO,
  });
}

export function sendPaid(res, body, settlement) {
  sendJson(res, 200, { ...body, paid: true }, {
    'PAYMENT-RESPONSE': encodeHeader(settlement),
    'x402-settled': 'true',
  });
}
