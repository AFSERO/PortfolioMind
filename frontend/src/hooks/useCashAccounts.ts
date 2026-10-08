import { useState, useEffect, useCallback } from 'react'
import type { CashAccount, CashMovement } from '@/types'
import { cashService } from '@/services/cashService'
import type { DepositPayload, WithdrawPayload, TransferPayload } from '@/services/cashService'

export function useCashAccounts() {
  const [accounts, setAccounts] = useState<CashAccount[]>([])
  const [movements, setMovements] = useState<CashMovement[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    try {
      const [accts, mvts] = await Promise.all([
        cashService.getAccounts(),
        cashService.getMovements(),
      ])
      setAccounts(accts)
      setMovements(mvts)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load cash accounts')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const deposit = useCallback(async (payload: DepositPayload) => {
    await cashService.deposit(payload)
    await fetchAll()
  }, [fetchAll])

  const withdraw = useCallback(async (payload: WithdrawPayload) => {
    await cashService.withdraw(payload)
    await fetchAll()
  }, [fetchAll])

  const transfer = useCallback(async (payload: TransferPayload) => {
    await cashService.transfer(payload)
    await fetchAll()
  }, [fetchAll])

  return { accounts, movements, isLoading, error, refetch: fetchAll, deposit, withdraw, transfer }
}
