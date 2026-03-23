# Zerion MPP Proxy

Pay-per-request access to the [Zerion API](https://developers.zerion.io) via the [Machine Payments Protocol (MPP)](https://mpp.dev).

AI agents can query any Zerion endpoint by paying **$0.01 per request** in pathUSD on the Tempo blockchain — no API key required.

## How it works

```
Agent ──► MPP Proxy (this service) ──► Zerion public-api (Go)
          │                                     │
          │  1. Invalid path → 404 (no charge)  │
          │  2. No payment → 402 challenge      │
          │  3. Valid credential → proxy + receipt│
          │  4. Replayed credential → 409        │
          └─────────────────────────────────────┘
```

1. Agent calls any `/v1/*` endpoint → proxy first validates the path is a known Zerion route (unknown paths return **404 with no charge**)
2. Valid path, no payment → proxy returns **HTTP 402** with MPP challenge
3. Agent signs payment credential (handled automatically by `mppx` CLI or SDK)
4. Agent retries with signed credential → proxy verifies payment, checks for replay, forwards to Zerion API, returns data + receipt
5. If the same credential is resubmitted → proxy returns **HTTP 409** (replay blocked)

## Security

### Replay protection

Every verified payment credential is tracked in an in-memory store (TTL: 1 hour, max 100k entries). Resubmitting a used credential returns `409 Conflict`. For multi-instance deployments, swap the in-memory store for Redis (`SET key EX ttl NX`).

### URL validation (pre-payment)

Requests to unknown paths (e.g., `/v1/nonexistent`) are rejected with `404` **before** the payment flow starts, so agents never pay for resources that don't exist.

## Observability

### Prometheus metrics

`GET /metrics` exposes counters and histograms in Prometheus text format:

| Metric | Type | Description |
|--------|------|-------------|
| `mpp_challenges_total` | counter | 402 challenges issued |
| `mpp_payments_verified_total` | counter | Successful payments |
| `mpp_replays_blocked_total` | counter | Replay attempts rejected |
| `proxy_requests_total` | counter | Requests forwarded upstream |
| `proxy_errors_total` | counter | Upstream errors |
| `proxy_404_blocked_total` | counter | Requests blocked by URL validator |
| `http_responses_2xx_total` | counter | 2xx responses |
| `http_responses_4xx_total` | counter | 4xx responses |
| `http_responses_5xx_total` | counter | 5xx responses |
| `proxy_upstream_latency_ms` | histogram | Upstream response latency |
| `receipt_store_size` | gauge | Current receipt store entries |

### Structured logging

All logs are JSON-structured for ingestion by Datadog, Loki, CloudWatch, etc.

### Suggested alerts

- `rate(mpp_replays_blocked_total[5m]) > 0` — someone is attempting replay attacks
- `rate(proxy_errors_total[5m]) / rate(proxy_requests_total[5m]) > 0.05` — upstream error rate > 5%
- `proxy_upstream_latency_ms_bucket{le="5000"} / proxy_upstream_latency_ms_count < 0.95` — p95 latency > 5s

## Quick start

```bash
# Install dependencies
npm install

# Copy env and configure your recipient wallet
cp .env.example .env

# Run in dev mode
npm run dev

# Test (in another terminal)
npx mppx account create
npx mppx http://localhost:3402/v1/wallets/0xd8da6bf26964af9d7eed9e03e53415d37aa96045/portfolio
```

## Endpoints

All standard Zerion API v1 endpoints are supported:

| Endpoint | Description |
|----------|-------------|
| `GET /v1/fungibles/` | Token list |
| `GET /v1/wallets/:address/portfolio` | Wallet portfolio |
| `GET /v1/wallets/:address/positions/` | Token positions |
| `GET /v1/wallets/:address/transactions/` | Transaction history |
| `GET /v1/wallets/:address/pnl` | Profit & loss |
| `GET /v1/wallets/:address/nft-collections/` | NFT collections |
| `GET /v1/wallets/:address/nft-portfolio` | NFT portfolio |
| `GET /v1/wallets/:address/nft-positions/` | NFT positions |
| `GET /v1/wallets/:address/charts/:period` | Portfolio charts |
| `GET /v1/chains/` | Supported chains |
| `GET /v1/dapps/` | DApp catalog |
| `GET /v1/nfts/` | NFT catalog |
| `GET /health` | Health check |
| `GET /metrics` | Prometheus metrics |

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ZERION_API_KEY` | Zerion API key (Basic Auth) | `zk_dev_...` |
| `ZERION_API_BASE_URL` | Zerion upstream URL | `https://api.zerion.io` |
| `MPP_RECIPIENT_ADDRESS` | Wallet receiving payments on Tempo | — |
| `MPP_CURRENCY_ADDRESS` | pathUSD token address | testnet default |
| `MPP_CHARGE_AMOUNT` | USD charge per request | `0.01` |
| `MPP_TESTNET` | Use Tempo testnet | `true` |
| `MPP_SECRET_KEY` | Base64 secret for signing receipts | auto-generated |
| `PORT` | Server port | `3402` |

## Docker

```bash
docker compose up --build
```

## Mainnet deployment

1. Set `MPP_TESTNET=false`
2. Set `MPP_CURRENCY_ADDRESS=0x20c000000000000000000000b9537d11c60e8b50` (pathUSD mainnet)
3. Set `MPP_RECIPIENT_ADDRESS` to your production Tempo wallet
4. Set a stable `MPP_SECRET_KEY` (receipts must verify across restarts)

## Architecture

This is a **sidecar proxy** pattern. The Go `public-api` service is untouched — this TypeScript service sits in front of it and handles MPP payment verification using the official [`mppx`](https://www.npmjs.com/package/mppx) SDK by Wevm/Tempo.

### Language choice

The proxy is written in TypeScript (Node.js) because the `mppx` SDK is JS-native and was the fastest path to a working prototype. Ivan's recommendation to evaluate Python (or Go) for long-term maintainability is noted — the team has deeper expertise in those languages. If this moves to production, consider:

- **Python**: Tempo ships `pympp`; aligns with existing backend services
- **Go**: Native integration into `public-api` as middleware (like the existing x402 impl)
- **Keep JS**: If the proxy stays as a standalone sidecar, the JS implementation is fine

### Production checklist (from Ivan's review)

- [x] Replay protection — in-memory credential tracking (swap to Redis for multi-instance)
- [x] URL validation — pre-payment path validation prevents paying for 404s
- [x] Observability — Prometheus `/metrics` endpoint, structured JSON logging, suggested alert rules
- [ ] Set real `MPP_RECIPIENT_ADDRESS` (register Tempo wallet)
- [ ] Generate and persist `MPP_SECRET_KEY`
- [ ] Switch to production Zerion API key
- [ ] Deploy with proper infra (Kubernetes, Fly.io, etc.)
