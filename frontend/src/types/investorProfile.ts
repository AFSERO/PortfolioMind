export interface QuestionOption {
  code: string
  label: string
  description?: string
  exclusive?: boolean
}

export interface QuestionDefinition {
  id: string
  section: string
  layer: string
  priority: string
  text: string
  helper_text?: string
  question_type: string
  options: QuestionOption[]
  has_other?: boolean
  dependencies?: string[]
  affects_dimensions?: string[]
}

export interface SectionDefinition {
  id: string
  title: string
  description: string
  question_ids: string[]
}

export interface AnswerResponse {
  id: string
  question_id: string
  item_id?: string
  knowledge_state: string
  selected_options: string[]
  numeric_inputs: Record<string, any>
  raw_text?: string
  locale: string
  answered_at: string
}

export interface AssessmentState {
  id: string
  user_id: string
  status: string
  questionnaire_version: string
  resume_question_id?: string
  answers: AnswerResponse[]
  created_at: string
  updated_at: string
}

export interface ProfileIssue {
  id: string
  rule_id: string
  field_paths: string[]
  severity: string
  state: string
  explanation: string
}

export interface ProfileCompleteness {
  overall_pct: number
  domains: Record<string, number>
  missing_field_paths: string[]
}

export interface CapabilityReadiness {
  risk_analysis: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  capacity_analysis: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  target_allocation_analysis: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  portfolio_fit: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  liquidity_analysis: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  copilot_support: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
  research_relevance: 'READY' | 'PARTIAL' | 'LIMITED' | 'UNAVAILABLE'
}

export interface InvestorProfileDraft {
  id: string
  user_id: string
  assessment_id?: string
  base_version_id?: string
  goals: {
    items: Array<{
      id: string
      kind: string
      horizon?: string
      flexibility?: string
      loss_consequence?: string
      target_date?: string
    }>
    withdrawals: Array<{
      id: string
      timing_band?: string
      size?: Record<string, any>
      coverage?: string
    }>
    withdrawal_pattern?: string
    reserve_months_band?: string
    cashflow?: string
    income_reliability?: string
    obligation_pressure?: string
    spending_currencies?: string[]
  }
  risk: {
    drawdown_comfort?: string
    custom_drawdown_pct?: number
    stress_response?: string
    tolerance_summary: string
    capacity_by_goal: Array<{
      goal_id: string
      status: string
      reason_codes: string[]
    }>
    liquidity_summary: string
    resilience_summary: string
  }
  policy: {
    restriction_topics: string[]
    constraints: Array<Record<string, any>>
    allocation_mode?: string
    allocations: Array<Record<string, any>>
  }
  preferences: {
    experience: Array<{ family: string; level: string }>
    involvement?: string
    styles: string[]
    explanation_depth?: string
    language?: string
  }
  issues: ProfileIssue[]
  completeness: ProfileCompleteness
  readiness: CapabilityReadiness
  created_at: string
  updated_at: string
}

export interface InvestorProfileData {
  id: string
  user_id: string
  version_number?: number
  active_version_id?: string
  completeness_overall_pct: number
  analysis_readiness: CapabilityReadiness
  goals: Record<string, any>
  risk: Record<string, any>
  policy: Record<string, any>
  preferences: Record<string, any>
  issues: ProfileIssue[]
  confirmed_at?: string
  updated_at: string
}

export interface InvestorProfileVersionSummary {
  id: string
  version_number: number
  change_reason: string
  change_source: string
  confirmed_at: string
}
