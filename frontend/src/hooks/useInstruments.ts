import { useState, useEffect, useCallback } from 'react'
import type { AssetType, Instrument } from '@/types'
import { instrumentService, type InstrumentCreatePayload } from '@/services/instrumentService'

export function useInstruments(q?: string, assetType?: AssetType) {
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await instrumentService.list(q, assetType)
      setInstruments(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load instruments')
    } finally {
      setIsLoading(false)
    }
  }, [q, assetType])

  useEffect(() => {
    refetch()
  }, [refetch])

  const createInstrument = useCallback(async (payload: InstrumentCreatePayload): Promise<Instrument> => {
    const inst = await instrumentService.create(payload)
    setInstruments((prev) => [inst, ...prev])
    return inst
  }, [])

  return { instruments, isLoading, error, refetch, createInstrument }
}
