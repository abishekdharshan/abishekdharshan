import { config } from './config.js'

/**
 * Forward a verified request to the Zerion upstream API.
 * - Maps the incoming path to the upstream URL
 * - Adds Basic Auth with the Zerion API key
 * - Streams the upstream response back to the caller
 */
export async function forwardToZerion(request: Request): Promise<Response> {
  const url = new URL(request.url)

  // Build upstream URL preserving path + query string
  const upstream = new URL(url.pathname + url.search, config.zerionApiBaseUrl)

  // Build headers – forward most originals, override auth
  const headers = new Headers(request.headers)

  // Remove MPP / payment headers before forwarding
  headers.delete('authorization')
  headers.delete('x-payment')

  // Zerion API uses Basic Auth: key as username, empty password
  const basicAuth = Buffer.from(`${config.zerionApiKey}:`).toString('base64')
  headers.set('Authorization', `Basic ${basicAuth}`)

  // Forward the request
  const upstreamResponse = await fetch(upstream.toString(), {
    method: request.method,
    headers,
    body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
    // @ts-expect-error – duplex needed for streaming body in Node 18+
    duplex: request.body ? 'half' : undefined,
  })

  // Return upstream response with original status + headers
  const responseHeaders = new Headers(upstreamResponse.headers)
  // Remove hop-by-hop headers
  responseHeaders.delete('transfer-encoding')

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  })
}
