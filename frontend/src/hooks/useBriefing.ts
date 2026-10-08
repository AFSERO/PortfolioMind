import { useCallback, useEffect, useState } from 'react'
import { briefingService } from '@/services/briefingService'
import type { BriefingItem, BriefingRun, BriefingStats } from '@/types'

export function useBriefing() {
  const [briefing, setBriefing] = useState<BriefingRun | null>(null)
  const [stats, setStats] = useState<BriefingStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchBriefing = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await briefingService.getLatestBriefing()
      setBriefing(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch briefing')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const data = await briefingService.getBriefingStats()
      setStats(data)
    } catch {
      // Non-critical background stats
    }
  }, [])

  const generateBriefing = useCallback(
    async (forceRefresh = true) => {
      setIsGenerating(true)
      setError(null)
      try {
        const data = await briefingService.generateBriefing({
          force_refresh: forceRefresh,
        })
        setBriefing(data)
        if (data) {
          const attCount = data.items.filter((i) => i.review_required).length
          setStats({
            attention_count: attCount,
            items_shown: data.items_shown,
            items_filtered: data.items_filtered,
            last_generated_at: data.generated_at,
          })
        }
        return data
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to generate briefing')
        throw err
      } finally {
        setIsGenerating(false)
      }
    },
    []
  )

  const updateBriefingItem = useCallback((itemId: string, updates: Partial<BriefingItem>) => {
    setBriefing((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        items: prev.items.map((item) => (item.id === itemId ? { ...item, ...updates } : item)),
      }
    })
  }, [])

  useEffect(() => {
    fetchBriefing()
    fetchStats()
  }, [fetchBriefing, fetchStats])

  return {
    briefing,
    stats,
    isLoading,
    isGenerating,
    error,
    fetchBriefing,
    fetchStats,
    generateBriefing,
    updateBriefingItem,
  }
}
