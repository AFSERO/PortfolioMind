import { useCallback, useEffect, useState } from 'react'

import { liabilityService } from '@/services/liabilityService'
import type {
  LiabilityCreatePayload,
  LiabilityUpdatePayload,
} from '@/services/liabilityService'
import type { Liability } from '@/types'


export function useLiabilities() {
  const [liabilities, setLiabilities] = useState<Liability[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await liabilityService.list()
      setLiabilities(data)
      setError(null)
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Failed to load liabilities',
      )
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refetch()
  }, [refetch])

  const createLiability = useCallback(
    async (payload: LiabilityCreatePayload): Promise<Liability> => {
      const liability = await liabilityService.create(payload)
      setLiabilities((current) => [liability, ...current])
      return liability
    },
    [],
  )

  const updateLiability = useCallback(
    async (id: string, payload: LiabilityUpdatePayload): Promise<Liability> => {
      const updated = await liabilityService.update(id, payload)
      setLiabilities((current) =>
        current.map((liability) => (liability.id === id ? updated : liability)),
      )
      return updated
    },
    [],
  )

  const deleteLiability = useCallback(async (id: string): Promise<void> => {
    await liabilityService.delete(id)
    setLiabilities((current) =>
      current.filter((liability) => liability.id !== id),
    )
  }, [])

  return {
    liabilities,
    isLoading,
    error,
    refetch,
    createLiability,
    updateLiability,
    deleteLiability,
  }
}

