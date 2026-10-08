export interface ContextProvenanceItem {
  source_type: string
  source_id?: string | null
  title: string
  updated_at?: string | null
  freshness?: string | null
}

export interface CopilotPageContext {
  page_type?: string
  instrument_id?: string
  asset_id?: string
}

export interface SemanticFinancialValue {
  value: number | string
  currency: string
  meaning: string
  source: string
  freshness?: string | null
  formatted?: string | null
  notes?: string | null
}

export interface PendingActionDraft {
  draft_id: string
  action_type: string
  acquisition_type: string
  symbol?: string | null
  instrument_name?: string | null
  asset_id?: string | null
  instrument_id?: string | null
  quantity?: number | null
  unit_price?: number | null
  currency?: string | null
  total_amount?: number | null
  affects_cash: boolean
  cash_outflow: number
  transaction_date?: string | null
  notes?: string | null
  is_complete: boolean
  missing_fields: string[]
}

export interface ActionProposal {
  id: string
  user_id: string
  conversation_id?: string | null
  action_type: string
  permission_level: string
  status: 'PENDING' | 'DRAFT' | 'NEEDS_INPUT' | 'READY_FOR_CONFIRMATION' | 'CONFIRMED' | 'EXECUTED' | 'APPLIED' | 'CANCELLED' | 'EXPIRED' | 'STALE' | 'FAILED' | string
  parameters: Record<string, any>
  expected_impact?: Record<string, any> | null
  current_state_snapshot?: Record<string, any> | null
  human_readable_summary: string
  warnings: string[]
  idempotency_key: string
  created_at: string
  expires_at?: string | null
  confirmed_at?: string | null
  applied_at?: string | null
  execution_result?: Record<string, any> | null
}

export type ImportSourceType = 'NATURAL_LANGUAGE' | 'SCREENSHOT' | 'CSV' | 'MANUAL';
export type ImportBatchStatus = 'DRAFT' | 'PARSED' | 'READY_FOR_CONFIRMATION' | 'CONFIRMED' | 'APPLIED' | 'CANCELLED' | 'FAILED';
export type ImportItemAction = 'CREATE_OPENING_POSITION' | 'UPDATE_EXISTING_OPENING_POSITION' | 'ADD_TO_EXISTING_POSITION' | 'SKIP' | 'NEEDS_REVIEW' | 'AMBIGUOUS' | 'INVALID';
export type ActionResolutionType = 'REPLACE_OPENING_STATE' | 'ADD_TO_EXISTING' | 'SKIP';

export interface PortfolioImportItem {
  id: string;
  batch_id: string;
  raw_input: string;
  resolved_instrument_id?: string | null;
  asset_type: string;
  symbol?: string | null;
  name: string;
  quantity?: number | null;
  market_value?: number | null;
  average_cost?: number | null;
  total_cost?: number | null;
  currency?: string | null;
  as_of_date?: string | null;
  existing_asset_id?: string | null;
  existing_quantity?: number | null;
  intended_action: ImportItemAction;
  action_resolution?: ActionResolutionType | null;
  warnings: string[];
  missing_fields: string[];
  resulting_asset_id?: string | null;
  resulting_opening_position_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PortfolioImportBatch {
  id: string;
  user_id: string;
  conversation_id?: string | null;
  proposal_id?: string | null;
  source_type: ImportSourceType;
  source_reference?: string | null;
  status: ImportBatchStatus;
  raw_content_preview?: string | null;
  warnings: string[];
  errors: string[];
  idempotency_key: string;
  created_at: string;
  parsed_at?: string | null;
  confirmed_at?: string | null;
  applied_at?: string | null;
  items: PortfolioImportItem[];
  ready_count: number;
  needs_review_count: number;
  ambiguous_count: number;
}

export interface CopilotStructuredResponse {
  response_type: 'ANSWER' | 'NEEDS_INPUT' | 'ACTION_INTENT' | 'PROPOSAL' | string
  answer?: string | null
  question?: string | null
  intent: string
  execution_mode?: 'READ_ONLY' | 'AUTO_APPLY' | 'PROPOSE' | 'NEEDS_INPUT' | string | null
  missing_fields?: string[] | null
  action?: Record<string, any> | null
  action_draft?: PendingActionDraft | null
  proposal?: ActionProposal | null
  import_batch?: PortfolioImportBatch | null
  financial_values?: SemanticFinancialValue[] | null
  context_used: ContextProvenanceItem[]
}

export interface ConfirmProposalResponse {
  status: string
  data: {
    proposal: ActionProposal | null
    execution_result: Record<string, any>
  }
}

export interface CancelProposalResponse {
  status: string
  data: ActionProposal
}

export interface CopilotExternalSource {
  title: string
  source: string
  url?: string
  published_at?: string
  snippet?: string
}

export interface CopilotMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  raw_content: string
  intent?: string | null
  structured_metadata?: Record<string, any> | null
  external_sources?: CopilotExternalSource[]
  created_at: string
}

