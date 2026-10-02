const PA_SOURCE = 'https://data.pa.gov/resource/xvd7-5r2c.json';
const TREASURY_API = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates';
const IANA_RDAP = 'https://data.iana.org/rdap/dns.json';
const OFAC_BASE = 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports';
const USER_AGENT = 'agent-data-tools-x402/1.0 (contact: jayp19386@gmail.com)';

async function fetchTimeout(url, options = {}, ms = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function normalizeText(value) {
  return String(value ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function sortedTokens(value) {
  return normalizeText(value).split(' ').filter(Boolean).sort().join(' ');
}

function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const next = [i];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      next[j] = Math.min(next[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    prev = next;
  }
  return prev[b.length];
}

function tokenJaccard(a, b) {
  const aa = new Set(normalizeText(a).split(' ').filter(Boolean));
  const bb = new Set(normalizeText(b).split(' ').filter(Boolean));
  if (!aa.size || !bb.size) return 0;
  let shared = 0;
  for (const t of aa) if (bb.has(t)) shared += 1;
  return shared / new Set([...aa, ...bb]).size;
}

export function scoreName(query, candidate) {
  const q = normalizeText(query);
  const c = normalizeText(candidate);
  if (!q || !c) return 0;
  if (q === c) return 100;
  if (sortedTokens(q) === sortedTokens(c)) return 99;
  const contains = q.length >= 4 && c.length >= 4 && (q.includes(c) || c.includes(q)) ? 94 : 0;
  const edit = (1 - levenshtein(q, c) / Math.max(q.length, c.length, 1)) * 100;
  const qs = sortedTokens(q);
  const cs = sortedTokens(c);
  const editSorted = (1 - levenshtein(qs, cs) / Math.max(qs.length, cs.length, 1)) * 100;
  const tokens = tokenJaccard(q, c) * 100;
  return Math.max(contains, edit, editSorted, tokens);
}

function principalFromRow(row) {
  const first = row.first_name ?? row.party_first_name ?? row.firstname ?? null;
  const middle = row.middle_name ?? row.party_middle_name ?? row.middlename ?? null;
  const last = row.last_name ?? row.party_last_name ?? row.lastname ?? null;
  const role = row.party_type ?? row.partytype ?? null;
  if (!role && !first && !middle && !last) return null;
  return { role, firstName: first, middleName: middle, lastName: last };
}

function paEntityFromRows(rows) {
  const row = rows[0] ?? {};
  const principals = [];
  const seen = new Set();
  for (const r of rows) {
    const p = principalFromRow(r);
    if (!p) continue;
    const k = JSON.stringify(p);
    if (!seen.has(k)) { seen.add(k); principals.push(p); }
  }
  return {
    businessName: row.business_name ?? null,
    filingNumber: row.filing_number ?? null,
    registrationType: row.typeofbusinessregistration ?? null,
    creationDate: row.creationdate ? String(row.creationdate).slice(0, 10) : null,
    address1: row.address_line1 ?? null,
    address2: row.address_line2 ?? null,
    city: row.city ?? null,
    state: row.state ?? null,
    zip: row.zip ?? null,
    county: row.shortcountyname ?? null,
    countyCode: row.county_code ?? null,
    principals,
  };
}

export async function paSearch(query, limit = 10) {
  const q = String(query ?? '').trim();
  if (q.length < 2 || q.length > 120) throw new Error('invalid_pa_query');
  const capped = Math.max(1, Math.min(Number(limit) || 10, 25));
  const url = new URL(PA_SOURCE);
  url.searchParams.set('$limit', '250');
  url.searchParams.set('$q', q);
  const res = await fetchTimeout(url, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error('pa_source_' + res.status);
  const rows = await res.json();
  const groups = new Map();
  for (const row of rows) {
    const key = String(row.filing_number ?? row.business_name ?? Math.random());
    const list = groups.get(key) ?? [];
    list.push(row);
    groups.set(key, list);
  }
  const ranked = [...groups.values()].map(group => {
    const entity = paEntityFromRows(group);
    return { entity, score: Math.round(scoreName(q, entity.businessName ?? '')) };
  }).sort((a, b) => b.score - a.score || String(a.entity.businessName).localeCompare(String(b.entity.businessName)));
  return {
    query: q,
    count: Math.min(capped, ranked.length),
    results: ranked.slice(0, capped).map(x => ({ ...x.entity, matchScore: x.score })),
    source: 'Pennsylvania Department of State via data.pa.gov',
  };
}

export async function paBest(query) {
  const found = await paSearch(query, 25);
  const match = found.results[0] ?? null;
  return {
    query: found.query,
    found: Boolean(match),
    match,
    source: found.source,
  };
}

let secTickerCache = null;
async function secTickerMap() {
  if (secTickerCache) return secTickerCache;
  const res = await fetchTimeout('https://www.sec.gov/files/company_tickers.json', {
    headers: { 'User-Agent': USER_AGENT, accept: 'application/json' },
  });
  if (!res.ok) throw new Error('sec_tickers_' + res.status);
  secTickerCache = await res.json();
  return secTickerCache;
}

function normalizeCik(value) {
  const digits = String(value ?? '').replace(/\D/g, '');
  return digits && digits.length <= 10 ? digits.padStart(10, '0') : null;
}

export async function secFilings({ ticker, cik, form, limit = 10 }) {
  let resolved = cik ? normalizeCik(cik) : null;
  let companyTicker = ticker ? String(ticker).trim().toUpperCase() : null;
  let companyName = null;
  if (!resolved && companyTicker) {
    const map = await secTickerMap();
    for (const row of Object.values(map)) {
      if (String(row.ticker ?? '').toUpperCase() === companyTicker) {
        resolved = normalizeCik(row.cik_str);
        companyName = row.title ?? null;
        break;
      }
    }
  }
  if (!resolved) throw new Error('company_not_found');
  const url = 'https://data.sec.gov/submissions/CIK' + resolved + '.json';
  const res = await fetchTimeout(url, { headers: { 'User-Agent': USER_AGENT, accept: 'application/json' } });
  if (!res.ok) throw new Error('sec_submissions_' + res.status);
  const data = await res.json();
  companyName = companyName ?? data.name ?? null;
  companyTicker = companyTicker ?? (Array.isArray(data.tickers) ? data.tickers[0] : null);
  const recent = data.filings?.recent ?? {};
  const n = Array.isArray(recent.form) ? recent.form.length : 0;
  const wanted = form ? String(form).trim().toUpperCase() : null;
  const cap = Math.max(1, Math.min(Number(limit) || 10, 25));
  const filings = [];
  for (let i = 0; i < n && filings.length < cap; i += 1) {
    if (wanted && String(recent.form[i] ?? '').toUpperCase() !== wanted) continue;
    const accession = recent.accessionNumber[i];
    const primaryDocument = recent.primaryDocument[i];
    const accessionNoDash = String(accession ?? '').replace(/-/g, '');
    filings.push({
      form: recent.form[i] ?? null,
      filingDate: recent.filingDate[i] ?? null,
      reportDate: recent.reportDate[i] ?? null,
      accessionNumber: accession ?? null,
      primaryDocument: primaryDocument ?? null,
      filingUrl: accession && primaryDocument
        ? 'https://www.sec.gov/Archives/edgar/data/' + String(Number(resolved)) + '/' + accessionNoDash + '/' + primaryDocument
        : null,
    });
  }
  return {
    company: { name: companyName, cik: resolved, tickers: data.tickers ?? (companyTicker ? [companyTicker] : []) },
    count: filings.length,
    filings,
    source: 'U.S. Securities and Exchange Commission EDGAR',
  };
}

function firstGeo(geos, pattern) {
  for (const [key, value] of Object.entries(geos ?? {})) {
    if (pattern.test(key) && Array.isArray(value) && value.length) return value[0];
  }
  return null;
}

export async function censusGeocode(address) {
  const input = String(address ?? '').trim();
  if (input.length < 6 || input.length > 300) throw new Error('invalid_address');
  const url = new URL('https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress');
  url.searchParams.set('address', input);
  url.searchParams.set('benchmark', 'Public_AR_Current');
  url.searchParams.set('vintage', 'Current_Current');
  url.searchParams.set('format', 'json');
  const res = await fetchTimeout(url);
  if (!res.ok) throw new Error('census_' + res.status);
  const data = await res.json();
  const match = data.result?.addressMatches?.[0];
  if (!match) return { input, matched: false, source: 'U.S. Census Bureau Geocoding Services' };
  const geos = match.geographies ?? {};
  const state = firstGeo(geos, /^States$/i);
  const county = firstGeo(geos, /Counties/i);
  const tract = firstGeo(geos, /Census Tracts/i);
  const block = firstGeo(geos, /Census Blocks/i);
  const district = firstGeo(geos, /Congressional Districts/i);
  return {
    input,
    matched: true,
    matchedAddress: match.matchedAddress ?? null,
    coordinates: match.coordinates ?? null,
    geographies: {
      stateFips: state?.STATE ?? null,
      countyFips: county?.COUNTY ?? null,
      countyGeoid: county?.GEOID ?? null,
      tract: tract?.TRACT ?? null,
      tractGeoid: tract?.GEOID ?? null,
      block: block?.BLOCK ?? null,
      blockGeoid: block?.GEOID ?? null,
      congressionalDistrict: district?.CD ?? null,
    },
    source: 'U.S. Census Bureau Geocoding Services',
  };
}

let rdapBootstrapCache = null;
async function rdapBootstrap() {
  if (rdapBootstrapCache) return rdapBootstrapCache;
  const res = await fetchTimeout(IANA_RDAP, { headers: { accept: 'application/json', 'User-Agent': USER_AGENT } });
  if (!res.ok) throw new Error('iana_rdap_' + res.status);
  rdapBootstrapCache = await res.json();
  return rdapBootstrapCache;
}

function normalizeDomain(raw) {
  let value = String(raw ?? '').trim().toLowerCase().replace(/\.$/, '');
  if (value.length < 3 || value.length > 253 || !/^[a-z0-9.-]+$/.test(value)) throw new Error('invalid_domain');
  const labels = value.split('.');
  if (labels.length < 2 || labels.some(x => !x || x.length > 63 || x.startsWith('-') || x.endsWith('-'))) throw new Error('invalid_domain');
  return value;
}

function registrarFromEntities(entities) {
  for (const e of entities ?? []) {
    if (!(e.roles ?? []).includes('registrar')) continue;
    let name = null;
    const vcard = e.vcardArray?.[1] ?? [];
    for (const item of vcard) if (item?.[0] === 'fn') name = item?.[3] ?? null;
    return { name, handle: e.handle ?? null };
  }
  return null;
}

export async function domainRdap(rawDomain) {
  const domain = normalizeDomain(rawDomain);
  const tld = domain.split('.').pop();
  const boot = await rdapBootstrap();
  let base = null;
  for (const [tlds, urls] of boot.services ?? []) {
    if (tlds.includes(tld)) { base = urls?.[0] ?? null; break; }
  }
  if (!base) throw new Error('rdap_service_not_found');
  const endpoint = base.replace(/\/$/, '') + '/domain/' + encodeURIComponent(domain);
  const res = await fetchTimeout(endpoint, { headers: { accept: 'application/rdap+json, application/json', 'User-Agent': USER_AGENT } });
  if (res.status === 404) return { domain, registered: false, authoritativeRdapBase: base, source: 'IANA RDAP bootstrap + authoritative registry RDAP' };
  if (!res.ok) throw new Error('rdap_' + res.status);
  const data = await res.json();
  const events = {};
  for (const event of data.events ?? []) {
    if (event.eventAction && event.eventDate) events[event.eventAction] = event.eventDate;
  }
  return {
    domain,
    registered: true,
    handle: data.handle ?? null,
    status: data.status ?? [],
    registrar: registrarFromEntities(data.entities),
    events,
    nameservers: (data.nameservers ?? []).map(x => x.ldhName).filter(Boolean),
    secureDns: data.secureDNS ?? null,
    authoritativeRdapBase: base,
    source: 'IANA RDAP bootstrap + authoritative registry RDAP',
  };
}

export async function treasuryRates(security = '') {
  const wanted = String(security ?? '').trim();
  const url = new URL(TREASURY_API);
  url.searchParams.set('fields', 'record_date,security_type_desc,security_desc,avg_interest_rate_amt');
  url.searchParams.set('sort', '-record_date');
  url.searchParams.set('page[size]', '100');
  const res = await fetchTimeout(url, { headers: { accept: 'application/json', 'User-Agent': USER_AGENT } });
  if (!res.ok) throw new Error('treasury_' + res.status);
  const payload = await res.json();
  const rows = payload.data ?? [];
  if (!rows.length) throw new Error('treasury_no_data');
  const date = rows[0].record_date;
  const needle = wanted.toLowerCase();
  const filtered = rows.filter(row => row.record_date === date && (!needle || String(row.security_desc ?? '').toLowerCase().includes(needle)));
  return {
    recordDate: date,
    count: filtered.length,
    rates: filtered.map(row => ({
      securityDescription: row.security_desc ?? null,
      securityType: row.security_type_desc ?? null,
      averageInterestRatePercent: row.avg_interest_rate_amt == null || row.avg_interest_rate_amt === '' ? null : Number(row.avg_interest_rate_amt),
    })),
    source: 'U.S. Treasury Bureau of the Fiscal Service, Fiscal Data API',
  };
}

function parseCsv(text) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i += 1; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ''; }
    else if (ch === '\n') { row.push(field.replace(/\r$/, '')); if (row.some(v => v.length)) rows.push(row); row = []; field = ''; }
    else field += ch;
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/, '')); if (row.some(v => v.length)) rows.push(row); }
  return rows;
}

