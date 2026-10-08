import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AssetFormDialog from './AssetFormDialog'
import TransactionDialog from './TransactionDialog'
import { cashService } from '@/services/cashService'
import type { Asset } from '@/types'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/services/cashService', () => ({
  cashService: {
    getAccounts: vi.fn(),
    deposit: vi.fn(),
    withdraw: vi.fn(),
    transfer: vi.fn(),
    getMovements: vi.fn(),
  },
}))

const asset: Asset = {
  id: 'asset-1',
  user_id: 'user-1',
  asset_type: 'STOCK',
  symbol: 'AAPL',
  name: 'Apple',
  is_manual_price: false,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  total_quantity: 10,
  avg_cost: 100,
  avg_cost_currency: 'USD',
  total_cost: 1000,
  realized_pl: 0,
  has_mixed_currencies: false,
}

function setInput(name: string, value: string) {
  const input = document.querySelector<HTMLInputElement>(`input[name="${name}"]`)
  expect(input).not.toBeNull()
  fireEvent.change(input!, { target: { value } })
}

describe('transaction cash ownership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(cashService.getAccounts).mockResolvedValue([])
  })

  it.each([
    ['BUY', 'withdraw'],
    ['SELL', 'deposit'],
  ] as const)(
    'sends affects_cash for %s without a second %s request',
    async (type, _cashOperation) => {
      const onCreate = vi.fn().mockResolvedValue(undefined)
      render(
        <TransactionDialog
          open
          onClose={vi.fn()}
          asset={asset}
          onCreate={onCreate}
          onUpdate={vi.fn()}
        />,
      )

      if (type === 'SELL') {
        fireEvent.click(screen.getByRole('button', { name: 'SELL' }))
      }
      setInput('quantity', '2')
      setInput('price_per_unit', '150')
      fireEvent.click(screen.getByRole('button', { name: `Add ${type}` }))

      await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1))
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          transaction_type: type,
          quantity: 2,
          price_per_unit: 150,
          affects_cash: true,
        }),
      )
      expect(cashService.withdraw).not.toHaveBeenCalled()
      expect(cashService.deposit).not.toHaveBeenCalled()
    },
  )

  it('passes the initial asset BUY checkbox as a boolean without withdrawing again', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <AssetFormDialog
        open
        onClose={vi.fn()}
        onSave={onSave}
      />,
    )

    setInput('name', 'Apple')
    setInput('quantity', '2')
    setInput('price_per_unit', '100')
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Add Asset' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        initial_transaction: expect.objectContaining({
          transaction_type: 'BUY',
          affects_cash: false,
        }),
      }),
    )
    const payload = onSave.mock.calls[0][0].initial_transaction
    expect(typeof payload.affects_cash).toBe('boolean')
    expect(cashService.withdraw).not.toHaveBeenCalled()
    expect(cashService.deposit).not.toHaveBeenCalled()
  })
})
