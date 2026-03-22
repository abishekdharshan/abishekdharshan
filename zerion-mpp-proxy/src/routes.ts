import { Hono } from 'hono'
import { Mppx, tempo } from 'mppx/server'
import { config } from './config.js'
import { forwardToZerion } from './proxy.js'
import { healthCheck } from './health.js'
import { logPayment, logError } from './logger.js'

// ---------------------------------------------------------------------------
// Mppx instance – handles 402 challenge / credential / receipt flow
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

// MPP-gated Zerion API routes ----------------------------------------------
// Catch-all: any /v1/* request goes through the MPP charge middleware and
// then gets proxied to the Zerion upstream.
app.all('/v1/*', async (c) => {
  const start = Date.now()
  const endpoint = `${c.req.method} ${c.req.path}`

  try {
    const response = await mppx.charge({
      amount: config.mppChargeAmount,
    })(c.req.raw)

    // If payment is required, return the 402 challenge
    if (response.status === 402) {
      logPayment({ endpoint, amount: config.mppChargeAmount, status: 'challenge' })
      return new Response(response.challenge.body, {
        status: response.challenge.status,
        headers: response.challenge.headers,
      })
    }

    // Payment verified – proxy to Zerion
    const upstreamResponse = await forwardToZerion(c.req.raw)
    const durationMs = Date.now() - start

    logPayment({
      endpoint,
      amount: config.mppChargeAmount,
      status: 'charged',
      durationMs,
    })

    // Attach MPP receipt to the upstream response
    return response.withReceipt(upstreamResponse)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    logError('Payment or proxy error', { endpoint, error: message })
    return c.json({ error: 'Internal proxy error', detail: message }, 502)
  }
})

// Root – informational ------------------------------------------------------
app.get('/', (c) =>
  c.json({
    name: 'Zerion MPP Proxy',
    description: 'Pay-per-request access to the Zerion API via Machine Payments Protocol',
    docs: 'https://developers.zerion.io',
    mpp: 'https://mpp.dev',
    health: '/health',
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