let ofacCache = null;
async function ofacEntries() {
  if (ofacCache && Date.now() - ofacCache.at < 10 * 60 * 1000) return ofacCache.entries;
  const fetchFile = async name => {
    const res = await fetchTimeout(OFAC_BASE + '/' + name, { headers: { accept: 'text/csv,*/*', 'User-Agent': USER_AGENT } }, 20000);
    if (!res.ok) throw new Error('ofac_' + name + '_' + res.status);
    return res.text();
  };
  const [sdn, alt] = await Promise.all([fetchFile('SDN.CSV'), fetchFile('ALT.CSV')]);
  const map = new Map();
  const clean = v => (!v || v === '-0-' ? null : v.trim() || null);
  for (const cols of parseCsv(sdn)) {
    const uid = (cols[0] ?? '').trim();
    const name = (cols[1] ?? '').trim();
    if (!uid || !name) continue;
    map.set(uid, { uid, name, type: clean(cols[2]), program: clean(cols[3]), title: clean(cols[4]), remarks: clean(cols[11]), aliases: [] });
  }
  for (const cols of parseCsv(alt)) {
    const entry = map.get((cols[0] ?? '').trim());
    const name = (cols[3] ?? '').trim();
    if (entry && name) entry.aliases.push({ type: clean(cols[2]), name, remarks: clean(cols[4]) });
  }
  const entries = [...map.values()];
  ofacCache = { at: Date.now(), entries };
  return entries;
}

