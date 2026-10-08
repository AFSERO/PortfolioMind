import { api } from '@/services/api'
import type { DashboardSummary, AllocationData, TimelinePoint } from '@/types'

interface SummaryResponse {
  status: string
  data: DashboardSummary
}

interface AllocationResponse {
  status: string
  data: AllocationData
}

interface TimelineResponse {
  status: string
  data: TimelinePoint[]
}

export const dashboardService = {
  getSummary: () =>
    api.get<SummaryResponse>('/dashboard/summary').then((r) => (r as SummaryResponse).data),

  getAllocation: () =>
    api.get<AllocationResponse>('/dashboard/allocation').then((r) => (r as AllocationResponse).data),

  getTimeline: (days = 90) =>
    api.get<TimelineResponse>(`/dashboard/timeline?days=${days}`).then((r) => (r as TimelineResponse).data),

  createSnapshot: () =>
    api.post<{ status: string; data: Record<string, any> }>('/dashboard/snapshot', {}).then((r) => (r as any).data),
}
