import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LiabilityStatementsPage from './LiabilityStatementsPage'
import type { InstallmentForecast, Liability, LiabilityStatement } from '@/types'


const liability: Liability = { id: 'card-1', user_id: 'user-1', name: 'Garanti Bonus', liability_type: 'credit_card', currency: 'TRY', current_balance: 0, original_balance: null, interest_rate: null, minimum_payment: null, due_date: null, notes: null, is_active: true, created_at: '', updated_at: '' }
const statement: LiabilityStatement = { id: 'statement-1', user_id: 'user-1', liability_id: 'card-1', statement_period_start: '2026-06-25', statement_period_end: '2026-07-24', statement_date: '2026-07-24', due_date: '2026-08-12', currency: 'TRY', previous_balance: 5000, payments_total: 4000, purchases_total: 12000, fees_total: 100, interest_total: 200, refunds_total: 1000, statement_balance: 12300, minimum_payment: 2460, remaining_installments_total: 6000, status: 'draft', notes: null, source: 'manual', source_file_hash: null, confirmed_at: null, applied_to_liability_at: null, applied_balance: null, created_at: '', updated_at: '', calculated_balance: 12300, reported_balance: 12300, reconciliation_difference: 0, is_reconciled: true, reconciliation_tolerance: 0.01, calculation_source: 'summary', summary_calculated_balance: 12300, summary_difference: 0, transaction_calculated_balance: null, transaction_difference: null, transaction_count: 0 }
const forecast: InstallmentForecast = { currency: 'TRY', as_of: '2026-08-06', next_month_total: 1500, next_three_months: [{ month: '2026-09-01', amount: 1500 }, { month: '2026-10-01', amount: 1500 }, { month: '2026-11-01', amount: 1500 }], remaining_total: 6000, nearest_installment_date: '2026-08-24', active_plan_count: 1 }

const { hookState, serviceMocks } = vi.hoisted(() => ({
  hookState: { liability: null as Liability | null, statements: [] as LiabilityStatement[], plans: [], forecast: null as InstallmentForecast | null, isLoading: false, error: null as string | null, refetch: vi.fn() },
  serviceMocks: { delete: vi.fn(), cancelPlan: vi.fn(), create: vi.fn(), update: vi.fn(), createPlan: vi.fn(), updatePlan: vi.fn() },
}))

vi.mock('@/hooks/useStatements', () => ({ useStatementWorkspace: () => hookState }))
vi.mock('@/services/statementService', () => ({ statementService: serviceMocks }))
vi.mock('@/components/layout/AppShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

function renderPage() {
  return render(<MemoryRouter initialEntries={['/liabilities/card-1/statements']}><Routes><Route path="/liabilities/:liabilityId/statements" element={<LiabilityStatementsPage />} /></Routes></MemoryRouter>)
}

describe('LiabilityStatementsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks(); hookState.liability = liability; hookState.statements = [statement]; hookState.plans = []; hookState.forecast = forecast; hookState.isLoading = false; hookState.error = null; hookState.refetch.mockResolvedValue(undefined); serviceMocks.delete.mockResolvedValue(undefined)
  })

  it('renders statement rows and future installment summary', () => {
    renderPage()
    expect(screen.getByText('Garanti Bonus Statements')).toBeInTheDocument()
    expect(screen.getByText(/12\.300,00/)).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Installments' }), {
      button: 0,
      ctrlKey: false,
    })
    expect(screen.getByText('Next Month')).toBeInTheDocument()
    expect(screen.getByText('Active Plans')).toBeInTheDocument()
  })

  it('renders empty, loading, and error states safely', () => {
    hookState.statements = []
    const { rerender } = renderPage()
    expect(screen.getByText('No statements yet')).toBeInTheDocument()
    hookState.isLoading = true
    rerender(<MemoryRouter initialEntries={['/liabilities/card-1/statements']}><Routes><Route path="/liabilities/:liabilityId/statements" element={<LiabilityStatementsPage />} /></Routes></MemoryRouter>)
    expect(screen.getByLabelText('Loading statements')).toBeInTheDocument()
    hookState.isLoading = false; hookState.error = 'API failed'
    rerender(<MemoryRouter initialEntries={['/liabilities/card-1/statements']}><Routes><Route path="/liabilities/:liabilityId/statements" element={<LiabilityStatementsPage />} /></Routes></MemoryRouter>)
    expect(screen.getByRole('alert')).toHaveTextContent('API failed')
  })

  it('deletes a statement only after confirmation and refreshes', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Delete statement 2026-07-24' }))
    expect(serviceMocks.delete).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(serviceMocks.delete).toHaveBeenCalledWith('statement-1'))
    expect(hookState.refetch).toHaveBeenCalled()
  })
})
