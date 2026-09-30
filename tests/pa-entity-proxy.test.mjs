import assert from "node:assert/strict";
import proxy from "../netlify/functions/pa-business.mjs";

const originalFetch = globalThis.fetch;

try {
  const seen = [];
  globalThis.fetch = async (url, init = {}) => {
    seen.push({ url: String(url), init });
    return new Response(
      JSON.stringify({
        error: "payment_required",
        x402Version: 2,
        resource: {
          url: "https://pa-entity-x402.floot.app/_api/pa-business",
          mimeType: "application/json",
        },
        accepts: [{
          scheme: "exact",
          network: "eip155:8453",
          amount: "5000",
          asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
          payTo: "0x708f7b52b56eafd7fc1de65fc7752ed732914021",
          maxTimeoutSeconds: 60,
          extra: { name: "USD Coin", version: "2" },
        }],
      }),
      {
        status: 402,
        headers: {
          "content-type": "application/json",
          "payment-required": "opaque-upstream-challenge",
          "x402-price": "$0.005",
          "x402-network": "eip155:8453",
          "x402-pay-to": "0x708f7b52b56eafd7fc1de65fc7752ed732914021",
        },
      }
    );
  };

  const request = new Request(
    "https://capturebrief.netlify.app/api/pa-business?q=OpenAI&limit=1",
    {
      headers: {
        "user-agent": "Agent402/1.0",
        "payment-signature": "signed-payment",
        "x-unrelated-secret": "must-not-forward",
      },
    }
  );

  const response = await proxy(request);
  assert.equal(response.status, 402);
  assert.equal(seen.length, 1, "proxy must make exactly one upstream request");
  assert.equal(
    seen[0].url,
    "https://pa-entity-x402.floot.app/_api/pa-business?q=OpenAI&limit=1"
  );
  assert.equal(seen[0].init.method, "GET");

  const sentHeaders = new Headers(seen[0].init.headers);
  assert.equal(sentHeaders.get("user-agent"), "Agent402/1.0");
  assert.equal(sentHeaders.get("payment-signature"), "signed-payment");
  assert.equal(sentHeaders.get("x-unrelated-secret"), null);

  assert.equal(response.headers.get("payment-required"), "opaque-upstream-challenge");
  assert.equal(response.headers.get("x402-price"), "$0.005");
  assert.equal(response.headers.get("x402-network"), "eip155:8453");
  assert.equal(
    response.headers.get("x402-pay-to"),
    "0x708f7b52b56eafd7fc1de65fc7752ed732914021"
  );

  const body = await response.json();
  assert.equal(body.x402Version, 2);
  assert.equal(body.accepts[0].amount, "5000");
  assert.equal(
    body.accepts[0].payTo,
    "0x708f7b52b56eafd7fc1de65fc7752ed732914021"
  );

  console.log("PA x402 transparent proxy regression: PASS");
} finally {
  globalThis.fetch = originalFetch;
}
