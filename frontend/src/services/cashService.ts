import { api } from '@/services/api'
import type { CashAccount, CashMovement } from '@/types'

interface AccountsResponse { status: string; data: CashAccount[] }
interface AccountResponse { status: string; data: CashAccount }
interface MovementsResponse { status: string; data: CashMovement[] }
interface TransferResponse {
  status: string
  data: { from_account: CashAccount; to_account: CashAccount }
}

export interface DepositPayload {
  currency: string
  amount: number
  notes?: string
}

export interface WithdrawPayload {
  currency: string
  amount: number
  notes?: string
}

export interface TransferPayload {
  from_currency: string
  to_currency: string
  from_amount: number
  rate: number
  notes?: string
}

export const cashService = {
  getAccounts: () =>
    api.get<AccountsResponse>('/cash').then((r) => (r as AccountsResponse).data),

  getMovements: (limit = 100) =>
    api.get<MovementsResponse>(`/cash/movements?limit=${limit}`).then((r) => (r as MovementsResponse).data),

  deposit: (payload: DepositPayload) =>
    api.post<AccountResponse>('/cash/deposit', payload).then((r) => (r as AccountResponse).data),

  withdraw: (payload: WithdrawPayload) =>
    api.post<AccountResponse>('/cash/withdraw', payload).then((r) => (r as AccountResponse).data),

  transfer: (payload: TransferPayload) =>
    api.post<TransferResponse>('/cash/transfer', payload).then((r) => (r as TransferResponse).data),
}
