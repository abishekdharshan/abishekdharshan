# Zerion MPP Proxy

Pay-per-request access to the [Zerion API](https://developers.zerion.io) via the [Machine Payments Protocol (MPP)](https://mpp.dev).

AI agents can query any Zerion endpoint by paying **$0.01 per request** in pathUSD on the Tempo blockchain — no API key required.

## How it works

```
Agent ──► MPP Proxy (this service) ──► Zerion public-api (Go)
          │                                     │
          │  1. No payment → 402 challenge      │
          │  2. Valid credential → proxy + receipt│
          └─────────────────────────────────────┘
```

1. Agent calls any `/v1/*` endpoint without payment → proxy returns **HTTP 402** with MPP challenge
2. Agent signs payment credential (handled automatically by `mppx` CLI or SDK)
3. Agent retries with signed credential in `Authorization` header
4. Proxy verifies payment via `mppx`, forwards to Zerion API, returns data + receipt

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

When Ivan returns from vacation, the MPP logic can optionally be moved into the Go codebase as native middleware (similar to the existing x402 implementation).
