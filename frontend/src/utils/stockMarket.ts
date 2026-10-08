import { api } from '@/services/api'

export type StockMarket = 'BIST' | 'NASDAQ'

// Module-level cache — symbol → market. Populated on first call, reused forever.
// Markets don't change, so no TTL is needed.
const _cache = new Map<string, StockMarket>()

/**
 * Resolve which exchange market a stock symbol belongs to.
 *
 * - Symbols ending in `.IS` are always BIST.
 * - Other symbols are looked up against the backend's bist_stocks list.
 * - Results are cached in memory for the lifetime of the page.
 */
export async function resolveStockMarket(symbol: string): Promise<StockMarket> {
  const key = symbol.toUpperCase()

  // Fast path: .IS suffix is unambiguously BIST
  if (key.endsWith('.IS')) return 'BIST'

  const cached = _cache.get(key)
  if (cached !== undefined) return cached

  try {
    const resp = await api.get<{ status: string; data: { market: StockMarket } }>(
      `/symbols/resolve-market/${encodeURIComponent(key)}`
    )
    const market = resp.data.market
    _cache.set(key, market)
    return market
  } catch {
    // On any network failure, fall back to NASDAQ so the chart still renders.
    _cache.set(key, 'NASDAQ')
    return 'NASDAQ'
  }
}
