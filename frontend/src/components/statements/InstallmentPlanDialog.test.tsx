import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import InstallmentPlanDialog from './InstallmentPlanDialog'


function fillPlan(monthly: string) {
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Telefon' } })
  fireEvent.change(screen.getByLabelText('Purchase Date'), { target: { value: '2026-05-20' } })
  fireEvent.change(screen.getByLabelText('Original Amount'), { target: { value: '9000' } })
  fireEvent.change(screen.getByLabelText('Installment Count'), { target: { value: '6' } })
  fireEvent.change(screen.getByLabelText('Monthly Installment'), { target: { value: monthly } })
  fireEvent.change(screen.getByLabelText('First Installment Date'), { target: { value: '2026-06-24' } })
  fireEvent.change(screen.getByLabelText('Completed Installments'), { target: { value: '2' } })
}

describe('InstallmentPlanDialog', () => {
  it('rejects a schedule beyond rounding tolerance', async () => {
    const onSave = vi.fn()
    render(<InstallmentPlanDialog open currency="TRY" onClose={vi.fn()} onSave={onSave} />)
    fillPlan('100')
    fireEvent.click(screen.getByRole('button', { name: 'Save Plan' }))
    expect(await screen.findByText('Schedule exceeds rounding tolerance')).toBeInTheDocument()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('submits a valid plan', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(<InstallmentPlanDialog open currency="TRY" onClose={vi.fn()} onSave={onSave} />)
    fillPlan('1500')
    fireEvent.click(screen.getByRole('button', { name: 'Save Plan' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ original_amount: '9000', monthly_installment_amount: '1500', installment_count: 6, completed_installment_count: 2 }), undefined)
  })
})
