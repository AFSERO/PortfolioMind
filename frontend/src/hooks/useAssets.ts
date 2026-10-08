import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import type { Asset } from '@/types'
import { assetService, type AssetCreatePayload, type AssetUpdatePayload } from '@/services/assetService'
import { priceService, onPricesRefreshed, notifyPricesRefreshed } from '@/services/priceService'

// ── List ─────────────────────────────────────────────────────────────────────

export function useAssets() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setIsLoading(true)
    }
    try {
      const data = await assetService.list()
      setAssets(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load assets')
    } finally {
      if (!options?.silent) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => { refetch() }, [refetch])

  useEffect(() => {
    return onPricesRefreshed(() => {
      refetch({ silent: true })
    })
  }, [refetch])

  const createAsset = useCallback(async (payload: AssetCreatePayload): Promise<Asset> => {
    const asset = await assetService.create(payload)
    setAssets((prev) => [asset, ...prev])
    return asset
  }, [])

  const updateAsset = useCallback(async (id: string, payload: AssetUpdatePayload): Promise<Asset> => {
    const updated = await assetService.update(id, payload)
    setAssets((prev) => prev.map((a) => (a.id === id ? updated : a)))
    return updated
  }, [])

  const deleteAsset = useCallback(async (id: string): Promise<void> => {
    await assetService.delete(id)
    setAssets((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const refreshPrices = useCallback(async (): Promise<void> => {
    const results = await priceService.refreshPrices()
    // Refetch and notify all other screens
    notifyPricesRefreshed()
    await refetch()
    const updated = Array.isArray(results)
      ? results.filter((r: unknown) => (r as { status: string }).status === 'updated').length
      : 0
    toast.success(`Prices refreshed — ${updated} updated`)
  }, [refetch])

  return { assets, isLoading, error, refetch, createAsset, updateAsset, deleteAsset, refreshPrices }
}

// ── Single asset ──────────────────────────────────────────────────────────────

export function useAssetDetail(id: string) {
  const [asset, setAsset] = useState<Asset | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async (options?: { silent?: boolean }) => {
    if (!id) return
    if (!options?.silent) {
      setIsLoading(true)
    }
    try {
      const data = await assetService.get(id)
      setAsset(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Asset not found')
    } finally {
      if (!options?.silent) {
        setIsLoading(false)
      }
    }
  }, [id])

  useEffect(() => { refetch() }, [refetch])

  useEffect(() => {
    return onPricesRefreshed(() => {
      refetch({ silent: true })
    })
  }, [refetch])

  const updatePrice = useCallback(async (price: number, currency: string) => {
    if (!id) return
    const updated = await assetService.updatePrice(id, {
      current_price: price,
      current_price_currency: currency,
    })
    setAsset(updated)
    return updated
  }, [id])

  return { asset, isLoading, error, refetch, updatePrice }
}
