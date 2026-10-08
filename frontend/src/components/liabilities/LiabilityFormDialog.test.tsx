import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import LiabilityFormDialog from './LiabilityFormDialog'
import type { Liability } from '@/types'


vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))


function setInput(name: string, value: string) {
  const input = document.querySelector<HTMLInputElement>(`[name="${name}"]`)
  expect(input).not.toBeNull()
  fireEvent.change(input!, { target: { value } })
}


describe('LiabilityFormDialog', () => {
  it('submits monetary values as decimal strings and active state as a boolean', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <LiabilityFormDialog open onClose={vi.fn()} onSave={onSave} />,
    )

    setInput('name', 'Travel card')
    setInput('current_balance', '20000.123456')
    setInput('original_balance', '25000.654321')
    setInput('interest_rate', '4.25')
    setInput('minimum_payment', '500.10')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Active liability' }))
    fireEvent.click(screen.getByRole('button', { name: 'Add Liability' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Travel card',
        liability_type: 'credit_card',
        currency: 'TRY',
        current_balance: '20000.123456',
        original_balance: '25000.654321',
        interest_rate: '4.25',
        minimum_payment: '500.10',
        is_active: false,
      }),
      undefined,
    )
    const payload = onSave.mock.calls[0][0]
    expect(typeof payload.current_balance).toBe('string')
    expect(typeof payload.is_active).toBe('boolean')
  })

  it('preserves existing edit values when submitted unchanged', async () => {
    const liability: Liability = {
      id: 'liability-1',
      user_id: 'user-1',
      name: 'Home loan',
      liability_type: 'mortgage',
      currency: 'USD',
      current_balance: 5000.000001,
      original_balance: 8000.25,
      interest_rate: 3.5,
      minimum_payment: 125.75,
      due_date: '2026-08-31',
      notes: 'Keep this note',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    const onSave = vi.fn().mockResolvedValue(undefined)

    render(
      <LiabilityFormDialog
        open
        liability={liability}
        onClose={vi.fn()}
        onSave={onSave}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Home loan',
        liability_type: 'mortgage',
        currency: 'USD',
        current_balance: '5000.000001',
        original_balance: '8000.25',
        interest_rate: '3.5',
        minimum_payment: '125.75',
        due_date: '2026-08-31',
        notes: 'Keep this note',
        is_active: true,
      }),
      'liability-1',
    )
  })
})

