import { serve } from '@hono/node-server'
import { app } from './routes.js'
import { config } from './config.js'
import { logInfo } from './logger.js'

serve({ fetch: app.fetch, port: config.port }, (info) => {
  logInfo('Zerion MPP Proxy started', {
    port: info.port,
    testnet: config.mppTestnet,
    upstream: config.zerionApiBaseUrl,
    recipient: config.mppRecipientAddress,
    chargeAmount: config.mppChargeAmount,
  })
  console.log(`\n  🟢 Zerion MPP Proxy running at http://localhost:${info.port}`)
  console.log(`     Testnet: ${config.mppTestnet}`)
  console.log(`     Upstream: ${config.zerionApiBaseUrl}`)
  console.log(`     Charge: $${config.mppChargeAmount}/request\n`)
  console.log(`  Test with:`)
  console.log(`     npx mppx account create`)
  console.log(`     npx mppx http://localhost:${info.port}/v1/wallets/0xd8da6bf26964af9d7eed9e03e53415d37aa96045/portfolio\n`)
})
