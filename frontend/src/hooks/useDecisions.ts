import { useCallback, useEffect, useState } from 'react'
import { decisionService, type DecisionListParams } from '@/services/decisionService'
import type {
  DecisionLogCreateRequest,
  DecisionLogEntry,
  DecisionLogUpdateRationaleRequest,
} from '@/types'

export function useDecisions(initialParams?: DecisionListParams) {
  const [decisions, setDecisions] = useState<DecisionLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDecisions = useCallback(async (params?: DecisionListParams) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await decisionService.getDecisions(params ?? initialParams)
      setDecisions(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch decisions')
    } finally {
      setIsLoading(false)
    }
  }, [initialParams])

  useEffect(() => {
    fetchDecisions()
  }, [fetchDecisions])

  const createDecision = useCallback(
    async (payload: DecisionLogCreateRequest) => {
      const created = await decisionService.createDecision(payload)
      setDecisions((prev) => [created, ...prev])
      setTotal((prev) => prev + 1)
      return created
    },
    []
  )

  const updateRationale = useCallback(
    async (id: string, payload: DecisionLogUpdateRationaleRequest) => {
      const updated = await decisionService.updateRationale(id, payload)
      setDecisions((prev) =>
        prev.map((item) => (item.id === id ? updated : item))
      )
      return updated
    },
    []
  )

  return {
    decisions,
    total,
    isLoading,
    error,
    fetchDecisions,
    createDecision,
    updateRationale,
  }
}
