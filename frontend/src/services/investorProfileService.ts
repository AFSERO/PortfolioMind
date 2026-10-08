import { api } from '@/services/api'
import type {
  AssessmentState,
  InvestorProfileData,
  InvestorProfileDraft,
  InvestorProfileVersionSummary,
  QuestionDefinition,
  SectionDefinition,
} from '@/types/investorProfile'

export interface QuestionCatalogResponse {
  sections: SectionDefinition[]
  questions: QuestionDefinition[]
}

export const investorProfileService = {
  async getQuestions(): Promise<QuestionCatalogResponse> {
    const res = await api.get<{ status: string; data: QuestionCatalogResponse }>('/investor-profile/questions')
    return res.data
  },

  async getCurrentAssessment(): Promise<AssessmentState> {
    const res = await api.get<{ status: string; data: AssessmentState }>('/investor-profile/assessment/current')
    return res.data
  },

  async saveAnswer(payload: {
    question_id: string
    item_id?: string
    knowledge_state?: string
    selected_options?: string[]
    numeric_inputs?: Record<string, any>
    raw_text?: string
    locale?: string
  }): Promise<any> {
    const res = await api.post<{ status: string; data: any }>('/investor-profile/assessment/answer', payload)
    return res.data
  },

  async skipQuestion(question_id: string, item_id?: string): Promise<any> {
    let url = `/investor-profile/assessment/skip-question?question_id=${encodeURIComponent(question_id)}`
    if (item_id) {
      url += `&item_id=${encodeURIComponent(item_id)}`
    }
    const res = await api.post<{ status: string; data: any }>(url, {})
    return res.data
  },

  async getDraft(): Promise<InvestorProfileDraft> {
    const res = await api.get<{ status: string; data: InvestorProfileDraft }>('/investor-profile/draft')
    return res.data
  },

  async updateDraft(updated_data: Record<string, any>): Promise<InvestorProfileDraft> {
    const res = await api.put<{ status: string; data: InvestorProfileDraft }>('/investor-profile/draft', updated_data)
    return res.data
  },

  async confirmProfile(change_reason?: string, change_source?: string): Promise<any> {
    const res = await api.post<{ status: string; data: any }>('/investor-profile/confirm', {
      change_reason: change_reason || 'Profile confirmed',
      change_source: change_source || 'ONBOARDING',
    })
    return res.data
  },

  async getCurrentProfile(): Promise<InvestorProfileData> {
    const res = await api.get<{ status: string; data: InvestorProfileData }>('/investor-profile/current')
    return res.data
  },

  async getVersions(): Promise<InvestorProfileVersionSummary[]> {
    const res = await api.get<{ status: string; data: InvestorProfileVersionSummary[] }>('/investor-profile/versions')
    return res.data
  },

  async getVersionDetail(version_id: string): Promise<any> {
    const res = await api.get<{ status: string; data: any }>(`/investor-profile/versions/${version_id}`)
    return res.data
  },

  async updateProfile(changes: Record<string, any>, reason?: string): Promise<any> {
    const res = await api.patch<{ status: string; data: any }>('/investor-profile/update', {
      changes,
      reason: reason || 'Settings update',
    })
    return res.data
  },
}
