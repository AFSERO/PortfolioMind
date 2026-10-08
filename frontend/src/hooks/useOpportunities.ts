import { useState, useEffect, useCallback } from 'react'
import type {
  ResearchQueueResponse,
  WatchlistItem,
} from '@/types'
import { opportunityService } from '@/services/opportunityService'

export function useOpportunities() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [researchQueue, setResearchQueue] = useState<ResearchQueueResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setIsLoading(true)
    try {
      const [wlData, rqData] = await Promise.all([
        opportunityService.getWatchlist(),
        opportunityService.getResearchQueue(),
      ])
      setWatchlist(wlData || [])
      setResearchQueue(rqData || null)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load opportunities')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  const addToWatchlist = useCallback(async (payload: any) => {
    const item = await opportunityService.addToWatchlist(payload)
    await refetch()
    return item
  }, [refetch])

  const updateWatchlistItem = useCallback(async (id: string, payload: any) => {
    const updated = await opportunityService.updateWatchlistItem(id, payload)
    await refetch()
    return updated
  }, [refetch])

  const deleteWatchlistItem = useCallback(async (id: string) => {
    await opportunityService.deleteWatchlistItem(id)
    await refetch()
  }, [refetch])

  const evaluate = useCallback(async (params?: { instrument_id?: string; force_refresh?: boolean }) => {
    const res = await opportunityService.evaluateOpportunities(params)
    await refetch()
    return res
  }, [refetch])

  const launchReview = useCallback(async (instrumentId: string, protocol?: string) => {
    const res = await opportunityService.launchSuggestedReview(instrumentId, protocol)
    await refetch()
    return res
  }, [refetch])

  return {
    watchlist,
    researchQueue,
    isLoading,
    error,
    refetch,
    addToWatchlist,
    updateWatchlistItem,
    deleteWatchlistItem,
    evaluate,
    launchReview,
  }
}
