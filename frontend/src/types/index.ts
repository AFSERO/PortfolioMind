export type AssetType =
  | 'STOCK'
  | 'FOREX'
  | 'PRECIOUS_METALS'
  | 'CRYPTO'
  | 'FUND'
  | 'REAL_ESTATE'
  | 'CUSTOM'

export type TransactionType = 'BUY' | 'SELL'

export type LiabilityType =
  | 'credit_card'
  | 'personal_loan'
  | 'mortgage'
  | 'student_loan'
  | 'other'

export interface User {
  id: string
  email: string
  display_name?: string
  base_currency: string
  created_at: string
}

export interface Instrument {
  id: string
  symbol?: string | null
  name: string
  asset_type: AssetType
  exchange?: string | null
  currency?: string | null
  country?: string | null
  isin?: string | null
  provider?: string | null
  provider_id?: string | null
  intelligence_state?: InstrumentIntelligenceState | null
  created_at: string
  updated_at: string
}

export interface Asset {
  id: string
  user_id: string
  instrument_id?: string | null
  instrument?: Instrument | null
  asset_type: AssetType
  symbol?: string | null
  name: string
  current_price?: number | null
  current_price_currency?: string | null
  is_manual_price: boolean
  notes?: string | null
  created_at: string
  updated_at: string

  // Computed from transactions
  total_quantity: number
  avg_cost: number | null
  avg_cost_currency: string | null
  total_cost: number | null
  realized_pl: number | null
  has_mixed_currencies: boolean
}

export interface Transaction {
  id: string
  asset_id: string
  transaction_type: TransactionType
  quantity: number
  price_per_unit: number
  total_amount: number
  transaction_currency: string
  transaction_date: string  // YYYY-MM-DD
  notes?: string | null
  affects_cash: boolean
  created_at: string
  updated_at: string
}

export interface PriceHistory {
  id: string
  asset_id: string
  price: number
  currency: string
  recorded_at: string
}

export interface PortfolioSnapshot {
  id: string
  user_id: string
  total_value_try: number
  total_value_usd: number
  snapshot_date: string
}

