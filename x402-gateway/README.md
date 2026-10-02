# Agent Data Tools x402 Gateway

Self-contained Node 20 service for eight x402 v2 pay-per-call routes backed by authoritative public data.

## Run

```bash
cd x402-gateway
npm run check
node smoke.mjs
npm start
```

Runtime expects a host-provided `PORT`. No API keys or application secrets are required. Payment verification and settlement use the public PayAI facilitator, and payment results settle directly to the configured seller wallet.

The gateway verifies payment before source work and settles only after a successful source result. Upstream public-source failures return without settlement.
