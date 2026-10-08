import { api } from '@/services/api'
import type {
  InstrumentIntelligenceState,
  IntelligenceReview,
  TechnicalPlan,
} from '@/types'

interface IntelligenceStateResponse {
  status: string
  data: InstrumentIntelligenceState | null
}

interface ReviewsResponse {
  status: string
  data: IntelligenceReview[]
}

interface TechnicalPlanResponse {
  status: string
  data: TechnicalPlan | null
}

export const intelligenceService = {
  getIntelligenceState: (instrumentId: string) =>
    api
      .get<IntelligenceStateResponse>(`/instruments/${instrumentId}/intelligence`)
      .then((r) => (r as IntelligenceStateResponse).data),

  getReviews: (instrumentId: string, limit = 50) =>
    api
      .get<ReviewsResponse>(`/instruments/${instrumentId}/reviews?limit=${limit}`)
      .then((r) => (r as ReviewsResponse).data),

  getTechnicalPlan: (instrumentId: string) =>
    api
      .get<TechnicalPlanResponse>(`/instruments/${instrumentId}/technical-plan`)
      .then((r) => (r as TechnicalPlanResponse).data),
}
