import { api } from '@/services/api'
import type { Asset, AssetType, TransactionType } from '@/types'

interface AssetListResponse { status: string; data: Asset[] }
interface AssetResponse    { status: string; data: Asset  }

export interface InitialTransactionPayload {
  transaction_type: TransactionType  // always 'BUY' from the create form
  quantity?: number
  total_amount?: number
  price_per_unit: number
  transaction_currency: string
  transaction_date?: string  // YYYY-MM-DD; omit to default to today
  notes?: string
  affects_cash: boolean
}

export interface AssetCreatePayload {
  asset_type: AssetType
  symbol?: string
  name: string
  current_price?: number | null
  current_price_currency?: string | null
  is_manual_price?: boolean
  notes?: string
  initial_transaction?: InitialTransactionPayload
}

/** Edits to a position's metadata only — never quantity / cost (those flow from transactions). */
export interface AssetUpdatePayload {
  name?: string
  symbol?: string
  current_price?: number | null
  current_price_currency?: string | null
  is_manual_price?: boolean
  notes?: string
}

export interface ManualPricePayload {
  current_price: number
  current_price_currency: string
}

export const assetService = {
  list: (type?: AssetType) => {
    const qs = type ? `?asset_type=${type}` : ''
    return api.get<AssetListResponse>(`/assets${qs}`).then((r) => (r as AssetListResponse).data)
  },

  get: (id: string) =>
    api.get<AssetResponse>(`/assets/${id}`).then((r) => (r as AssetResponse).data),

  create: (payload: AssetCreatePayload) =>
    api.post<AssetResponse>('/assets', payload).then((r) => (r as AssetResponse).data),

  update: (id: string, payload: AssetUpdatePayload) =>
    api.put<AssetResponse>(`/assets/${id}`, payload).then((r) => (r as AssetResponse).data),

  delete: (id: string) =>
    api.delete<unknown>(`/assets/${id}`),

  updatePrice: (id: string, payload: ManualPricePayload) =>
    api.post<AssetResponse>(`/assets/${id}/update-price`, payload).then((r) => (r as AssetResponse).data),

  getPriceHistory: (id: string, limit = 90) =>
    api.get<{ status: string; data: import('@/types').PriceHistory[] }>(`/assets/${id}/price-history?limit=${limit}`)
      .then((r) => (r as { status: string; data: import('@/types').PriceHistory[] }).data),

  runDeepResearch: (id: string, protocol?: string) =>
    api.post<{ status: string; data: any }>(`/assets/${id}/research`, { protocol })
      .then((r) => (r as { status: string; data: any }).data),
}
