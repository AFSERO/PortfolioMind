import { api } from '@/services/api'
import type { DiscoveryRun, DiscoveryUniverse } from '@/types'

export interface ActionResponse {
  status: string
  message: string
  candidate_id?: string
  extra?: Record<string, any>
}

export const discoveryService = {
  getLatestRun: async (): Promise<DiscoveryRun | null> => {
    const res = await api.get<any>('/discovery/runs/latest')
    if (!res) return null
    return (res.data ?? res) as DiscoveryRun
  },

  triggerScan: async (payload?: {
    universe?: DiscoveryUniverse
    force_refresh?: boolean
  }): Promise<DiscoveryRun> => {
    const res = await api.post<any>('/discovery/scan', payload ?? {})
    return (res.data ?? res) as DiscoveryRun
  },

  addToWatchlist: async (candidateId: string): Promise<ActionResponse> => {
    const res = await api.post<any>(`/discovery/candidates/${candidateId}/add-to-watchlist`, {})
    return (res.data ?? res) as ActionResponse
  },

  dismissCandidate: async (candidateId: string): Promise<ActionResponse> => {
    const res = await api.post<any>(`/discovery/candidates/${candidateId}/dismiss`, {})
    return (res.data ?? res) as ActionResponse
  },

  screenCandidate: async (candidateId: string): Promise<ActionResponse> => {
    const res = await api.post<any>(`/discovery/candidates/${candidateId}/screen`, {})
    return (res.data ?? res) as ActionResponse
  },
}
