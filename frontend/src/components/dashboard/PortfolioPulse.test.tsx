import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PortfolioPulse from './PortfolioPulse'
import type { Asset, AllocationData } from '@/types'

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

describe('PortfolioPulse', () => {
  it('renders all four pulse indicators in calm normal state when no alerts exist', () => {
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

    const allocation: AllocationData = {
      total_value: 1000,
      by_type: [{ asset_type: 'STOCK', value: 1000, percentage: 100 }],
      by_asset: [{ asset_id: 'asset-1', name: 'Uber', symbol: 'UBER', asset_type: 'STOCK', value: 1000, percentage: 100 }],
    }

    render(<PortfolioPulse assets={assets} allocation={allocation} isLoading={false} />)

    expect(screen.getByText('Material Events')).toBeInTheDocument()
    expect(screen.getByText('Thesis Alerts')).toBeInTheDocument()
    expect(screen.getByText('Upcoming Events')).toBeInTheDocument()
    expect(screen.getByText('Target Alignment')).toBeInTheDocument()
    expect(screen.getByText('Operating normally')).toBeInTheDocument()
    expect(screen.getByText('Theses intact')).toBeInTheDocument()
  })

  it('increments thesis alerts when an asset has a WEAKER thesis status', () => {
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
            thesis_status: 'WEAKER',
            valuation_status: 'EXPENSIVE',
            technical_status: 'DEVIATED',
            recommendation: 'REVIEW_REQUIRED',
            created_at: '',
            updated_at: '',
          },
        },
      }),
    ]

    render(<PortfolioPulse assets={assets} allocation={null} isLoading={false} />)

    expect(screen.getByText('Holdings need review')).toBeInTheDocument()
    expect(screen.getByText('Require attention')).toBeInTheDocument()
  })
})
