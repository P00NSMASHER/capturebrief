import { PAY_TO, NETWORK, USDC } from './payment.mjs';

export const ROUTES = {
  '/api/pa-entity-one': {
    price: '$0.001', amount: '1000',
    serviceName: 'PA Entity Best Match',
    tags: ['business-registry', 'entity-resolution', 'Pennsylvania', 'vendor-verification', 'data'],
    description: 'Resolve one best Pennsylvania Department of State business-registry match by company name. Returns source facts only; no risk or good-standing verdict.',
    sampleQuery: { q: 'OpenAI' },
    sampleOutput: { query: 'OpenAI', found: true, match: { businessName: 'Openai Opco, Llc' }, paid: true },
    parameters: [
      { name: 'q', required: true, schema: { type: 'string', minLength: 2, maxLength: 120 }, example: 'OpenAI' },
    ],
  },
  '/api/pa-business': {
    price: '$0.005', amount: '5000',
    serviceName: 'PA Business Registry',
    tags: ['business-registry', 'company-identity', 'Pennsylvania', 'due-diligence', 'data'],
    description: 'Search Pennsylvania Department of State business-registration records by company name and return ranked source records.',
    sampleQuery: { q: 'OpenAI', limit: 5 },
    sampleOutput: { query: 'OpenAI', count: 2, results: [], paid: true },
    parameters: [
      { name: 'q', required: true, schema: { type: 'string', minLength: 2, maxLength: 120 }, example: 'OpenAI' },
      { name: 'limit', required: false, schema: { type: 'integer', minimum: 1, maximum: 25, default: 10 }, example: 5 },
    ],
  },
  '/api/vendor-intake-gate': {
    price: '$0.020', amount: '20000',
    serviceName: 'PA Vendor Intake Gate',
    tags: ['vendor-intake', 'agent-decision', 'human-review', 'business-registry', 'compliance'],
    description: 'Combine PA registry identity, Census address evidence, OFAC name-screen candidates, and RDAP domain evidence into proceed or human_review with explicit triggers.',
    sampleQuery: { name: 'OpenAI', address: '600 North Second Street, Suite 401, Harrisburg, PA 17101', domain: 'openai.com' },
    sampleOutput: { decision: 'proceed', reviewTriggers: [], paid: true },
    parameters: [
      { name: 'name', required: true, schema: { type: 'string', minLength: 2, maxLength: 160 }, example: 'OpenAI' },
      { name: 'address', required: true, schema: { type: 'string', minLength: 6, maxLength: 300 }, example: '600 North Second Street, Suite 401, Harrisburg, PA 17101' },
      { name: 'domain', required: true, schema: { type: 'string', minLength: 3, maxLength: 253 }, example: 'openai.com' },
    ],
  },
  '/api/sec-filings': {
    price: '$0.005', amount: '5000',
    serviceName: 'SEC Recent Filings',
    tags: ['SEC', 'EDGAR', 'filings', 'finance', 'company-data'],
    description: 'Retrieve recent SEC EDGAR filing metadata by ticker or CIK, optionally filtered by form type.',
    sampleQuery: { ticker: 'AAPL', form: '10-K', limit: 5 },
    sampleOutput: { company: { name: 'Apple Inc.', cik: '0000320193' }, count: 1, filings: [], paid: true },
    parameters: [
      { name: 'ticker', required: false, schema: { type: 'string', minLength: 1 }, example: 'AAPL' },
      { name: 'cik', required: false, schema: { type: 'string', minLength: 1 }, example: '0000320193' },
      { name: 'form', required: false, schema: { type: 'string' }, example: '10-K' },
      { name: 'limit', required: false, schema: { type: 'integer', minimum: 1, maximum: 25, default: 10 }, example: 5 },
    ],
  },
  '/api/us-address-geocode': {
    price: '$0.005', amount: '5000',
    serviceName: 'US Census Geocoder',
    tags: ['geocoding', 'Census', 'address', 'geography', 'US'],
    description: 'Geocode a U.S. address to a Census match, coordinates, and Census geography identifiers.',
    sampleQuery: { address: '4600 Silver Hill Rd, Washington, DC 20233' },
    sampleOutput: { matched: true, coordinates: { longitude: -76.9, latitude: 38.8 }, paid: true },
    parameters: [
      { name: 'address', required: true, schema: { type: 'string', minLength: 6, maxLength: 300 }, example: '4600 Silver Hill Rd, Washington, DC 20233' },
    ],
  },
  '/api/ofac-sdn-screen': {
    price: '$0.005', amount: '5000',
    serviceName: 'OFAC Name Screen',
    tags: ['OFAC', 'sanctions', 'compliance', 'name-screening', 'risk'],
    description: 'Screen a name against current OFAC SDN primary names and aliases and return ranked candidates for human review. No-match is not clearance.',
    sampleQuery: { name: 'VLADIMIR PUTIN', limit: 5, minScore: 85 },
    sampleOutput: { query: 'VLADIMIR PUTIN', candidates: [], reviewRequired: true, paid: true },
    parameters: [
      { name: 'name', required: true, schema: { type: 'string', minLength: 2, maxLength: 160 }, example: 'VLADIMIR PUTIN' },
      { name: 'limit', required: false, schema: { type: 'integer', minimum: 1, maximum: 10, default: 5 }, example: 5 },
      { name: 'minScore', required: false, schema: { type: 'integer', minimum: 70, maximum: 100, default: 85 }, example: 85 },
    ],
  },
  '/api/domain-rdap': {
    price: '$0.005', amount: '5000',
    serviceName: 'Domain RDAP Lookup',
    tags: ['RDAP', 'domain', 'registration', 'DNS', 'internet'],
    description: 'Retrieve live authoritative domain-registration metadata using IANA RDAP bootstrap and the authoritative registry service.',
    sampleQuery: { domain: 'example.com' },
    sampleOutput: { domain: 'example.com', registered: true, registrar: {}, paid: true },
    parameters: [
      { name: 'domain', required: true, schema: { type: 'string', minLength: 3, maxLength: 253 }, example: 'example.com' },
    ],
  },
  '/api/treasury-average-rates': {
    price: '$0.005', amount: '5000',
    serviceName: 'Treasury Average Rates',
    tags: ['Treasury', 'interest-rates', 'government', 'macro', 'finance'],
    description: 'Get the latest monthly average interest rates on outstanding U.S. Treasury securities. These are not live market yields.',
    sampleQuery: { security: 'Total Marketable' },
    sampleOutput: { recordDate: '2026-08-31', rates: [], paid: true },
    parameters: [
      { name: 'security', required: false, schema: { type: 'string', maxLength: 100 }, example: 'Total Marketable' },
    ],
  },
};

