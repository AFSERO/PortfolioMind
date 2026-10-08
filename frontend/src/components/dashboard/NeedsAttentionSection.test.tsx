import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import NeedsAttentionSection from './NeedsAttentionSection'
import type { Asset } from '@/types'

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

describe('NeedsAttentionSection', () => {
  it('renders the reassuring intentional quiet state when no alerts exist', () => {
    const assets = [
      makeAsset({
        instrument: {
          id: 'inst-1',
          name: 'Uber',
          symbol: 'UBER',
          asset_type: 'STOCK',
          created_at: '',
          updated_at: '',
          intelligence_state: {
            id: 'state-1',
            instrument_id: 'inst-1',
            thesis_status: 'UNCHANGED',
            valuation_status: 'FAIR',
            technical_status: 'ON_TRACK',
            recommendation: 'HOLD',
            created_at: '',
            updated_at: '',
          },
        },
      }),
    ]

    render(
      <BrowserRouter>
        <NeedsAttentionSection assets={assets} isLoading={false} />
      </BrowserRouter>
    )

    expect(screen.getByText('Nothing currently requires your attention.')).toBeInTheDocument()
    expect(screen.getByText(/1 positions monitored · 0 thesis-breaking events · 0 technical deviations/)).toBeInTheDocument()
  })

  it('renders actionable items when an asset thesis is invalidated', () => {
    const assets = [
      makeAsset({
        instrument: {
          id: 'inst-1',
          name: 'Uber',
          symbol: 'UBER',
          asset_type: 'STOCK',
          created_at: '',
          updated_at: '',
          intelligence_state: {
            id: 'state-1',
            instrument_id: 'inst-1',
            thesis_status: 'INVALIDATED',
            valuation_status: 'EXPENSIVE',
            technical_status: 'DEVIATED',
            recommendation: 'SELL',
            human_brief: 'Severe regulatory restriction passed.',
            created_at: '',
            updated_at: '',
          },
        },
      }),
    ]

    render(
      <BrowserRouter>
        <NeedsAttentionSection assets={assets} isLoading={false} />
      </BrowserRouter>
    )

    expect(screen.getByText('Thesis invalidated by material event')).toBeInTheDocument()
    expect(screen.getByText('Severe regulatory restriction passed.')).toBeInTheDocument()
    expect(screen.getByText('Review Asset')).toBeInTheDocument()
  })
})
