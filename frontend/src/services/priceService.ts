import { toast } from 'sonner'
import { api, getAccessToken } from '@/services/api'

export interface PriceRefreshResult {
  asset_id: string
  symbol: string | null
  status: 'updated' | 'failed'
  price?: number
  currency?: string
  error?: string
}

interface PriceRefreshResponse {
  status: string
  data: PriceRefreshResult[]
}

export const PRICES_REFRESHED_EVENT = 'portfoliomind:prices-refreshed'

export function notifyPricesRefreshed(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(PRICES_REFRESHED_EVENT))
  }
}

export function onPricesRefreshed(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const handler = () => callback()
  window.addEventListener(PRICES_REFRESHED_EVENT, handler)
  return () => window.removeEventListener(PRICES_REFRESHED_EVENT, handler)
}

export const priceService = {
  refreshPrices: () =>
    api
      .post<PriceRefreshResponse>('/prices/refresh', {})
      .then((r) => (r as PriceRefreshResponse).data),
}

let _activeRefreshPromise: Promise<PriceRefreshResult[] | null> | null = null
let _lastRefreshTime = 0
const DEDUPE_WINDOW_MS = 3000

export function resetPriceRefreshState(): void {
  _activeRefreshPromise = null
  _lastRefreshTime = 0
}

/**
 * Triggers background price refresh after successful credential login.
 * Non-blocking, deduplicated, and resilient to provider or network failures.
 * Never redirects to login or clears auth on failure.
 */
export function triggerLoginPriceRefresh(): Promise<PriceRefreshResult[] | null> {
  const token = getAccessToken()
  if (!token) {
    return Promise.resolve(null)
  }

  const now = Date.now()
  if (_activeRefreshPromise) {
    return _activeRefreshPromise
  }
  if (now - _lastRefreshTime < DEDUPE_WINDOW_MS) {
    return Promise.resolve(null)
  }

  _lastRefreshTime = now
  const promise = (async () => {
    try {
      const results = await priceService.refreshPrices()
      const updated = Array.isArray(results)
        ? results.filter((r) => r.status === 'updated').length
        : 0
      const failed = Array.isArray(results)
        ? results.filter((r) => r.status === 'failed').length
        : 0

      if (failed > 0 && updated === 0) {
        toast.warning('Could not update live asset prices')
        console.warn('Asset price refresh provider failure:', results)
      } else if (updated > 0) {
        toast.success(`Prices refreshed — ${updated} updated`)
      }

      notifyPricesRefreshed()
      return results
    } catch (err) {
      console.warn('Background price refresh failed:', err)
      toast.warning('Could not refresh asset prices')
      return null
    } finally {
      _activeRefreshPromise = null
    }
  })()

  _activeRefreshPromise = promise
  return promise
}