export interface Liability {
  id: string
  user_id: string
  name: string
  liability_type: LiabilityType
  currency: string
  current_balance: number
  original_balance: number | null
  interest_rate: number | null
  minimum_payment: number | null
  due_date: string | null
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type StatementStatus =
  | 'draft'
  | 'confirmed'
  | 'paid'
  | 'partially_paid'
  | 'overdue'

export type StatementTransactionType =
  | 'purchase'
  | 'payment'
  | 'refund'
  | 'fee'
  | 'interest'
  | 'cash_advance'
  | 'installment'
  | 'other'

export type InstallmentPlanStatus = 'active' | 'completed' | 'cancelled'

export interface StatementReconciliation {
  calculated_balance: number
  reported_balance: number
  reconciliation_difference: number
  is_reconciled: boolean
  reconciliation_tolerance: number
  calculation_source: 'summary' | 'transactions'
  summary_calculated_balance: number
  summary_difference: number
  transaction_calculated_balance: number | null
  transaction_difference: number | null
  transaction_count: number
}

export interface StatementTransaction {
  id: string
  user_id: string
  statement_id: string
  transaction_date: string
  posting_date: string | null
  description: string
  merchant_name: string | null
  transaction_type: StatementTransactionType
  amount: number
  currency: string
  installment_plan_id: string | null
  installment_number: number | null
  installment_count: number | null
  external_reference: string | null
  source_line_hash: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface LiabilityStatement extends StatementReconciliation {
  id: string
  user_id: string
  liability_id: string
  statement_period_start: string
  statement_period_end: string
  statement_date: string
  due_date: string
  currency: string
  previous_balance: number
  payments_total: number
  purchases_total: number
  fees_total: number
  interest_total: number
  refunds_total: number
  statement_balance: number
  minimum_payment: number
  remaining_installments_total: number
  status: StatementStatus
  notes: string | null
  source: 'manual' | 'pdf_import' | 'csv_import'
  source_file_hash: string | null
  confirmed_at: string | null
  applied_to_liability_at: string | null
  applied_balance: number | null
  created_at: string
  updated_at: string
  transactions?: StatementTransaction[] | null
}

export interface InstallmentPlan {
  id: string
  user_id: string
  liability_id: string
  description: string
  merchant_name: string | null
  purchase_date: string
  currency: string
  original_amount: number
  installment_count: number
  monthly_installment_amount: number
  first_installment_date: string
  completed_installment_count: number
  status: InstallmentPlanStatus
  external_reference: string | null
  created_at: string
  updated_at: string
  remaining_installment_count: number
  remaining_amount: number
  next_installment_date: string | null
  estimated_completion_date: string
}

export interface InstallmentForecast {
  currency: string
  as_of: string
  next_month_total: number
  next_three_months: Array<{ month: string; amount: number }>
  remaining_total: number
  nearest_installment_date: string | null
  active_plan_count: number
}

export interface ApiResponse<T> {
  status: 'success' | 'error'
  data?: T
  message?: string
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface PerformerInfo {
  asset_id: string
  name: string
  symbol: string | null
  pl: number
  pl_pct: number
}

export interface TypeSummary {
  asset_type: string
  total_value: number
  total_cost: number | null
  pl: number
  pl_pct: number
  count: number
}

export interface DashboardSummary {
  total_value: number
  total_assets: number
  total_liabilities: number
  net_worth: number
  total_cost: number | null
  total_pl: number | null
  total_pl_pct: number | null
  unrealized_pl: number | null
  realized_pl: number | null
  total_cash: number
  asset_count: number
  liability_count: number
  best_performer: PerformerInfo | null
  worst_performer: PerformerInfo | null
  by_type_summary: TypeSummary[]
  base_currency?: string
  exchange_rates?: ExchangeRateMetadata
}

export interface ExchangeRateMetadata {
  status: 'complete' | 'stale'
  rates: Array<{ pair: string; fetched_at: string | null; stale: boolean }>
}

export interface TypeAllocation {
  asset_type: string
  value: number
  percentage: number
}

export interface AssetAllocation {
  asset_id: string
  name: string
  symbol: string | null
  asset_type: string
  value: number
  percentage: number
}

export interface AllocationData {
  total_value: number
  by_type: TypeAllocation[]
  by_asset: AssetAllocation[]
  base_currency?: string
  exchange_rates?: ExchangeRateMetadata
}

export interface TimelinePoint {
  date: string
  total_value_try: number
  total_value_usd: number
  total_assets_try: number | null
  total_assets_usd: number | null
  total_liabilities_try: number | null
  total_liabilities_usd: number | null
  net_worth_try: number | null
  net_worth_usd: number | null
  value_semantics: 'gross_assets' | 'net_worth'
}

// ── Cash ───────────────────────────────────────────────────────────────────

export type CashMovementType =
  | 'DEPOSIT'
  | 'WITHDRAW'
  | 'TRANSFER_IN'
  | 'TRANSFER_OUT'
  | 'BUY'
  | 'SELL'
  | 'ADJUSTMENT'

export interface CashAccount {
  id: string
  currency: string
  balance: number
  created_at: string
  updated_at: string
}

export interface CashMovement {
  id: string
  cash_account_id: string
  movement_type: CashMovementType
  amount: number
  currency: string
  related_transaction_id: string | null
  notes: string | null
  created_at: string
}

// ── Investment Intelligence ────────────────────────────────────────────────

export type ThesisStatus = 'STRONGER' | 'UNCHANGED' | 'WEAKER' | 'INVALIDATED'
export type ValuationStatus = 'ATTRACTIVE' | 'FAIR' | 'EXPENSIVE' | 'UNKNOWN' | 'N_A'
export type TechnicalStatus =
  | 'ON_TRACK'
  | 'NEUTRAL'
  | 'DEVIATED'
  | 'PULLBACK'
  | 'EXTENDED'
  | 'BREAKDOWN'
  | 'UNKNOWN'
  | 'N_A'
  | 'REVIEW_REQUIRED'
export type Recommendation = 'ADD' | 'HOLD' | 'REDUCE' | 'SELL' | 'REVIEW_REQUIRED'
export type ExecutionStatus = 'AVAILABLE' | 'RESTRICTED' | 'BLOCKED' | 'UNKNOWN'
export type FundQuality = 'STRONG' | 'ACCEPTABLE' | 'WEAK' | 'POOR' | 'UNKNOWN'
export type ProtocolRunStatus = 'COMPLETED' | 'FAILED' | 'IN_PROGRESS' | 'PARTIAL'

export interface InstrumentIntelligenceState {
  id: string
  instrument_id: string
  thesis_status?: ThesisStatus | null
  valuation_status?: ValuationStatus | null
  technical_status?: TechnicalStatus | null
  recommendation?: Recommendation | null
  execution_status?: ExecutionStatus | null
  recovery_value_confidence?: string | null
  execution_confidence?: string | null
  data_quality_score?: number | null
  last_review_at?: string | null
  last_monitoring_at?: string | null
  next_review_at?: string | null
  human_brief?: string | null
  confidence?: string | null
  confidence_score?: number | null
  confidence_level?: 'HIGH' | 'MEDIUM' | 'LOW' | null
  primary_reason?: string | null
  supporting_reasons?: string[] | null
  key_risks?: string[] | null
  what_would_change_my_view?: string | null
  evidence_gaps?: string[] | null
  review_required_reason?: string | null
  assessment_type?: string | null
  asset_class_assessment?: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface IntelligenceReview {
  id: string
  instrument_id: string
  protocol: string
  run_type?: string | null
  status: ProtocolRunStatus
  machine_record?: Record<string, any> | null
  human_brief?: string | null
  confidence?: string | null
  research_path?: string | null
  source_run_id?: string | null
  created_at: string
}

export interface TechnicalPlan {
  id: string
  instrument_id: string
  reference_at: string
  reference_price?: number | null
  trend_expectation?: string | null
  entry_zones?: any[] | null
  support_zones?: any[] | null
  resistance_zones?: any[] | null
  review_or_invalidation_zones?: any[] | null
  profit_taking_or_reassessment_zones?: any[] | null
  notes?: string | null
  active: boolean
  created_at: string
  updated_at: string
}

// ── Decision Log ───────────────────────────────────────────────────────────

export type DecisionEventType =
  | 'POSITION_OPENED'
  | 'POSITION_ADDED'
  | 'POSITION_REDUCED'
  | 'POSITION_CLOSED'
  | 'BUY'
  | 'SELL'
  | 'THESIS_REVIEWED'
  | 'THESIS_CHANGED'
  | 'VALUATION_CHANGED'
  | 'TECHNICAL_PLAN_CHANGED'
  | 'RECOMMENDATION_CHANGED'
  | 'INTELLIGENCE_REVIEW_COMPLETED'
  | 'MANUAL_DECISION_NOTE'

export interface DecisionLogEntry {
  id: string
  user_id: string
  instrument_id?: string | null
  asset_id?: string | null
  event_type: DecisionEventType
  title: string
  summary: string
  user_rationale?: string | null
  confidence?: string | null
  expectation?: string | null
  related_review_id?: string | null
  related_transaction_id?: string | null
  metadata?: Record<string, any> | null
  occurred_at: string
  created_at: string
  updated_at: string
  instrument_symbol?: string | null
  instrument_name?: string | null
  asset_name?: string | null
}

export interface DecisionLogCreateRequest {
  instrument_id?: string
  asset_id?: string
  event_type?: DecisionEventType
  title: string
  summary: string
  user_rationale?: string
  confidence?: string
  expectation?: string
  metadata?: Record<string, any>
  occurred_at?: string
}

export interface DecisionLogUpdateRationaleRequest {
  user_rationale: string
  confidence?: string
  expectation?: string
}

// ── Intelligence Briefing ──────────────────────────────────────────────────

export type BriefingImpact = 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'MIXED'
export type BriefingMateriality = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type BriefingTimeHorizon = 'SHORT' | 'MEDIUM' | 'LONG'
export type BriefingThesisImpact = 'STRONGER' | 'UNCHANGED' | 'WEAKER' | 'INVALIDATED' | 'NOT_EVALUATED'
export type BriefingCategory = 'EARNINGS' | 'REGULATORY' | 'MACRO' | 'OPERATIONAL' | 'COMPETITIVE' | 'GENERAL'

export interface BriefingItem {
  id: string
  briefing_run_id: string
  user_id: string
  instrument_id: string
  headline: string
  summary: string
  why_it_matters: string
  impact: BriefingImpact
  materiality: BriefingMateriality
  time_horizon: BriefingTimeHorizon
  thesis_impact: BriefingThesisImpact
  review_required: boolean
  category: BriefingCategory
  source_metadata?: {
    source?: string
    url?: string
    source_quality?: string
    reasoning_source?: 'CODEX' | 'CODEX_CACHED' | 'DETERMINISTIC' | 'DETERMINISTIC_FALLBACK' | string
    reasoning_confidence?: string
    recommended_review?: string
    reasoning_generated_at?: string
    reasoning_fallback_reason?: string
    triggered_review_id?: string
    review_status?: 'READY' | 'RUNNING' | 'COMPLETED' | 'FAILED'
    triggered_protocol?: string
    triggered_at?: string
    review_summary?: {
      protocol?: string
      thesis_status?: string
      valuation_status?: string
      technical_status?: string
      recommendation?: string
      confidence?: string
      human_brief?: string
      state_updated?: boolean
    }
    review_error?: string
  } | null
  is_portfolio: boolean
  published_at?: string | null
  created_at: string
  instrument_symbol?: string | null
  instrument_name?: string | null
  attention_state?: 'OPEN' | 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' | 'DECISION_REQUIRED' | 'RESOLVED' | 'NONE'
}

export interface BriefingReviewResponse {
  status: 'READY' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  review_id?: string | null
  protocol?: string | null
  summary?: {
    protocol?: string
    thesis_status?: string
    valuation_status?: string
    technical_status?: string
    recommendation?: string
    confidence?: string
    human_brief?: string
    state_updated?: boolean
  } | null
  reused?: boolean
  error?: string | null
}

export interface BriefingRun {
  id: string
  user_id: string
  generated_at: string
  scope: string
  status: string
  trigger_type?: 'MANUAL' | 'SCHEDULED'
  items_found: number
  items_shown: number
  items_filtered: number
  created_at: string
  items: BriefingItem[]
}

export interface BriefingStats {
  attention_count: number
  items_shown: number
  items_filtered: number
  last_generated_at?: string | null
}

// ── Watchlist & Opportunity Automation ──────────────────────────────────────

export type ResearchStage =
  | 'DISCOVERED'
  | 'SCREENED'
  | 'RESEARCHING'
  | 'VALUED'
  | 'READY'
  | 'WAITING_FOR_PRICE'
  | 'OWNED'
  | 'REJECTED'

export type WatchlistPriority = 'LOW' | 'MEDIUM' | 'HIGH'

export type OpportunityStatus =
  | 'NO_CHANGE'
  | 'WATCH'
  | 'RESEARCH_SOON'
  | 'RESEARCH_NOW'

export type OpportunityDriver =
  | 'VALUATION'
  | 'FUNDAMENTAL'
  | 'CATALYST'
  | 'PRICE_MOVE'
  | 'RESEARCH_STALENESS'
  | 'OTHER'

export type ValuationSignal = 'ATTRACTIVE' | 'FAIR' | 'EXPENSIVE' | 'UNKNOWN'

export type ResearchFreshness = 'FRESH' | 'REVIEW' | 'STALE' | 'UNKNOWN'

export type SuggestedNextStep =
  | 'NONE'
  | 'SCREENING'
  | 'DEEP_RESEARCH'
  | 'VALUATION_UPDATE'
  | 'THESIS_REVIEW'
  | 'PRICE_REVIEW'

export type OpportunityConfidence = 'LOW' | 'MEDIUM' | 'HIGH'

export interface OpportunityAssessment {
  id: string
  instrument_id: string
  status: OpportunityStatus
  reason: string
  primary_driver: OpportunityDriver
  valuation_signal: ValuationSignal
  research_freshness: ResearchFreshness
  suggested_next_step: SuggestedNextStep
  confidence: OpportunityConfidence
  source_references?: Record<string, any> | null
  assessment_at: string
  created_at: string
}

export interface WatchlistItem {
  id: string
  instrument_id: string
  research_stage: ResearchStage
  priority: WatchlistPriority
  why_interesting?: string | null
  target_entry_min?: number | null
  target_entry_max?: number | null
  key_catalyst?: string | null
  key_risk?: string | null
  next_expected_event?: string | null
  notes?: string | null
  created_at: string
  updated_at: string
  instrument?: Instrument | null
  current_price?: number | null
  current_price_currency?: string | null
  opportunity?: OpportunityAssessment | null
}

export interface ResearchQueueItem {
  instrument_id: string
  symbol?: string | null
  name: string
  asset_type: string
  exchange?: string | null
  research_stage: ResearchStage
  priority: WatchlistPriority
  opportunity_status: OpportunityStatus
  primary_driver: OpportunityDriver
  suggested_next_step: SuggestedNextStep
  reason: string
  confidence: OpportunityConfidence
  current_price?: number | null
  current_price_currency?: string | null
  target_entry_min?: number | null
  target_entry_max?: number | null
  research_freshness: ResearchFreshness
  valuation_signal: ValuationSignal
  last_review_at?: string | null
  assessment_at: string
}

export interface ResearchQueueResponse {
  research_now: ResearchQueueItem[]
  research_soon: ResearchQueueItem[]
  waiting: ResearchQueueItem[]
  no_action: ResearchQueueItem[]
  stage_counts: Record<string, number>
  total_candidates: number
}

// Market-Wide Discovery Types
export type DiscoveryUniverse = 'US_LARGE_CAP' | 'US_TECH_GROWTH' | 'BIST_LIQUID' | 'CUSTOM'
export type DiscoveryStatus = 'HIGH_PRIORITY_SCREEN' | 'SCREEN' | 'WATCH' | 'IGNORE'
export type DiscoveryCandidateState = 'SURFACED' | 'WATCHLISTED' | 'DISMISSED' | 'SCREENED'
export type DiscoverySuggestedNextStep = 'NONE' | 'ADD_TO_WATCHLIST' | 'PRELIMINARY_SCREENING'
export type DiscoveryConfidence = 'LOW' | 'MEDIUM' | 'HIGH'
export type DiscoveryRunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface DiscoverySignal {
  type: string
  label: string
  detail: string
  data?: Record<string, any>
}

export interface DiscoveryCandidate {
  id: string
  run_id: string
  instrument_id: string
  symbol: string
  name: string
  status: DiscoveryStatus
  candidate_state: DiscoveryCandidateState
  primary_reason: string
  signals: DiscoverySignal[]
  key_question?: string | null
  key_risk?: string | null
  suggested_next_step: DiscoverySuggestedNextStep
  confidence: DiscoveryConfidence
  score_band?: string | null
  current_price?: number | null
  current_price_currency?: string | null
  market_data_snapshot?: Record<string, any>
  source_metadata?: Record<string, any>
  created_at: string
}

export interface DiscoveryRun {
  id: string
  universe: string
  trigger_type: string
  status: DiscoveryRunStatus
  instruments_scanned: number
  candidates_filtered: number
  candidates_reasoned: number
  candidates_surfaced: number
  started_at: string
  completed_at?: string | null
  diagnostics?: Record<string, any>
  candidates: DiscoveryCandidate[]
}


