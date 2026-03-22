/**
 * Structured JSON logger for payment events and general server logs.
 */
export function logPayment(event: {
  endpoint: string
  amount: string
  sender?: string
  txHash?: string
  status: 'charged' | 'challenge' | 'error'
  durationMs?: number
}) {
  const entry = {
    timestamp: new Date().toISOString(),
    type: 'payment',
    ...event,
  }
  console.log(JSON.stringify(entry))
}

export function logInfo(message: string, extra?: Record<string, unknown>) {
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), level: 'info', message, ...extra }))
}

export function logError(message: string, extra?: Record<string, unknown>) {
  console.error(JSON.stringify({ timestamp: new Date().toISOString(), level: 'error', message, ...extra }))
}
