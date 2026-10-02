import http from 'node:http';
import {
  CORS,
  decodePayment,
  getPaymentHeader,
  sendJson,
  sendPaid,
  sendPaymentRequired,
  settlePayment,
  verifyPayment,
} from './lib/payment.mjs';
import {
  censusGeocode,
  domainRdap,
  ofacScreen,
  paBest,
  paSearch,
  secFilings,
  treasuryRates,
  vendorIntakeGate,
} from './lib/sources.mjs';
import { ROUTES, homepage, llmsText, manifest, openApi, skillText } from './lib/discovery.mjs';

const PORT = Number(process.env.PORT || 3000);

function baseUrl(req) {
  const forwarded = req.headers['x-forwarded-proto'];
  const proto = forwarded ? String(forwarded).split(',')[0].trim() : (req.socket?.encrypted ? 'https' : 'http');
  return proto + '://' + (req.headers.host || 'localhost:' + PORT);
}

function sendText(res, status, text, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(status, { ...CORS, 'content-type': contentType, 'cache-control': 'no-store' });
  res.end(text);
}

function first(search, key) {
  const value = search.get(key);
  return value == null ? undefined : value;
}

function integer(search, key, fallback) {
  const raw = first(search, key);
  if (raw == null || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

async function execute(path, search) {
  switch (path) {
    case '/api/pa-entity-one':
      return paBest(first(search, 'q'));
    case '/api/pa-business':
      return paSearch(first(search, 'q'), integer(search, 'limit', 10));
    case '/api/vendor-intake-gate':
      return vendorIntakeGate({
        name: first(search, 'name'),
        address: first(search, 'address'),
        domain: first(search, 'domain'),
      });
    case '/api/sec-filings': {
      const ticker = first(search, 'ticker');
      const cik = first(search, 'cik');
      if (!ticker && !cik) throw new Error('ticker_or_cik_required');
      return secFilings({
        ticker,
        cik,
        form: first(search, 'form'),
        limit: integer(search, 'limit', 10),
      });
    }
    case '/api/us-address-geocode':
      return censusGeocode(first(search, 'address'));
    case '/api/ofac-sdn-screen':
      return ofacScreen(first(search, 'name'), integer(search, 'limit', 5), integer(search, 'minScore', 85));
    case '/api/domain-rdap':
      return domainRdap(first(search, 'domain'));
    case '/api/treasury-average-rates':
      return treasuryRates(first(search, 'security') || '');
    default:
      throw new Error('not_found');
  }
}

function sourceErrorStatus(err) {
  const message = String(err?.message || err || '');
  if (message === 'company_not_found' || message === 'not_found') return 404;
  if (
    message.startsWith('invalid_') ||
    message === 'ticker_or_cik_required'
  ) return 400;
  return 502;
}

function safeReason(err) {
  const message = String(err?.message || err || '');
  if (message === 'company_not_found') return 'Company not found; payment was not settled.';
  if (message === 'ticker_or_cik_required') return 'Provide ticker or cik.';
  if (message.startsWith('invalid_')) return message;
  return 'Authoritative public source is temporarily unavailable; payment was not settled.';
}

async function paidRoute(req, res, url, meta) {
  const routeMeta = { ...meta, path: url.pathname };
  const signature = getPaymentHeader(req);
  if (!signature) {
    sendPaymentRequired(req, res, routeMeta);
    return;
  }

  let payload;
  try {
    payload = decodePayment(signature);
  } catch {
    sendPaymentRequired(req, res, routeMeta, 'invalid_payment_header');
    return;
  }

  try {
    await verifyPayment(payload, routeMeta);
  } catch (err) {
    if (err?.paymentRejected) {
      sendPaymentRequired(req, res, routeMeta, String(err.message || 'payment_verification_failed'));
    } else {
      sendJson(res, 503, { error: 'payment_verifier_unavailable', paid: false });
    }
    return;
  }

  let result;
  try {
    result = await execute(url.pathname, url.searchParams);
  } catch (err) {
    sendJson(res, sourceErrorStatus(err), { error: safeReason(err), paid: false });
    return;
  }

  let settlement;
  try {
    settlement = await settlePayment(payload, routeMeta);
  } catch (err) {
    if (err?.paymentRejected) {
      sendPaymentRequired(req, res, routeMeta, String(err.message || 'payment_settlement_failed'));
    } else if (err?.paymentUnresolved) {
      sendJson(res, 503, {
        error: 'payment_settlement_state_unknown',
        reason: String(err.message || 'settlement_unknown'),
        retrySamePayment: true,
        resultServed: false,
      });
    } else {
      sendJson(res, 503, { error: 'payment_settlement_unavailable', resultServed: false });
    }
    return;
  }

  sendPaid(res, result, settlement);
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS);
    res.end();
    return;
  }

  const origin = baseUrl(req);
  const url = new URL(req.url || '/', origin);

  if (req.method !== 'GET') {
    sendJson(res, 405, { error: 'method_not_allowed' }, { allow: 'GET, OPTIONS' });
    return;
  }

  if (url.pathname === '/health') {
    sendJson(res, 200, {
      ok: true,
      service: 'agent-data-tools-x402',
      routes: Object.keys(ROUTES).length,
      paymentNetwork: 'eip155:8453',
    });
    return;
  }

  if (url.pathname === '/openapi.json') {
    sendJson(res, 200, openApi(origin), { 'cache-control': 'public, max-age=300' });
    return;
  }

  if (url.pathname === '/.well-known/x402') {
    sendJson(res, 200, manifest(origin), { 'cache-control': 'public, max-age=300' });
    return;
  }

  if (url.pathname === '/llms.txt') {
    sendText(res, 200, llmsText(origin), 'text/plain; charset=utf-8');
    return;
  }

  if (url.pathname === '/skill.md') {
    sendText(res, 200, skillText(origin), 'text/markdown; charset=utf-8');
    return;
  }

  if (url.pathname === '/') {
    sendText(res, 200, homepage(origin), 'text/html; charset=utf-8');
    return;
  }

  const meta = ROUTES[url.pathname];
  if (!meta) {
    sendJson(res, 404, { error: 'not_found' });
    return;
  }

  await paidRoute(req, res, url, meta);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log('agent-data-tools-x402 listening on port ' + PORT);
});
