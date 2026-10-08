import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AssetFormDialog from './AssetFormDialog'
import { cashService } from '@/services/cashService'
import { fundService } from '@/services/fundService'
import { api } from '@/services/api'
import type { Asset } from '@/types'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/services/cashService', () => ({
  cashService: {
    getAccounts: vi.fn(),
  },
}))

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const mockFundAsset: Asset = {
  id: 'fund-asset-1',
  user_id: 'user-1',
  asset_type: 'FUND',
  symbol: 'KCV',
  name: 'KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU',
  current_price: 5.289166,
  current_price_currency: 'TRY',
  is_manual_price: false,
  total_quantity: 1000,
  avg_cost: 5.20,
  avg_cost_currency: 'TRY',
  total_cost: 5200,
  realized_pl: 0,
  has_mixed_currencies: false,
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-15T00:00:00Z',
}

describe('Fund Support in Frontend', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(cashService.getAccounts).mockResolvedValue([])
  })

  it('fundService.getInfo queries /funds/info/{symbol}', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      status: 'success',
      data: {
        fund_code: 'KCV',
        fund_name: 'KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU',
        price: 5.289166,
        currency: 'TRY',
        price_date: '2026-09-15',
        provider: 'TEFAS',
      },
    })

    const info = await fundService.getInfo('KCV')
    expect(api.get).toHaveBeenCalledWith('/funds/info/KCV')
    expect(info.fund_code).toBe('KCV')
    expect(info.price).toBe(5.289166)
    expect(info.currency).toBe('TRY')
  })

  it('renders existing FUND asset with Fund Code label in AssetFormDialog', async () => {
    render(
      <AssetFormDialog
        open={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
        asset={mockFundAsset}
      />
    )

    // In edit mode for FUND, Fund Code label should be visible
    expect(screen.getByText('Fund Code')).toBeInTheDocument()
    // Fund name should be in input
    const nameInput = screen.getByDisplayValue('KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU')
    expect(nameInput).toBeInTheDocument()
  })
})
