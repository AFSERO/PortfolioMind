import { api } from '@/services/api'
import type { AssetType, Instrument } from '@/types'

interface InstrumentListResponse {
  status: string
  data: Instrument[]
}

interface InstrumentResponse {
  status: string
  data: Instrument
}

export interface InstrumentCreatePayload {
  name: string
  asset_type: AssetType
  symbol?: string
  exchange?: string
  currency?: string
  country?: string
  isin?: string
}

export const instrumentService = {
  list: (q?: string, assetType?: AssetType, limit = 50) => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (assetType) params.set('asset_type', assetType)
    params.set('limit', limit.toString())

    return api
      .get<InstrumentListResponse>(`/instruments?${params.toString()}`)
      .then((r) => (r as InstrumentListResponse).data)
  },

  get: (id: string) =>
    api
      .get<InstrumentResponse>(`/instruments/${id}`)
      .then((r) => (r as InstrumentResponse).data),

  create: (payload: InstrumentCreatePayload) =>
    api
      .post<InstrumentResponse>('/instruments', payload)
      .then((r) => (r as InstrumentResponse).data),
}
