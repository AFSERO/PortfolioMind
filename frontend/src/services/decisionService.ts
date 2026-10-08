import { api } from '@/services/api'
import type {
  DecisionLogCreateRequest,
  DecisionLogEntry,
  DecisionLogUpdateRationaleRequest,
} from '@/types'

interface DecisionsListResponse {
  status: string
  data: {
    items: DecisionLogEntry[]
    total: number
  }
}

interface DecisionItemResponse {
  status: string
  data: DecisionLogEntry
}

export interface DecisionListParams {
  instrument_id?: string
  asset_id?: string
  event_type?: string
  limit?: number
  offset?: number
}

export const decisionService = {
  getDecisions: (params?: DecisionListParams) => {
    const query = new URLSearchParams()
    if (params?.instrument_id) query.set('instrument_id', params.instrument_id)
    if (params?.asset_id) query.set('asset_id', params.asset_id)
    if (params?.event_type) query.set('event_type', params.event_type)
    if (params?.limit !== undefined) query.set('limit', String(params.limit))
    if (params?.offset !== undefined) query.set('offset', String(params.offset))

    const qs = query.toString()
    const url = qs ? `/decisions?${qs}` : '/decisions'
    return api
      .get<DecisionsListResponse>(url)
      .then((r) => (r as DecisionsListResponse).data)
  },

  getDecision: (id: string) =>
    api
      .get<DecisionItemResponse>(`/decisions/${id}`)
      .then((r) => (r as DecisionItemResponse).data),

  createDecision: (payload: DecisionLogCreateRequest) =>
    api
      .post<DecisionItemResponse>('/decisions', payload)
      .then((r) => (r as DecisionItemResponse).data),

  updateRationale: (id: string, payload: DecisionLogUpdateRationaleRequest) =>
    api
      .patch<DecisionItemResponse>(`/decisions/${id}/rationale`, payload)
      .then((r) => (r as DecisionItemResponse).data),
}
