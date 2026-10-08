import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StatementDetailPage from './StatementDetailPage'
import type { InstallmentForecast, LiabilityStatement, StatementTransaction } from '@/types'


const transaction: StatementTransaction = { id: 'tx-1', user_id: 'user-1', statement_id: 'statement-1', transaction_date: '2026-07-01', posting_date: null, description: 'Market', merchant_name: null, transaction_type: 'purchase', amount: 2000, currency: 'TRY', installment_plan_id: null, installment_number: null, installment_count: null, external_reference: null, source_line_hash: null, notes: null, created_at: '', updated_at: '' }
const baseStatement: LiabilityStatement = { id: 'statement-1', user_id: 'user-1', liability_id: 'card-1', statement_period_start: '2026-06-25', statement_period_end: '2026-07-24', statement_date: '2026-07-24', due_date: '2026-08-12', currency: 'TRY', previous_balance: 0, payments_total: 0, purchases_total: 2000, fees_total: 0, interest_total: 0, refunds_total: 0, statement_balance: 2000, minimum_payment: 400, remaining_installments_total: 6000, status: 'draft', notes: null, source: 'manual', source_file_hash: null, confirmed_at: null, applied_to_liability_at: null, applied_balance: null, created_at: '', updated_at: '', calculated_balance: 2000, reported_balance: 2000, reconciliation_difference: 0, is_reconciled: true, reconciliation_tolerance: 0.01, calculation_source: 'transactions', summary_calculated_balance: 2000, summary_difference: 0, transaction_calculated_balance: 2000, transaction_difference: 0, transaction_count: 1, transactions: [transaction] }
const forecast: InstallmentForecast = { currency: 'TRY', as_of: '2026-08-06', next_month_total: 1500, next_three_months: [], remaining_total: 6000, nearest_installment_date: '2026-08-24', active_plan_count: 1 }

const { hookState, serviceMocks } = vi.hoisted(() => ({
  hookState: { statement: null as LiabilityStatement | null, plans: [], forecast: null as InstallmentForecast | null, isLoading: false, error: null as string | null, refetch: vi.fn() },
  serviceMocks: { confirm: vi.fn(), deleteTransaction: vi.fn(), createTransaction: vi.fn(), updateTransaction: vi.fn() },
}))

vi.mock('@/hooks/useStatements', () => ({ useStatementDetail: () => hookState }))
vi.mock('@/services/statementService', () => ({ statementService: serviceMocks }))
vi.mock('@/components/layout/AppShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

function renderPage() {
  return render(<MemoryRouter initialEntries={['/liabilities/card-1/statements/statement-1']}><Routes><Route path="/liabilities/:liabilityId/statements/:statementId" element={<StatementDetailPage />} /></Routes></MemoryRouter>)
}

describe('StatementDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks(); hookState.statement = { ...baseStatement, transactions: [transaction] }; hookState.plans = []; hookState.forecast = forecast; hookState.isLoading = false; hookState.error = null; hookState.refetch.mockResolvedValue(undefined); serviceMocks.confirm.mockResolvedValue(baseStatement); serviceMocks.deleteTransaction.mockResolvedValue(undefined)
  })

  it('shows a reconciliation difference warning', () => {
    hookState.statement = { ...baseStatement, is_reconciled: false, reconciliation_difference: 25, transactions: [transaction] }
    renderPage()
    expect(screen.getByText('Reconciliation required')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  })

  it('sends the apply-to-liability boolean and refreshes after confirmation', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Apply this statement balance to the liability' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm Statement' }))
    await waitFor(() => expect(serviceMocks.confirm).toHaveBeenCalledWith('statement-1', true))
    expect(hookState.refetch).toHaveBeenCalled()
  })

  it('deletes a statement transaction after confirmation', async () => {
    renderPage()
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Transactions' }), {
      button: 0,
      ctrlKey: false,
    })
    fireEvent.click(screen.getByRole('button', { name: 'Delete Market' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(serviceMocks.deleteTransaction).toHaveBeenCalledWith('tx-1'))
    expect(hookState.refetch).toHaveBeenCalled()
  })
})
