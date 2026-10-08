import { api } from '@/services/api'
import type {
  FinancialContext,
  FinancialGoal,
  FinancialIntelligenceSummary,
  InvestmentMandate,
  UnassignedResourcesResponse,
} from '@/types/financialContext'

export const financialContextService = {
  async getFinancialContext(): Promise<FinancialContext> {
    const res = await api.get<{ status: string; data: FinancialContext }>('/financial-context')
    return res.data
  },

  async updateFinancialContext(payload: Partial<FinancialContext>): Promise<FinancialContext> {
    const res = await api.put<{ status: string; data: FinancialContext }>('/financial-context', payload)
    return res.data
  },

  async confirmFinancialContext(): Promise<FinancialContext> {
    const res = await api.post<{ status: string; data: FinancialContext }>('/financial-context/confirm', {})
    return res.data
  },

  async getUnassignedResources(): Promise<UnassignedResourcesResponse> {
    const res = await api.get<{ status: string; data: UnassignedResourcesResponse }>('/financial-context/unassigned-resources')
    return res.data
  },

  async listGoals(): Promise<FinancialGoal[]> {
    const res = await api.get<{ status: string; data: FinancialGoal[] }>('/financial-goals')
    return res.data
  },

  async createGoal(payload: Partial<FinancialGoal>): Promise<FinancialGoal> {
    const res = await api.post<{ status: string; data: FinancialGoal }>('/financial-goals', payload)
    return res.data
  },

  async getGoal(goalId: string): Promise<FinancialGoal> {
    const res = await api.get<{ status: string; data: FinancialGoal }>(`/financial-goals/${goalId}`)
    return res.data
  },

  async updateGoal(goalId: string, payload: Partial<FinancialGoal>): Promise<FinancialGoal> {
    const res = await api.put<{ status: string; data: FinancialGoal }>(`/financial-goals/${goalId}`, payload)
    return res.data
  },

  async deleteGoal(goalId: string): Promise<void> {
    await api.delete(`/financial-goals/${goalId}`)
  },

  async listMandates(goalId?: string): Promise<InvestmentMandate[]> {
    const url = goalId ? `/mandates?goal_id=${encodeURIComponent(goalId)}` : '/mandates'
    const res = await api.get<{ status: string; data: InvestmentMandate[] }>(url)
    return res.data
  },

  async createMandate(payload: Partial<InvestmentMandate>): Promise<InvestmentMandate> {
    const res = await api.post<{ status: string; data: InvestmentMandate }>('/mandates', payload)
    return res.data
  },

  async getMandate(mandateId: string): Promise<InvestmentMandate> {
    const res = await api.get<{ status: string; data: InvestmentMandate }>(`/mandates/${mandateId}`)
    return res.data
  },

  async updateMandate(mandateId: string, payload: Partial<InvestmentMandate>): Promise<InvestmentMandate> {
    const res = await api.put<{ status: string; data: InvestmentMandate }>(`/mandates/${mandateId}`, payload)
    return res.data
  },

  async deleteMandate(mandateId: string): Promise<void> {
    await api.delete(`/mandates/${mandateId}`)
  },

  async assignCapital(
    mandateId: string,
    payload: {
      mandate_id: string
      resource_type: string
      asset_id?: string
      cash_account_id?: string
      assigned_quantity?: string | number
      assigned_amount?: string | number
      notes?: string
    }
  ): Promise<any> {
    const res = await api.post<{ status: string; data: any }>(`/mandates/${mandateId}/assignments`, payload)
    return res.data
  },

  async removeAssignment(assignmentId: string): Promise<void> {
    await api.delete(`/mandates/assignments/${assignmentId}`)
  },

  async transferCapital(payload: {
    from_mandate_id: string
    to_mandate_id: string
    resource_type: string
    asset_id?: string
    cash_account_id?: string
    quantity?: string | number
    amount?: string | number
  }): Promise<any> {
    const res = await api.post<{ status: string; data: any }>('/mandates/transfer-capital', payload)
    return res.data
  },

  async getFinancialIntelligenceSummary(): Promise<FinancialIntelligenceSummary> {
    const res = await api.get<{ status: string; data: FinancialIntelligenceSummary }>('/financial-intelligence/summary')
    return res.data
  },

  async resolveAssignmentReview(payload: {
    asset_id: string
    mandate_adjustments: Record<string, string | number>
  }): Promise<any> {
    const res = await api.post<{ status: string; data: any }>('/mandates/resolve-assignment-review', payload)
    return res.data
  },

  async getProfileSynthesis(): Promise<any> {
    const res = await api.get<{ status: string; data: any }>('/financial-intelligence/synthesis')
    return res.data
  },
}
