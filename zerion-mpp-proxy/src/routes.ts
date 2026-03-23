import { Hono } from 'hono'
import { Mppx, tempo } from 'mppx/hono'
import { config } from './config.js'
import { forwardToZerion } from './proxy.js'
import { healthCheck } from './health.js'
import { isValidZerionPath } from './url-validator.js'
import { isReplay, startCleanup } from './receipt-store.js'
import { incCounter, recordLatency, recordHttpStatus, metricsEndpoint } from './metrics.js'
import { logPayment, logError, logInfo } from './logger.js'

// ---------------------------------------------------------------------------
// Boot: start the receipt-store cleanup timer
// ---------------------------------------------------------------------------
startCleanup()

// ---------------------------------------------------------------------------
// Mppx instance – Hono-native middleware that auto-handles 402/receipt flow
// ---------------------------------------------------------------------------
const mppx = Mppx.create({
  methods: [
    tempo.charge({
      currency: config.mppCurrencyAddress,
      recipient: config.mppRecipientAddress,
      ...(config.mppTestnet ? { testnet: true } : {}),
    }),
  ],
  secretKey: config.mppSecretKey,
})

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
const app = new Hono()

// Health -------------------------------------------------------------------
app.get('/health', healthCheck)
app.get('/healthz', healthCheck)

// Metrics (Prometheus) -----------------------------------------------------
app.get('/metrics', metricsEndpoint)

// MPP-gated Zerion API routes ----------------------------------------------
app.all('/v1/*', async (c, next) => {
  // ── Step 1: URL validation (before payment!) ───────────────────────────
  // Reject requests to non-existent resources so agents don't lose money.
  if (!isValidZerionPath(c.req.path)) {
    incCounter('proxy_404_blocked_total')
    logInfo('Blocked request to unknown path (pre-payment)', { path: c.req.path })
    return c.json(
      {
        error: 'Unknown endpoint',
        detail: `${c.req.path} does not match any known Zerion API route. No payment was charged.`,
        hint: 'GET / for a list of supported endpoints.',
      },
      404,
    )
  }

  await next()
})

// MPP charge middleware
app.all(
  '/v1/*',
  mppx.charge({ amount: config.mppChargeAmount }),
  async (c) => {
    const start = Date.now()
    const endpoint = `${c.req.method} ${c.req.path}`

    // ── Step 2: Replay protection ──────────────────────────────────────
    // Extract the payment credential from the Authorization header.
    // mppx has already verified the signature at this point — we just
    // need to ensure the same credential isn't used a second time.
    const credential = c.req.header('authorization') ?? ''
    if (credential && isReplay(credential)) {
      incCounter('mpp_replays_blocked_total')
      logError('Replay attack blocked', { endpoint })
      return c.json(
        { error: 'Payment credential already used', detail: 'Each payment credential can only be used once.' },
        409,
      )
    }

    incCounter('mpp_payments_verified_total')
    incCounter('proxy_requests_total')

    // ── Step 3: Proxy to Zerion ────────────────────────────────────────
    try {
      const upstreamResponse = await forwardToZerion(c.req.raw)
      const durationMs = Date.now() - start

      recordLatency(durationMs)
      recordHttpStatus(upstreamResponse.status)

      logPayment({
        endpoint,
        amount: config.mppChargeAmount,
        status: 'charged',
        durationMs,
      })

      return upstreamResponse
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      incCounter('proxy_errors_total')
      logError('Proxy error', { endpoint, error: message })
      return c.json({ error: 'Internal proxy error', detail: message }, 502)
    }
  },
)

// Root – informational ------------------------------------------------------
app.get('/', (c) =>
  c.json({
    name: 'Zerion MPP Proxy',
    description: 'Pay-per-request access to the Zerion API via Machine Payments Protocol',
    docs: 'https://developers.zerion.io',
    mpp: 'https://mpp.dev',
    health: '/health',
    metrics: '/metrics',
    pricing: `$${config.mppChargeAmount} per request (pathUSD on Tempo${config.mppTestnet ? ' testnet' : ''})`,
    endpoints: [
      'GET /v1/fungibles/',
      'GET /v1/wallets/:address/portfolio',
      'GET /v1/wallets/:address/positions/',
      'GET /v1/wallets/:address/transactions/',
      'GET /v1/wallets/:address/pnl',
      'GET /v1/wallets/:address/nft-collections/',
      'GET /v1/wallets/:address/nft-portfolio',
      'GET /v1/wallets/:address/nft-positions/',
      'GET /v1/wallets/:address/charts/:period',
      'GET /v1/chains/',
      'GET /v1/dapps/',
      'GET /v1/nfts/',
    ],
  }),
)

export { app }
