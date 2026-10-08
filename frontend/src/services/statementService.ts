import { api } from '@/services/api'
import type {
  InstallmentForecast,
  InstallmentPlan,
  InstallmentPlanStatus,
  LiabilityStatement,
  StatementReconciliation,
  StatementStatus,
  StatementTransaction,
  StatementTransactionType,
} from '@/types'


interface DataResponse<T> {
  status: string
  data: T
}

export interface StatementPayload {
  statement_period_start: string
  statement_period_end: string
  statement_date: string
  due_date: string
  currency: string
  previous_balance: string
  payments_total: string
  purchases_total: string
  fees_total: string
  interest_total: string
  refunds_total: string
  statement_balance: string
  minimum_payment: string
  remaining_installments_total: string
  status?: StatementStatus
  notes?: string | null
  source?: 'manual'
}

export type StatementUpdatePayload = Partial<StatementPayload>

export interface StatementTransactionPayload {
  transaction_date: string
  posting_date?: string | null
  description: string
  merchant_name?: string | null
  transaction_type: StatementTransactionType
  amount: string
  currency: string
  installment_plan_id?: string | null
  installment_number?: number | null
  installment_count?: number | null
  external_reference?: string | null
  notes?: string | null
}

export type StatementTransactionUpdatePayload = Partial<StatementTransactionPayload>

export interface InstallmentPlanPayload {
  description: string
  merchant_name?: string | null
  purchase_date: string
  currency: string
  original_amount: string
  installment_count: number
  monthly_installment_amount: string
  first_installment_date: string
  completed_installment_count: number
  status: InstallmentPlanStatus
  external_reference?: string | null
}

export type InstallmentPlanUpdatePayload = Partial<InstallmentPlanPayload>

export interface StatementPdfPreflight {
  filename: string
  size_bytes: number
  sha256: string
  is_pdf: true
  is_duplicate: boolean
  matched_statement_id: string | null
  status: 'ready' | 'duplicate_statement_file'
  analysis_available: false
}

export const STATEMENT_PDF_MAX_BYTES = 10 * 1024 * 1024


const data = <T>(response: DataResponse<T>) => response.data

export const statementService = {
  preflightPdf: (liabilityId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .postForm<DataResponse<StatementPdfPreflight>>(
        `/liabilities/${liabilityId}/statement-imports/preflight`,
        form,
      )
      .then(data)
  },

  list: (liabilityId: string) =>
    api
      .get<DataResponse<LiabilityStatement[]>>(
        `/liabilities/${liabilityId}/statements`,
      )
      .then(data),

  get: (statementId: string) =>
    api
      .get<DataResponse<LiabilityStatement>>(`/statements/${statementId}`)
      .then(data),

  create: (liabilityId: string, payload: StatementPayload) =>
    api
      .post<DataResponse<LiabilityStatement>>(
        `/liabilities/${liabilityId}/statements`,
        payload,
      )
      .then(data),

  update: (statementId: string, payload: StatementUpdatePayload) =>
    api
      .put<DataResponse<LiabilityStatement>>(
        `/statements/${statementId}`,
        payload,
      )
      .then(data),

  delete: (statementId: string) =>
    api.delete<unknown>(`/statements/${statementId}`),

  confirm: (statementId: string, applyToLiability: boolean) =>
    api
      .post<DataResponse<LiabilityStatement>>(
        `/statements/${statementId}/confirm`,
        { apply_to_liability: applyToLiability },
      )
      .then(data),

  createTransaction: (
    statementId: string,
    payload: StatementTransactionPayload,
  ) =>
    api
      .post<
        DataResponse<{
          transaction: StatementTransaction
          reconciliation: StatementReconciliation
        }>
      >(`/statements/${statementId}/transactions`, payload)
      .then(data),

  updateTransaction: (
    transactionId: string,
    payload: StatementTransactionUpdatePayload,
  ) =>
    api
      .put<
        DataResponse<{
          transaction: StatementTransaction
          reconciliation: StatementReconciliation
        }>
      >(`/statement-transactions/${transactionId}`, payload)
      .then(data),

  deleteTransaction: (transactionId: string) =>
    api.delete<unknown>(`/statement-transactions/${transactionId}`),

  listPlans: (liabilityId: string) =>
    api
      .get<DataResponse<InstallmentPlan[]>>(
        `/liabilities/${liabilityId}/installment-plans`,
      )
      .then(data),

  createPlan: (liabilityId: string, payload: InstallmentPlanPayload) =>
    api
      .post<DataResponse<InstallmentPlan>>(
        `/liabilities/${liabilityId}/installment-plans`,
        payload,
      )
      .then(data),

  updatePlan: (planId: string, payload: InstallmentPlanUpdatePayload) =>
    api
      .put<DataResponse<InstallmentPlan>>(`/installment-plans/${planId}`, payload)
      .then(data),

  cancelPlan: (planId: string) =>
    api
      .post<DataResponse<InstallmentPlan>>(`/installment-plans/${planId}/cancel`, {})
      .then(data),

  forecast: (liabilityId: string) =>
    api
      .get<DataResponse<InstallmentForecast>>(
        `/liabilities/${liabilityId}/installment-forecast`,
      )
      .then(data),
}