export interface CopilotConversation {
  id: string
  user_id: string
  title?: string | null
  created_at: string
  updated_at: string
  messages?: CopilotMessage[]
}

export interface SendMessageResponse {
  status: string
  data: {
    message: CopilotMessage
    structured_response: CopilotStructuredResponse
    context_used: ContextProvenanceItem[]
  }
}

export type CopilotV2ProgressEventType =
  | 'STARTED'
  | 'TOOL_RUNNING'
  | 'ESCALATING'
  | 'REASONING'
  | 'FINAL'
  | 'FAILED'

export interface CopilotV2ProgressEvent {
  type: CopilotV2ProgressEventType
  message: string
  tool?: string
  target_profile?: string
  profile?: string
  effort?: string
}

export interface CopilotV2Trace {
  starting_profile: string
  final_profile: string
  reasoning_effort: string
  total_latency_ms: number
  codex_invocation_count: number
  tools_called: string[]
  tool_durations: Record<string, number>
  tool_results_reused: number
  escalation_occurred: boolean
  failure_category?: string | null
  conversation_id?: string | null
  codex_session_id?: string | null
  session_mode: 'NEW' | 'RESUMED' | 'RECOVERED' | string
  profile_sequence: string[]
  reasoning_effort_sequence: string[]
  session_resume_failed: boolean
  session_recovery_occurred: boolean
  time_to_first_progress_event_ms?: number | null
  external_search_used?: boolean
  external_tools_called?: string[]
  search_queries_count?: number
  search_results_count?: number
  pages_fetched?: number
  external_tool_latency_ms?: number
  source_count_used_in_final_answer?: number
  simulation_used?: boolean
  simulation_type?: string | null
  simulation_tool_latency_ms?: number
  simulation_validation_status?: string | null
}

export interface SimulationInstrumentInfo {
  symbol: string
  name: string
  instrument_id?: string | null
  asset_id?: string | null
  asset_type: string
  currency: string
  is_owned: boolean
}

export interface SimulationPositionSnapshot {
  quantity: number
  position_value: number
  position_value_base: number
  weight_pct: number
}

export interface SimulationCashSnapshot {
  balance: number
  currency: string
  total_cash_base: number
  cash_weight_pct: number
  cash_account_exists: boolean
}

export interface SimulationPortfolioSnapshot {
  total_value_base: number
  total_invested_assets_base: number
  base_currency: string
  target_position: SimulationPositionSnapshot
  cash: SimulationCashSnapshot
}

export interface SimulationTransactionSpec {
  transaction_type: 'SELL' | 'BUY'
  quantity: number
  gross_value: number
  gross_value_base: number
  fee: number
  net_cash_delta: number
  net_cash_delta_base: number
  currency: string
  is_affordable: boolean
  cash_shortfall: number
}

export interface SimulationAssumptions {
  price?: number | null
  price_currency?: string | null
  price_source: 'EXPLICIT_SCENARIO_PRICE' | 'CURRENT_REFERENCE_PRICE' | 'UNKNOWN'
  price_timestamp?: string | null
  fee: number
  fee_currency?: string | null
  affects_cash: boolean
  notes?: string | null
}

export interface SimulationValidation {
  is_valid: boolean
  reason?: string | null
  message?: string | null
}

export interface SimulationAllocationItem {
  asset_type?: string
  symbol?: string
  name?: string
  value: number
  percentage: number
}

export interface SimulationAllocationSnapshot {
  by_type: SimulationAllocationItem[]
  by_asset: SimulationAllocationItem[]
}

export interface SimulationResultData {
  status: 'success' | 'warning' | 'error' | string
  simulation_type: 'SELL' | 'BUY'
  instrument: SimulationInstrumentInfo
  assumptions: SimulationAssumptions
  validation: SimulationValidation
  before: SimulationPortfolioSnapshot
  transaction: SimulationTransactionSpec
  after: SimulationPortfolioSnapshot
  allocation_before: SimulationAllocationSnapshot
  allocation_after: SimulationAllocationSnapshot
  warnings: string[]
}


