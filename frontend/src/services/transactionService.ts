import { api } from '@/services/api'
import type { Transaction, TransactionType } from '@/types'

interface TransactionListResponse { status: string; data: Transaction[] }
interface TransactionResponse     { status: string; data: Transaction  }

export interface TransactionCreatePayload {
  transaction_type: TransactionType
  quantity?: number
  total_amount?: number
  price_per_unit: number
  transaction_currency: string
  transaction_date?: string  // YYYY-MM-DD; omit to default to today
  notes?: string
  affects_cash: boolean
}

export type TransactionUpdatePayload = Partial<TransactionCreatePayload>

export const transactionService = {
  list: (assetId: string) =>
    api
      .get<TransactionListResponse>(`/assets/${assetId}/transactions`)
      .then((r) => (r as TransactionListResponse).data),

  create: (assetId: string, body: TransactionCreatePayload) =>
    api
      .post<TransactionResponse>(`/assets/${assetId}/transactions`, body)
      .then((r) => (r as TransactionResponse).data),

  update: (txId: string, body: TransactionUpdatePayload) =>
    api
      .put<TransactionResponse>(`/transactions/${txId}`, body)
      .then((r) => (r as TransactionResponse).data),

  remove: (txId: string) =>
    api.delete<unknown>(`/transactions/${txId}`),
}
