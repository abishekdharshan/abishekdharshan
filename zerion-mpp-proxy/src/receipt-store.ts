/**
 * In-memory store for tracking used payment credentials to prevent replay attacks.
 *
 * Production note: replace with Redis (SET key EX ttl NX) for multi-instance deployments.
 * This in-memory implementation is fine for a single-instance proxy.
 */

const DEFAULT_TTL_MS = 60 * 60 * 1000 // 1 hour
const CLEANUP_INTERVAL_MS = 5 * 60 * 1000 // sweep every 5 min
const MAX_ENTRIES = 100_000 // hard cap to prevent memory leaks

interface Entry {
  expiresAt: number
}

const seen = new Map<string, Entry>()
let cleanupTimer: ReturnType<typeof setInterval> | null = null

/**
 * Check if a credential has already been used. If not, mark it as used.
 * Returns `true` if this is a replay (already seen), `false` if fresh.
 */
export function isReplay(credentialId: string, ttlMs = DEFAULT_TTL_MS): boolean {
  const now = Date.now()

  // Already seen and not expired → replay
  const existing = seen.get(credentialId)
  if (existing && existing.expiresAt > now) {
    return true
  }

  // Hard cap — reject if store is full (back-pressure, prevents OOM)
  if (seen.size >= MAX_ENTRIES) {
    evictExpired(now)
    if (seen.size >= MAX_ENTRIES) {
      // Still full after eviction — treat as replay to be safe
      return true
    }
  }

  seen.set(credentialId, { expiresAt: now + ttlMs })
  return false
}

/** Remove all expired entries. */
function evictExpired(now = Date.now()) {
  for (const [key, entry] of seen) {
    if (entry.expiresAt <= now) {
      seen.delete(key)
    }
  }
}

/** Start the periodic cleanup timer (called once at startup). */
export function startCleanup() {
  if (cleanupTimer) return
  cleanupTimer = setInterval(() => evictExpired(), CLEANUP_INTERVAL_MS)
  // Allow Node to exit even if the timer is still running
  cleanupTimer.unref()
}

/** Expose store size for metrics. */
export function receiptStoreSize(): number {
  return seen.size
}
