import { useState, useEffect, useCallback } from 'react'
import type { DashboardSummary, AllocationData, TimelinePoint } from '@/types'
import { dashboardService } from '@/services/dashboardService'
import { onPricesRefreshed } from '@/services/priceService'

function useQuery<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setIsLoading(true)
    }
    try {
      const result = await fetcher()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      if (!options?.silent) {
        setIsLoading(false)
      }
    }
  }, [fetcher])

  useEffect(() => { run() }, [run])

  useEffect(() => {
    return onPricesRefreshed(() => {
      run({ silent: true })
    })
  }, [run])

  return { data, isLoading, error, refetch: run }
}

export function useDashboardSummary() {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetcher = useCallback(() => dashboardService.getSummary(), [])
  return useQuery<DashboardSummary>(fetcher)
}

export function useDashboardAllocation() {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fetcher = useCallback(() => dashboardService.getAllocation(), [])
  return useQuery<AllocationData>(fetcher)
}

export function useDashboardTimeline(days: number) {
  const fetcher = useCallback(
    () => dashboardService.getTimeline(days),
    [days],
  )
  return useQuery<TimelinePoint[]>(fetcher)
}