export async function ofacScreen(name, limit = 5, minScore = 85) {
  const query = String(name ?? '').trim();
  if (query.length < 2 || query.length > 160) throw new Error('invalid_ofac_name');
  const cap = Math.max(1, Math.min(Number(limit) || 5, 10));
  const threshold = Math.max(70, Math.min(Number(minScore) || 85, 100));
  const entries = await ofacEntries();
  const candidates = [];
  for (const entry of entries) {
    let best = scoreName(query, entry.name);
    let matchedOn = 'primary', matchedName = entry.name;
    for (const alias of entry.aliases) {
      const score = scoreName(query, alias.name);
      if (score > best) { best = score; matchedOn = 'alias'; matchedName = alias.name; }
    }
    if (best >= threshold) candidates.push({
      uid: entry.uid, primaryName: entry.name, type: entry.type, program: entry.program,
      title: entry.title, remarks: entry.remarks, matchedOn, matchedName, score: Math.round(best),
    });
  }
  candidates.sort((a, b) => b.score - a.score || a.primaryName.localeCompare(b.primaryName));
  return {
    query,
    minScore: threshold,
    count: Math.min(candidates.length, cap),
    totalCandidatesAboveThreshold: candidates.length,
    candidates: candidates.slice(0, cap),
    source: 'U.S. Treasury OFAC Specially Designated Nationals (SDN) List',
    sourceFiles: ['SDN.CSV', 'ALT.CSV'],
    reviewRequired: true,
    limitations: [
      'Candidate-name screening only; a match is not a legal determination.',
      'A no-match is not sanctions clearance.',
      'This service does not implement OFAC 50 Percent Rule ownership analysis.',
    ],
  };
}