function queryParams(meta) {
  return meta.parameters.map(p => ({
    name: p.name,
    in: 'query',
    required: p.required,
    schema: p.schema,
    example: p.example,
  }));
}

export function openApi(baseUrl) {
  const paths = {};
  for (const [path, meta] of Object.entries(ROUTES)) {
    paths[path] = {
      get: {
        operationId: path.replace(/^\/api\//, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase()),
        summary: meta.serviceName,
        description: meta.description,
        tags: meta.tags.slice(0, 3),
        security: [],
        'x-payment-info': {
          price: { mode: 'fixed', currency: 'USD', amount: meta.price.replace('$', '') + '000'.slice(meta.price.split('.')[1]?.length ?? 0) },
          protocols: [{ x402: {} }],
          network: NETWORK,
          payTo: PAY_TO,
        },
        parameters: queryParams(meta),
        responses: {
          '200': {
            description: 'Paid JSON result',
            content: { 'application/json': { schema: { type: 'object' } } },
          },
          '400': { description: 'Invalid input' },
          '402': { description: 'Payment Required' },
          '404': { description: 'Requested public record not found' },
          '502': { description: 'Authoritative upstream unavailable; payment is not settled' },
          '503': { description: 'Payment facilitator unavailable; no result is served' },
        },
      },
    };
  }
  return {
    openapi: '3.1.0',
    info: {
      title: 'Agent Data Tools x402',
      version: '1.0.0',
      description: 'Eight pay-per-call x402 endpoints backed by authoritative public data and a composed vendor-intake decision gate.',
      contact: { email: 'jayp19386@gmail.com' },
      'x-guidance': 'Use /api/vendor-intake-gate for a bounded proceed or human_review workflow decision. Use the lower-cost raw endpoints for source facts. Prices are $0.001-$0.020 USDC on Base. Unpaid calls return x402 v2 HTTP 402 challenges. A successful paid call settles only after its authoritative source work succeeds.',
    },
    servers: [{ url: baseUrl }],
    paths,
  };
}

export function manifest(baseUrl) {
  return {
    x402Version: 2,
    name: 'Agent Data Tools x402',
    description: 'Eight machine-payable public-data tools for autonomous agents.',
    network: NETWORK,
    asset: USDC,
    payTo: PAY_TO,
    resources: Object.entries(ROUTES).map(([path, meta]) => ({
      resource: baseUrl + path,
      method: 'GET',
      price: meta.price,
      description: meta.description,
      serviceName: meta.serviceName,
      tags: meta.tags,
      inputSchema: {
        type: 'object',
        properties: Object.fromEntries(meta.parameters.map(p => [p.name, p.schema])),
        required: meta.parameters.filter(p => p.required).map(p => p.name),
      },
    })),
  };
}

export function llmsText(baseUrl) {
  return '# Agent Data Tools x402\n\n' +
    'Eight paid endpoints backed by authoritative public sources.\n\n' +
    'Base URL: ' + baseUrl + '\n' +
    'Payment: x402 v2 exact, USDC on Base.\n' +
    'Prices: $0.001-$0.020 per successful call.\n' +
    'OpenAPI: ' + baseUrl + '/openapi.json\n' +
    'x402 manifest: ' + baseUrl + '/.well-known/x402\n' +
    'Skill guide: ' + baseUrl + '/skill.md\n\n' +
    Object.entries(ROUTES).map(([path, m]) => '- ' + path + ' — ' + m.price + ' — ' + m.description).join('\n') + '\n';
}

export function skillText(baseUrl) {
  return '# Agent Data Tools x402\n\n' +
    '## Use\nCall an endpoint without payment to receive its x402 v2 PAYMENT-REQUIRED challenge. Sign the Base USDC authorization, then retry with PAYMENT-SIGNATURE. Results are settled only after source work succeeds.\n\n' +
    '## Discovery\n- ' + baseUrl + '/openapi.json\n- ' + baseUrl + '/.well-known/x402\n- ' + baseUrl + '/llms.txt\n\n' +
    '## Safety / interpretation\nThe vendor-intake gate returns proceed or human_review as a workflow signal only. It is not legal, sanctions, fraud, credit, or compliance approval. OFAC output is candidate-name screening and does not implement the 50 Percent Rule. Treasury averages are not live market yields. PA registry records do not prove good standing or ownership.\n';
}

export function homepage(baseUrl) {
  const cards = Object.entries(ROUTES).map(([path, m]) =>
    '<li><strong>' + m.serviceName + '</strong> <code>' + path + '</code> — ' + m.price + '<br><span>' + m.description + '</span></li>'
  ).join('');
  return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Agent Data Tools x402</title><style>body{font:16px system-ui;max-width:900px;margin:48px auto;padding:0 20px;line-height:1.5;color:#111}code{background:#f3f3f3;padding:2px 5px;border-radius:5px}li{margin:18px 0}span{color:#555}</style></head><body><h1>Agent Data Tools x402</h1><p>Eight pay-per-call APIs for agents. USDC on Base via x402 v2.</p><p><a href="/openapi.json">OpenAPI</a> · <a href="/.well-known/x402">x402 manifest</a> · <a href="/skill.md">skill.md</a> · <a href="/llms.txt">llms.txt</a></p><ul>' + cards + '</ul><p>Health: <a href="/health">' + baseUrl + '/health</a></p></body></html>';
}
