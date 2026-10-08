import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AssetFormDialog from './AssetFormDialog'
import { cashService } from '@/services/cashService'
import { assetResolverService } from '@/services/assetResolverService'

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

vi.mock('@/services/assetResolverService', () => ({
  assetResolverService: {
    resolve: vi.fn(),
  },
}))

describe('Unified Asset Search & Auto-Fill in AssetFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(cashService.getAccounts).mockResolvedValue([])
  })

  it('auto-fills US Stock metadata and price when NVDA is typed', async () => {
    vi.mocked(assetResolverService.resolve).mockResolvedValueOnce({
      symbol: 'NVDA',
      name: 'NVIDIA Corporation',
      asset_type: 'STOCK',
      currency: 'USD',
      latest_price: 213.30,
      price_date: '2026-09-15',
      market: 'NASDAQ',
      provider: 'yfinance',
    })

    render(
      <AssetFormDialog
        open={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    )

    const symbolInput = screen.getByPlaceholderText(/Search ticker or name…/i)
    fireEvent.change(symbolInput, { target: { value: 'NVDA' } })

    await waitFor(() => {
      expect(assetResolverService.resolve).toHaveBeenCalledWith('STOCK', 'NVDA')
    })

    await waitFor(() => {
      expect(screen.getByDisplayValue('NVIDIA Corporation')).toBeInTheDocument()
      expect(screen.getByDisplayValue('213.3')).toBeInTheDocument()
    })
  })

  it('auto-fills BIST Stock metadata and TRY currency when THYAO is typed', async () => {
    vi.mocked(assetResolverService.resolve).mockResolvedValueOnce({
      symbol: 'THYAO',
      name: 'Türk Hava Yolları',
      asset_type: 'STOCK',
      currency: 'TRY',
      latest_price: 292.00,
      price_date: '2026-09-15',
      market: 'BIST',
      provider: 'yfinance',
    })

    render(
      <AssetFormDialog
        open={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    )

    const symbolInput = screen.getByPlaceholderText(/Search ticker or name…/i)
    fireEvent.change(symbolInput, { target: { value: 'THYAO' } })

    await waitFor(() => {
      expect(assetResolverService.resolve).toHaveBeenCalledWith('STOCK', 'THYAO')
    })

    await waitFor(() => {
      expect(screen.getByDisplayValue('Türk Hava Yolları')).toBeInTheDocument()
      expect(screen.getByDisplayValue('292')).toBeInTheDocument()
    })
  })

  it('displays graceful error message on invalid symbol without crashing', async () => {
    vi.mocked(assetResolverService.resolve).mockRejectedValueOnce(
      new Error("Could not resolve stock 'ASSET_DOES_NOT_EXIST_92831'")
    )

    render(
      <AssetFormDialog
        open={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    )

    const symbolInput = screen.getByPlaceholderText(/Search ticker or name…/i)
    fireEvent.change(symbolInput, { target: { value: 'ASSET_DOES_NOT_EXIST_92831' } })

    await waitFor(() => {
      expect(
        screen.getByText(/Could not resolve stock 'ASSET_DOES_NOT_EXIST_92831'/i)
      ).toBeInTheDocument()
    })
  })
})
