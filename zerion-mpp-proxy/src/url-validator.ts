/**
 * Validates that a request path maps to a known Zerion API resource pattern
 * BEFORE the payment flow starts, so agents don't pay for 404s.
 */

/** Allowed path patterns (order doesn't matter). */
const VALID_PATTERNS: RegExp[] = [
  // Fungibles
  /^\/v1\/fungibles\/?$/,
  /^\/v1\/fungibles\/[^/]+\/?$/,

  // Wallet endpoints
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/portfolio\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/positions\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/transactions\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/pnl\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/nft-collections\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/nft-portfolio\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/nft-positions\/?$/,
  /^\/v1\/wallets\/0x[0-9a-fA-F]{40}\/charts\/[^/]+\/?$/,

  // Chains, DApps, NFTs
  /^\/v1\/chains\/?$/,
  /^\/v1\/dapps\/?$/,
  /^\/v1\/nfts\/?$/,
  /^\/v1\/nfts\/[^/]+\/?$/,
]

/**
 * Returns true if the path (without query string) matches a known Zerion
 * endpoint pattern. This is intentionally conservative — unknown paths are
 * rejected early with 404 so the agent keeps their money.
 */
export function isValidZerionPath(path: string): boolean {
  // Strip query string if present
  const cleanPath = path.split('?')[0]
  return VALID_PATTERNS.some((re) => re.test(cleanPath))
}
