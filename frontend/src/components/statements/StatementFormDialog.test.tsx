import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import StatementFormDialog from './StatementFormDialog'
import type { Liability, LiabilityStatement } from '@/types'


const liability: Liability = {
  id: 'card-1', user_id: 'user-1', name: 'Garanti Bonus', liability_type: 'credit_card', currency: 'TRY', current_balance: 0, original_balance: null, interest_rate: null, minimum_payment: null, due_date: null, notes: null, is_active: true, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

function fillRequired() {
  fireEvent.change(screen.getByLabelText('Period Start'), { target: { value: '2026-06-25' } })
  fireEvent.change(screen.getByLabelText('Period End'), { target: { value: '2026-07-24' } })
  fireEvent.change(screen.getByLabelText('Statement Date'), { target: { value: '2026-07-24' } })
  fireEvent.change(screen.getByLabelText('Due Date'), { target: { value: '2026-08-12' } })
  fireEvent.change(screen.getByLabelText('Previous Balance'), { target: { value: '5000.000001' } })
  fireEvent.change(screen.getByLabelText('Purchases'), { target: { value: '12000.000001' } })
  fireEvent.change(screen.getByLabelText('Payments'), { target: { value: '4000.000001' } })
  fireEvent.change(screen.getByLabelText('Refunds'), { target: { value: '1000.000001' } })
  fireEvent.change(screen.getByLabelText('Interest'), { target: { value: '200.000001' } })
  fireEvent.change(screen.getByLabelText('Fees'), { target: { value: '100.000001' } })
  fireEvent.change(screen.getByLabelText('Reported Statement Balance'), { target: { value: '12300.000001' } })
  fireEvent.change(screen.getByLabelText('Minimum Payment'), { target: { value: '2460.000001' } })
  fireEvent.change(screen.getByLabelText('Remaining Installments (informational)'), { target: { value: '6000.000001' } })
}

describe('StatementFormDialog', () => {
  it('submits every monetary field as a decimal string', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<StatementFormDialog open liability={liability} onClose={vi.fn()} onSave={onSave} />)
    fillRequired()
    fireEvent.click(screen.getByRole('button', { name: 'Add Statement' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave.mock.calls[0][0]).toMatchObject({
      currency: 'TRY', previous_balance: '5000.000001', purchases_total: '12000.000001', payments_total: '4000.000001', refunds_total: '1000.000001', fees_total: '100.000001', interest_total: '200.000001', statement_balance: '12300.000001', minimum_payment: '2460.000001', remaining_installments_total: '6000.000001', source: 'manual',
    })
  })

  it('preserves existing values when editing', async () => {
    const statement = {
      id: 'statement-1', liability_id: liability.id, user_id: liability.user_id, statement_period_start: '2026-06-25', statement_period_end: '2026-07-24', statement_date: '2026-07-24', due_date: '2026-08-12', currency: 'TRY', previous_balance: 5000, payments_total: 4000, purchases_total: 12000, fees_total: 100, interest_total: 200, refunds_total: 1000, statement_balance: 12300, minimum_payment: 2460, remaining_installments_total: 6000, status: 'draft', notes: 'Existing', source: 'manual', source_file_hash: null, confirmed_at: null, applied_to_liability_at: null, applied_balance: null, created_at: '', updated_at: '', calculated_balance: 12300, reported_balance: 12300, reconciliation_difference: 0, is_reconciled: true, reconciliation_tolerance: 0.01, calculation_source: 'summary', summary_calculated_balance: 12300, summary_difference: 0, transaction_calculated_balance: null, transaction_difference: null, transaction_count: 0,
    } satisfies LiabilityStatement
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<StatementFormDialog open liability={liability} statement={statement} onClose={vi.fn()} onSave={onSave} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ statement_balance: '12300', notes: 'Existing' }), 'statement-1')
  })
})
