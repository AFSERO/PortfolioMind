import { api } from '@/services/api'
import type { Liability, LiabilityType } from '@/types'


interface LiabilityListResponse {
  status: string
  data: Liability[]
}

interface LiabilityResponse {
  status: string
  data: Liability
}

export interface LiabilityCreatePayload {
  name: string
  liability_type: LiabilityType
  currency: string
  current_balance: string
  original_balance?: string | null
  interest_rate?: string | null
  minimum_payment?: string | null
  due_date?: string | null
  notes?: string | null
  is_active: boolean
}

export type LiabilityUpdatePayload = Partial<LiabilityCreatePayload>


export const liabilityService = {
  list: () =>
    api
      .get<LiabilityListResponse>('/liabilities')
      .then((response) => (response as LiabilityListResponse).data),

  get: (id: string) =>
    api
      .get<LiabilityResponse>(`/liabilities/${id}`)
      .then((response) => (response as LiabilityResponse).data),

  create: (payload: LiabilityCreatePayload) =>
    api
      .post<LiabilityResponse>('/liabilities', payload)
      .then((response) => (response as LiabilityResponse).data),

  update: (id: string, payload: LiabilityUpdatePayload) =>
    api
      .put<LiabilityResponse>(`/liabilities/${id}`, payload)
      .then((response) => (response as LiabilityResponse).data),

  delete: (id: string) => api.delete<unknown>(`/liabilities/${id}`),
}

