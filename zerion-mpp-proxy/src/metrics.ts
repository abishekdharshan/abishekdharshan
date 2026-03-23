import type { Context } from 'hono'
import { receiptStoreSize } from './receipt-store.js'

/**
 * Lightweight Prometheus-compatible metrics.
 * No external dependencies — just counters and a text exporter.
 *
 * Plug into Prometheus/Grafana or Datadog agent via the /metrics endpoint.
 */

// ---------------------------------------------------------------------------
// Counters
// ---------------------------------------------------------------------------

const counters: Record<string, number> = {
  // Payment flow
  'mpp_challenges_total': 0,       // 402 challenges issued
  'mpp_payments_verified_total': 0, // successful payments
  'mpp_replays_blocked_total': 0,  // replay attempts rejected

  // Upstream
  'proxy_requests_total': 0,       // total requests forwarded upstream
  'proxy_errors_total': 0,         // upstream errors (5xx, network)
  'proxy_404_blocked_total': 0,    // requests blocked by URL validator

  // HTTP status buckets
  'http_responses_2xx_total': 0,
  'http_responses_4xx_total': 0,
  'http_responses_5xx_total': 0,
}

// Latency tracking (simple histogram buckets in ms)
const LATENCY_BUCKETS = [50, 100, 250, 500, 1000, 2500, 5000, 10000]
const latencyCounts: Record<string, number> = {}
let latencySum = 0
let latencyCount = 0

for (const bucket of LATENCY_BUCKETS) {
  latencyCounts[`le_${bucket}`] = 0
}
latencyCounts['le_Inf'] = 0

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function incCounter(name: keyof typeof counters, by = 1) {
  if (name in counters) {
    counters[name] += by
  }
}

export function recordLatency(ms: number) {
  latencySum += ms
  latencyCount += 1
  for (const bucket of LATENCY_BUCKETS) {
    if (ms <= bucket) {
      latencyCounts[`le_${bucket}`] += 1
    }
  }
  latencyCounts['le_Inf'] += 1
}

export function recordHttpStatus(status: number) {
  if (status >= 200 && status < 300) incCounter('http_responses_2xx_total')
  else if (status >= 400 && status < 500) incCounter('http_responses_4xx_total')
  else if (status >= 500) incCounter('http_responses_5xx_total')
}

// ---------------------------------------------------------------------------
// Prometheus text exposition format
// ---------------------------------------------------------------------------

function prometheusText(): string {
  const lines: string[] = []

  // Counters
  for (const [name, value] of Object.entries(counters)) {
    lines.push(`# TYPE ${name} counter`)
    lines.push(`${name} ${value}`)
  }

  // Upstream latency histogram
  lines.push('# TYPE proxy_upstream_latency_ms histogram')
  for (const bucket of LATENCY_BUCKETS) {
    lines.push(`proxy_upstream_latency_ms_bucket{le="${bucket}"} ${latencyCounts[`le_${bucket}`]}`)
  }
  lines.push(`proxy_upstream_latency_ms_bucket{le="+Inf"} ${latencyCounts['le_Inf']}`)
  lines.push(`proxy_upstream_latency_ms_sum ${latencySum}`)
  lines.push(`proxy_upstream_latency_ms_count ${latencyCount}`)

  // Gauges
  lines.push('# TYPE receipt_store_size gauge')
  lines.push(`receipt_store_size ${receiptStoreSize()}`)

  return lines.join('\n') + '\n'
}

// ---------------------------------------------------------------------------
// Hono handler
// ---------------------------------------------------------------------------

export function metricsEndpoint(c: Context) {
  return c.text(prometheusText(), 200, {
    'Content-Type': 'text/plain; version=0.0.4; charset=utf-8',
  })
}
