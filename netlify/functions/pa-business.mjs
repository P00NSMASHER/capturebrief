const UPSTREAM = "https://pa-entity-x402.floot.app/_api/pa-business";

const FORWARD_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "payment-signature",
  "x-payment",
  "user-agent",
];

const DROP_RESPONSE_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export default async function paBusinessProxy(request) {
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, HEAD, OPTIONS",
        "access-control-allow-headers":
          "payment-signature, x-payment, content-type, accept",
        "cache-control": "no-store",
      },
    });
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response(
      JSON.stringify({ error: "method_not_allowed", allowed: ["GET", "HEAD"] }),
      {
        status: 405,
        headers: {
          "content-type": "application/json; charset=utf-8",
          allow: "GET, HEAD, OPTIONS",
        },
      }
    );
  }

  const incomingUrl = new URL(request.url);
  const upstreamUrl = new URL(UPSTREAM);
  upstreamUrl.search = incomingUrl.search;

  const upstreamHeaders = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) upstreamHeaders.set(name, value);
  }

  // Exactly one upstream request. The Floot seller remains authoritative for
  // x402 verification, Pennsylvania lookup execution, and settlement ordering.
  const upstreamResponse = await fetch(upstreamUrl, {
    method: request.method,
    headers: upstreamHeaders,
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  for (const [name, value] of upstreamResponse.headers) {
    if (!DROP_RESPONSE_HEADERS.has(name.toLowerCase())) {
      responseHeaders.set(name, value);
    }
  }
  responseHeaders.set("access-control-allow-origin", "*");
  responseHeaders.set("vary", "Origin");

  return new Response(
    request.method === "HEAD" ? null : upstreamResponse.body,
    {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    }
  );
}
