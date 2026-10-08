import { useState, useEffect, useCallback } from 'react'
import type { DiscoveryRun, DiscoveryUniverse } from '@/types'
import { discoveryService } from '@/services/discoveryService'

export function useDiscovery() {
  const [run, setRun] = useState<DiscoveryRun | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isScanning, setIsScanning] = useState(false)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await discoveryService.getLatestRun()
      setRun(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load discovery data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  const triggerScan = useCallback(
    async (universe?: DiscoveryUniverse, forceRefresh: boolean = false) => {
      setIsScanning(true)
      setError(null)
      try {
        const newRun = await discoveryService.triggerScan({
          universe,
          force_refresh: forceRefresh,
        })
        setRun(newRun)
        return newRun
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to run discovery scan'
        setError(msg)
        throw e
      } finally {
        setIsScanning(false)
      }
    },
    [],
  )

  const addToWatchlist = useCallback(
    async (candidateId: string) => {
      setActionInProgress(candidateId)
      try {
        const res = await discoveryService.addToWatchlist(candidateId)
        await refetch()
        return res
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to add candidate to watchlist'
        setError(msg)
        throw e
      } finally {
        setActionInProgress(null)
      }
    },
    [refetch],
  )

  const dismissCandidate = useCallback(
    async (candidateId: string) => {
      setActionInProgress(candidateId)
      try {
        const res = await discoveryService.dismissCandidate(candidateId)
        await refetch()
        return res
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to dismiss candidate'
        setError(msg)
        throw e
      } finally {
        setActionInProgress(null)
      }
    },
    [refetch],
  )

  const screenCandidate = useCallback(
    async (candidateId: string) => {
      setActionInProgress(candidateId)
      try {
        const res = await discoveryService.screenCandidate(candidateId)
        await refetch()
        return res
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to execute preliminary screening'
        setError(msg)
        throw e
      } finally {
        setActionInProgress(null)
      }
    },
    [refetch],
  )

  return {
    run,
    isLoading,
    isScanning,
    actionInProgress,
    error,
    refetch,
    triggerScan,
    addToWatchlist,
    dismissCandidate,
    screenCandidate,
  }
}
