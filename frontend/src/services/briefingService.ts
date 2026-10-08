import { api } from '@/services/api'
import type { BriefingReviewResponse, BriefingRun, BriefingStats } from '@/types'

interface BriefingRunResponse {
  status: string
  data: BriefingRun | null
}

interface BriefingStatsResponse {
  status: string
  data: BriefingStats
}

interface BriefingItemReviewApiResponse {
  status: string
  data: BriefingReviewResponse
}

export const briefingService = {
  getLatestBriefing: () =>
    api
      .get<BriefingRunResponse>('/briefing/latest')
      .then((r) => (r as BriefingRunResponse).data),

  generateBriefing: (params?: { scope?: string; force_refresh?: boolean }) =>
    api
      .post<BriefingRunResponse>('/briefing/generate', {
        scope: params?.scope ?? 'PORTFOLIO_AND_WATCHLIST',
        force_refresh: params?.force_refresh ?? false,
      })
      .then((r) => (r as BriefingRunResponse).data),

  getBriefingStats: () =>
    api
      .get<BriefingStatsResponse>('/briefing/stats')
      .then((r) => (r as BriefingStatsResponse).data),

  runItemReview: (itemId: string, forceRerun: boolean = false) =>
    api
      .post<BriefingItemReviewApiResponse>(`/briefing/items/${itemId}/review`, {
        force_rerun: forceRerun,
      })
      .then((r) => (r as BriefingItemReviewApiResponse).data),

  getItemReviewStatus: (itemId: string) =>
    api
      .get<BriefingItemReviewApiResponse>(`/briefing/items/${itemId}/review`)
      .then((r) => (r as BriefingItemReviewApiResponse).data),
}
