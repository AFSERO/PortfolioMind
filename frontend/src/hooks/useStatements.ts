import { useCallback, useEffect, useState } from 'react'

import { liabilityService } from '@/services/liabilityService'
import { statementService } from '@/services/statementService'
import type {
  InstallmentForecast,
  InstallmentPlan,
  Liability,
  LiabilityStatement,
} from '@/types'


export function useStatementWorkspace(liabilityId: string | undefined) {
  const [liability, setLiability] = useState<Liability | null>(null)
  const [statements, setStatements] = useState<LiabilityStatement[]>([])
  const [plans, setPlans] = useState<InstallmentPlan[]>([])
  const [forecast, setForecast] = useState<InstallmentForecast | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!liabilityId) return
    setIsLoading(true)
    try {
      const [nextLiability, nextStatements, nextPlans, nextForecast] =
        await Promise.all([
          liabilityService.get(liabilityId),
          statementService.list(liabilityId),
          statementService.listPlans(liabilityId),
          statementService.forecast(liabilityId),
        ])
      setLiability(nextLiability)
      setStatements(nextStatements)
      setPlans(nextPlans)
      setForecast(nextForecast)
      setError(null)
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Failed to load statements',
      )
    } finally {
      setIsLoading(false)
    }
  }, [liabilityId])

  useEffect(() => {
    void refetch()
  }, [refetch])

  return {
    liability,
    statements,
    plans,
    forecast,
    isLoading,
    error,
    refetch,
  }
}


export function useStatementDetail(
  liabilityId: string | undefined,
  statementId: string | undefined,
) {
  const [statement, setStatement] = useState<LiabilityStatement | null>(null)
  const [plans, setPlans] = useState<InstallmentPlan[]>([])
  const [forecast, setForecast] = useState<InstallmentForecast | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!liabilityId || !statementId) return
    setIsLoading(true)
    try {
      const [nextStatement, nextPlans, nextForecast] = await Promise.all([
        statementService.get(statementId),
        statementService.listPlans(liabilityId),
        statementService.forecast(liabilityId),
      ])
      setStatement(nextStatement)
      setPlans(nextPlans)
      setForecast(nextForecast)
      setError(null)
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Failed to load statement',
      )
    } finally {
      setIsLoading(false)
    }
  }, [liabilityId, statementId])

  useEffect(() => {
    void refetch()
  }, [refetch])

  return { statement, plans, forecast, isLoading, error, refetch }
}
