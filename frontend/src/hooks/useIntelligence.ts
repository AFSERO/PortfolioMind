import { useState, useEffect, useCallback } from 'react'
import type { IntelligenceReview, TechnicalPlan } from '@/types'
import { intelligenceService } from '@/services/intelligenceService'

export function useInstrumentReviews(instrumentId?: string | null) {
  const [reviews, setReviews] = useState<IntelligenceReview[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!instrumentId) {
      setReviews([])
      return
    }
    setIsLoading(true)
    try {
      const data = await intelligenceService.getReviews(instrumentId)
      setReviews(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load intelligence reviews')
    } finally {
      setIsLoading(false)
    }
  }, [instrumentId])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { reviews, isLoading, error, refetch }
}

export function useTechnicalPlan(instrumentId?: string | null) {
  const [plan, setPlan] = useState<TechnicalPlan | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!instrumentId) {
      setPlan(null)
      return
    }
    setIsLoading(true)
    try {
      const data = await intelligenceService.getTechnicalPlan(instrumentId)
      setPlan(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load technical plan')
    } finally {
      setIsLoading(false)
    }
  }, [instrumentId])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { plan, isLoading, error, refetch }
}
