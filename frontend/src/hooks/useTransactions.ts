import { useState, useEffect, useCallback } from 'react'
import type { Transaction } from '@/types'
import {
  transactionService,
  type TransactionCreatePayload,
  type TransactionUpdatePayload,
} from '@/services/transactionService'

export function useTransactions(assetId: string | undefined) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!assetId) {
      setTransactions([])
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    try {
      const data = await transactionService.list(assetId)
      setTransactions(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load transactions')
    } finally {
      setIsLoading(false)
    }
  }, [assetId])

  useEffect(() => { refetch() }, [refetch])

  const create = useCallback(
    async (body: TransactionCreatePayload) => {
      if (!assetId) throw new Error('No asset')
      const tx = await transactionService.create(assetId, body)
      await refetch()
      return tx
    },
    [assetId, refetch],
  )

  const update = useCallback(
    async (txId: string, body: TransactionUpdatePayload) => {
      const tx = await transactionService.update(txId, body)
      await refetch()
      return tx
    },
    [refetch],
  )

  const remove = useCallback(
    async (txId: string) => {
      await transactionService.remove(txId)
      await refetch()
    },
    [refetch],
  )

  return { transactions, isLoading, error, refetch, create, update, remove }
}