function normalizeAddress(value) {
  return normalizeText(value).replace(/\bSTREET\b/g, 'ST').replace(/\bROAD\b/g, 'RD').replace(/\bAVENUE\b/g, 'AVE').replace(/\bSUITE\b/g, 'STE');
}

export async function vendorIntakeGate({ name, address, domain }) {
  const [pa, census, ofac, rdap] = await Promise.all([
    paBest(name),
    censusGeocode(address),
    ofacScreen(name, 3, 90),
    domainRdap(domain),
  ]);
  const triggers = [];
  if (!pa.found) triggers.push('pa_registry_match_not_found');
  if (!census.matched) triggers.push('submitted_address_not_matched_by_census');
  if (ofac.candidates.length) triggers.push('ofac_name_candidate_requires_review');
  if (!rdap.registered) triggers.push('domain_not_registered');
  let addressConsistent = null;
  if (pa.match) {
    const registered = [pa.match.address1, pa.match.address2, pa.match.city, pa.match.state, pa.match.zip].filter(Boolean).join(' ');
    const a = normalizeAddress(address);
    const b = normalizeAddress(registered);
    addressConsistent = Boolean(a && b && (a.includes(b) || b.includes(a) || tokenJaccard(a, b) >= 0.65));
    if (!addressConsistent) triggers.push('submitted_address_differs_from_pa_registry');
  }
  return {
    decision: triggers.length ? 'human_review' : 'proceed',
    agentAction: triggers.length ? 'Pause automated intake and review the listed triggers/evidence.' : 'Continue the configured intake workflow; retain evidence for audit.',
    reviewTriggers: triggers,
    evidence: {
      paRegistry: pa,
      censusAddress: { ...census, consistentWithPaRegistry: addressConsistent },
      ofacNameScreen: ofac,
      rdapDomain: rdap,
    },
    limitations: [
      'Proceed only means the configured automated review triggers were not hit.',
      'This is not legal, sanctions, fraud, credit, or compliance approval.',
      'OFAC screening is candidate-name screening only and does not implement the 50 Percent Rule.',
    ],
  };
}
