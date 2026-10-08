import { api } from '@/services/api'
import type {
  BriefingReviewResponse,
  ResearchQueueResponse,
  WatchlistItem,
} from '@/types'

interface WatchlistApiResponse {
  status: string
  data: WatchlistItem[]
}

interface WatchlistItemApiResponse {
  status: string
  data: WatchlistItem
}

interface OpportunityEvaluationSummaryResponse {
  status: string
  data: {
    total_candidates: number
    evaluated: number
    opportunities_found: number
    research_now_count: number
    research_soon_count: number
    items: any[]
  }
}

interface ResearchQueueApiResponse {
  status: string
  data: ResearchQueueResponse
}

interface LaunchReviewApiResponse {
  status: string
  data: BriefingReviewResponse
}

export const opportunityService = {
  getWatchlist: () =>
    api
      .get<WatchlistApiResponse>('/watchlist')
      .then((r) => (r as WatchlistApiResponse).data),

  addToWatchlist: (payload: {
    instrument_id?: string
    name?: string
    symbol?: string
    asset_type?: string
    exchange?: string
    currency?: string
    research_stage?: string
    priority?: string
    why_interesting?: string
    target_entry_min?: number
    target_entry_max?: number
    key_catalyst?: string
    key_risk?: string
    next_expected_event?: string
    notes?: string
  }) =>
    api
      .post<WatchlistItemApiResponse>('/watchlist', payload)
      .then((r) => (r as WatchlistItemApiResponse).data),

  updateWatchlistItem: (
    itemId: string,
    payload: {
      research_stage?: string
      priority?: string
      why_interesting?: string
      target_entry_min?: number
      target_entry_max?: number
      key_catalyst?: string
      key_risk?: string
      next_expected_event?: string
      notes?: string
    }
  ) =>
    api
      .put<WatchlistItemApiResponse>(`/watchlist/${itemId}`, payload)
      .then((r) => (r as WatchlistItemApiResponse).data),

  deleteWatchlistItem: (itemId: string) =>
    api
      .delete<{ status: string; data: { deleted: boolean; id: string } }>(
        `/watchlist/${itemId}`
      )
      .then((r) => r.data),

  evaluateOpportunities: (params?: {
    instrument_id?: string
    force_refresh?: boolean
  }) =>
    api
      .post<OpportunityEvaluationSummaryResponse>('/opportunities/evaluate', {
        instrument_id: params?.instrument_id,
        force_refresh: params?.force_refresh ?? false,
      })
      .then((r) => (r as OpportunityEvaluationSummaryResponse).data),

  launchSuggestedReview: (instrumentId: string, protocol?: string) =>
    api
      .post<LaunchReviewApiResponse>(
        `/opportunities/${instrumentId}/launch-review`,
        { protocol }
      )
      .then((r) => (r as LaunchReviewApiResponse).data),

  getResearchQueue: () =>
    api
      .get<ResearchQueueApiResponse>('/research')
      .then((r) => (r as ResearchQueueApiResponse).data),
}
