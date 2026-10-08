import { fireEvent, render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import MonitoringTable from './MonitoringTable'
import type { Asset } from '@/types'
import { assetService } from '@/services/assetService'

function makeAsset(overrides: Partial<Asset> = {}): Asset {
  return {
    id: 'asset-1',
    user_id: 'user-1',
    name: 'Uber Technologies',
    symbol: 'UBER',
    asset_type: 'STOCK',
    is_manual_price: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    total_quantity: 10,
    avg_cost: 50,
    avg_cost_currency: 'USD',
    total_cost: 500,
    realized_pl: 0,
    has_mixed_currencies: false,
    ...overrides,
  }
}

describe('MonitoringTable', () => {
  it('renders table with assets and filters correctly', () => {
    const assets: Asset[] = [
      makeAsset({
        id: 'uber-1',
        name: 'Uber Technologies',
        symbol: 'UBER',
        instrument: {
          id: 'inst-uber',
          name: 'Uber',
          symbol: 'UBER',
          asset_type: 'STOCK',
          created_at: '',
          updated_at: '',
          intelligence_state: {
            id: 'state-1',
            instrument_id: 'inst-uber',
            thesis_status: 'WEAKER',
            valuation_status: 'EXPENSIVE',
            technical_status: 'DEVIATED',
            recommendation: 'REVIEW_REQUIRED',
            created_at: '',
            updated_at: '',
          },
        },
      }),
      makeAsset({
        id: 'aapl-1',
        name: 'Apple Inc',
        symbol: 'AAPL',
        instrument: {
          id: 'inst-aapl',
          name: 'Apple',
          symbol: 'AAPL',
          asset_type: 'STOCK',
          created_at: '',
          updated_at: '',
          intelligence_state: {
            id: 'state-2',
            instrument_id: 'inst-aapl',
            thesis_status: 'UNCHANGED',
            valuation_status: 'FAIR',
            technical_status: 'ON_TRACK',
            recommendation: 'HOLD',
            created_at: '',
            updated_at: '',
          },
        },
      }),
      // Completely unreviewed asset
      makeAsset({
        id: 'btc-1',
        name: 'Bitcoin',
        symbol: 'BTC',
        asset_type: 'CRYPTO',
        instrument: {
          id: 'inst-btc',
          name: 'Bitcoin',
          symbol: 'BTC',
          asset_type: 'CRYPTO',
          created_at: '',
          updated_at: '',
          intelligence_state: null,
        },
      }),
    ]

    render(
      <BrowserRouter>
        <MonitoringTable assets={assets} isLoading={false} />
      </BrowserRouter>
    )

    // All monitored shows all three
    expect(screen.getByText('UBER')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('BTC')).toBeInTheDocument()

    // Unreviewed asset MUST display "NOT REVIEWED" under recommendation, NOT "HOLD"
    const notReviewedBadges = screen.getAllByText('NOT REVIEWED')
    expect(notReviewedBadges.length).toBeGreaterThan(0)

    // Click "Attention Required"
    fireEvent.click(screen.getByRole('button', { name: /Attention Required/i }))
    expect(screen.getByText('UBER')).toBeInTheDocument()
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    expect(screen.queryByText('BTC')).not.toBeInTheDocument()

    // Click "On Track"
    fireEvent.click(screen.getByRole('button', { name: /On Track/i }))
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.queryByText('UBER')).not.toBeInTheDocument()
    // BTC must NOT be in On Track!
    expect(screen.queryByText('BTC')).not.toBeInTheDocument()

    // Click "Unreviewed"
    fireEvent.click(screen.getByRole('button', { name: /Unreviewed/i }))
    expect(screen.getByText('BTC')).toBeInTheDocument()
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    expect(screen.queryByText('UBER')).not.toBeInTheDocument()
  })

  it('triggers Deep Research when clicking button', async () => {
    const runMock = vi.spyOn(assetService, 'runDeepResearch').mockResolvedValue({
      status: 'COMPLETED',
      summary: { recommendation: 'ADD' },
    })

    const onRefresh = vi.fn()
    const assets: Asset[] = [
      makeAsset({
        id: 'thyao-1',
        name: 'Türk Hava Yolları',
        symbol: 'THYAO',
        asset_type: 'STOCK',
        instrument: {
          id: 'inst-thyao',
          name: 'THYAO',
          symbol: 'THYAO',
          asset_type: 'STOCK',
          created_at: '',
          updated_at: '',
          intelligence_state: null,
        },
      }),
    ]

    render(
      <BrowserRouter>
        <MonitoringTable assets={assets} isLoading={false} onRefresh={onRefresh} />
      </BrowserRouter>
    )

    const deepResearchBtn = screen.getByRole('button', { name: /Deep Research/i })
    expect(deepResearchBtn).toBeInTheDocument()

    fireEvent.click(deepResearchBtn)
    expect(runMock).toHaveBeenCalledWith('thyao-1')
  })
})
