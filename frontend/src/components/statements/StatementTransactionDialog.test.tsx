import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import StatementTransactionDialog from './StatementTransactionDialog'
import type { StatementTransaction } from '@/types'


describe('StatementTransactionDialog', () => {
  it('creates a transaction with a decimal string amount', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<StatementTransactionDialog open currency="TRY" plans={[]} onClose={vi.fn()} onSave={onSave} />)
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-07-01' } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Market' } })
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '2000.000001' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Transaction' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ amount: '2000.000001', currency: 'TRY', transaction_type: 'purchase' }), undefined)
  })

  it('preserves edited transaction values', async () => {
    const transaction: StatementTransaction = { id: 'tx-1', user_id: 'user-1', statement_id: 'statement-1', transaction_date: '2026-07-02', posting_date: null, description: 'Online', merchant_name: null, transaction_type: 'purchase', amount: 3000, currency: 'TRY', installment_plan_id: null, installment_number: null, installment_count: null, external_reference: null, source_line_hash: null, notes: 'Existing', created_at: '', updated_at: '' }
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<StatementTransactionDialog open currency="TRY" plans={[]} transaction={transaction} onClose={vi.fn()} onSave={onSave} />)
    fireEvent.click(screen.getByRole('button', { name: 'Save Transaction' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ description: 'Online', amount: '3000', notes: 'Existing' }), 'tx-1')
  })
})
