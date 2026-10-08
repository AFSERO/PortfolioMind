/**
 * useForexRates — fetches all standard forex rates from the backend's cached
 * endpoint (``GET /api/prices/forex-rates``) and exposes a ``convertCurrency``
 * helper for frontend P/L and display calculations.
 *
 * The backend serves these from a three-layer cache (in-memory → DB → live API)
 * so a single call is cheap and rarely hits an external service.
 *
 * Module-level cache here adds a 5-minute browser-side TTL so repeated
 * component mounts within the same page session skip the network entirely.
 */

import { useState, useEffect } from 'react'
import { api } from '@/services/api'

export type ForexRates = Record<string, number>

// Module-level browser cache
let _cachedRates: ForexRates | null = null
let _cacheExpiry = 0
const CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes

interface ForexRatesResponse {
  status: string
  data: Record<string, number>
}

async function fetchRates(): Promise<ForexRates> {
  try {
    const resp = await api.get<ForexRatesResponse>('/prices/forex-rates')
    return (resp as ForexRatesResponse).data ?? {}
  } catch {
    return {}
  }
}

export function useForexRates(): { rates: ForexRates; isLoading: boolean } {
  const [rates, setRates] = useState<ForexRates>(_cachedRates ?? {})
  const [isLoading, setIsLoading] = useState(_cachedRates === null)

  useEffect(() => {
    if (_cachedRates !== null && Date.now() < _cacheExpiry) {
      setRates(_cachedRates)
      setIsLoading(false)
      return
    }

    let cancelled = false
    fetchRates().then((r) => {
      if (cancelled) return
      _cachedRates = r
      _cacheExpiry = Date.now() + CACHE_TTL_MS
      setRates(r)
      setIsLoading(false)
    })

    return () => {
      cancelled = true
    }
  }, [])

  return { rates, isLoading }
}

/**
 * Convert *amount* from *fromCurrency* to *toCurrency* using *rates*.
 *
 * Lookup order:
 * 1. Direct pair  "FROM/TO"
 * 2. Inverse pair "TO/FROM"  (1 / rate)
 * 3. Cross via TRY: (FROM/TRY) / (TO/TRY)
 *
 * Returns *amount* unchanged when no path is found.
 */
export function convertCurrency(
  amount: number,
  fromCurrency: string,
  toCurrency: string,
  rates: ForexRates,
): number | null {
  if (!isFinite(amount)) return null
  if (fromCurrency === toCurrency) return amount

  // Direct
  const direct = rates[`${fromCurrency}/${toCurrency}`]
  if (direct != null && direct > 0) return amount * direct

  // Inverse
  const inverse = rates[`${toCurrency}/${fromCurrency}`]
  if (inverse != null && inverse > 0) return amount / inverse

  // Cross via TRY
  const fromToTry = rates[`${fromCurrency}/TRY`]
  const toToTry   = rates[`${toCurrency}/TRY`]
  if (fromToTry != null && fromToTry > 0 && toToTry != null && toToTry > 0) {
    return amount * (fromToTry / toToTry)
  }

  return null
}
