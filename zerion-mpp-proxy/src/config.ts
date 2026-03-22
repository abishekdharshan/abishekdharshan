import crypto from 'node:crypto'

export const config = {
  /** Zerion upstream */
  zerionApiKey: env('ZERION_API_KEY', 'zk_dev_8ef01ce562c24dcbbaf3b46325712b85'),
  zerionApiBaseUrl: env('ZERION_API_BASE_URL', 'https://api.zerion.io'),

  /** MPP / Tempo */
  mppRecipientAddress: env('MPP_RECIPIENT_ADDRESS', '0x0000000000000000000000000000000000000000') as `0x${string}`,
  mppCurrencyAddress: env('MPP_CURRENCY_ADDRESS', '0x20c0000000000000000000000000000000000000') as `0x${string}`,
  mppChargeAmount: env('MPP_CHARGE_AMOUNT', '0.01'),
  mppTestnet: env('MPP_TESTNET', 'true') === 'true',
  mppSecretKey: env('MPP_SECRET_KEY', '') || crypto.randomBytes(32).toString('base64'),

  /** Server */
  port: Number(env('PORT', '3402')),
} as const

function env(key: string, fallback: string): string {
  return process.env[key] ?? fallback
}
