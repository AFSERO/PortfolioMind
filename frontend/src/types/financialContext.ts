export type FinancialScope = 'INDIVIDUAL' | 'PERSONAL_SHARE_OF_HOUSEHOLD'

export type IncomeStability = 'PREDICTABLE' | 'VARIABLE' | 'AT_RISK' | 'TEMPORARY' | 'UNKNOWN'

export type GoalType =
  | 'RETIREMENT'
  | 'HOME_PURCHASE'
  | 'EDUCATION'
  | 'EMERGENCY_RESERVE'
  | 'WEALTH_GROWTH'
  | 'FINANCIAL_INDEPENDENCE'
  | 'CAPITAL_PRESERVATION'
  | 'INCOME_GENERATION'
  | 'BUSINESS_CAPITAL'
  | 'TRAVEL'
  | 'OTHER'

export type GoalMode = 'TARGET_AMOUNT' | 'TARGET_INCOME' | 'OPEN_ENDED'

export type GoalPriority = 'ESSENTIAL' | 'IMPORTANT' | 'ASPIRATIONAL'

export type GoalStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'ACHIEVED' | 'CANCELLED'

export type MandateType = 'RESERVE' | 'PRESERVATION' | 'INCOME' | 'GROWTH' | 'SPECULATIVE' | 'CUSTOM'

export type RiskCapacity = 'CONSTRAINED' | 'LOW' | 'MODERATE' | 'HIGH' | 'UNCONSTRAINED'

export type MandateStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'CLOSED'

export type ResourceAssignmentType = 'ASSET' | 'CASH_ACCOUNT'

export interface CapitalAssignment {
  id: string
  user_id: string
  mandate_id: string
  resource_type: ResourceAssignmentType
  asset_id?: string | null
  cash_account_id?: string | null
  assigned_quantity: string | number
  assigned_amount: string | number
  notes?: string | null
  current_market_value: string | number
  resource_symbol?: string | null
  resource_name?: string | null
  created_at: string
  updated_at: string
}

export interface InvestmentMandate {
  id: string
  user_id: string
  goal_id?: string | null
  name: string
  mandate_type: MandateType
  purpose?: string | null
  horizon_override?: string | null
  risk_capacity: RiskCapacity
  target_allocation: Record<string, number>
  concentration_limits: Record<string, any>
  policy_rules: Record<string, any>
  status: MandateStatus
  created_at: string
  updated_at: string
  assignments: CapitalAssignment[]
  total_assigned_value: string | number
}

export interface FinancialGoal {
  id: string
  user_id: string
  name: string
  goal_type: GoalType
  mode: GoalMode
  target_amount?: string | number | null
  target_currency: string
  target_date?: string | null
  horizon_band?: string | null
  priority: GoalPriority
  date_flexibility: string
  amount_flexibility: string
  status: GoalStatus
  notes?: string | null
  created_at: string
  updated_at: string
  mandates: InvestmentMandate[]
  current_funding: string | number
  funded_ratio?: number | null
  remaining_amount?: string | number | null
  months_remaining?: number | null
  time_remaining_text?: string | null
  required_monthly_contribution?: string | number | null
  projection_assumptions?: string | null
  status_assessment: string
}

export interface FinancialContext {
  id: string
  user_id: string
  financial_scope: FinancialScope
  spending_currencies: string[]
  planning_currency: string
  monthly_net_income?: string | number | null
  monthly_essential_expenses?: string | number | null
  monthly_discretionary_expenses?: string | number | null
  income_stability: IncomeStability
  dependents_count?: number | null
  reserve_self_report?: string | null
  user_surplus_estimate?: string | number | null
  last_confirmed_at?: string | null
  created_at: string
  updated_at: string
}

export interface FinancialIntelligenceIssue {
  code: string
  message: string
  severity: 'WARNING' | 'CRITICAL' | 'INFO'
}

export interface FinancialIntelligenceSummary {
  user_id: string
  net_worth?: string | number | null
  liquid_net_worth?: string | number | null
  total_assets_value?: string | number | null
  total_cash_value?: string | number | null
  total_liabilities?: string | number | null
  monthly_net_income?: string | number | null
  monthly_essential_expenses?: string | number | null
  monthly_discretionary_expenses?: string | number | null
  monthly_surplus?: string | number | null
  savings_rate_pct?: string | number | null
  emergency_coverage_months?: string | number | null
  debt_to_income_pct?: string | number | null
  speculative_exposure_pct?: string | number | null
  unassigned_capital_value?: string | number | null
  currency: string
  issues: FinancialIntelligenceIssue[]
}

export interface UnassignedAsset {
  asset_id: string
  symbol: string
  name: string
  total_quantity: string
  assigned_quantity: string
  unassigned_quantity: string
  over_assigned_amount?: string | number
  reconciliation_status?: string
  currency: string
}

export interface UnassignedCashAccount {
  cash_account_id: string
  currency: string
  total_balance: string
  assigned_amount: string
  unassigned_amount: string
  over_assigned_amount?: string | number
  reconciliation_status?: string
}

export interface UnassignedResourcesResponse {
  assets: UnassignedAsset[]
  cash_accounts: UnassignedCashAccount[]
}

export interface FinancialProfileSynthesis {
  generated_at: string
  freshness_status: 'CURRENT' | 'REVIEW_DUE' | 'STALE' | 'UNKNOWN'
  is_authoritative: boolean
  disclaimer: string
  investor_profile_summary: Record<string, any>
  cash_flow_and_surplus_summary: Record<string, any>
  emergency_reserve_adequacy: Record<string, any>
  goal_architecture_summary: Record<string, any>
  debt_posture_summary: Record<string, any>
  mandate_alignment_summary: Record<string, any>
  open_questions_and_gaps: string[]
  source_traceability: Record<string, any>
  confidence_limitations?: string[]
}

