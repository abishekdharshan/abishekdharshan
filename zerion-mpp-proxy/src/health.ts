import type { Context } from 'hono'
import { config } from './config.js'

export function healthCheck(c: Context) {
  return c.json({
    status: 'ok',
    service: 'zerion-mpp-proxy',
    testnet: config.mppTestnet,
    upstream: config.zerionApiBaseUrl,
    timestamp: new Date().toISOString(),
  })
}
