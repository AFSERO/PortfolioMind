import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TechnicalPlanZones from './TechnicalPlanZones'
import type { TechnicalPlan } from '@/types'

describe('TechnicalPlanZones', () => {
  it('renders empty state when no active plan exists', () => {
    render(<TechnicalPlanZones plan={null} />)

    expect(screen.getByText('Technical Strategy Zones')).toBeInTheDocument()
    expect(screen.getByText(/No active technical plan or price zones/)).toBeInTheDocument()
  })

  it('renders strategy boundaries for entry, invalidation, and profit taking', () => {
    const plan: TechnicalPlan = {
      id: 'plan-1',
      instrument_id: 'inst-1',
      reference_at: '2026-09-14T10:00:00Z',
      trend_expectation: 'BULLISH_CONTINUATION',
      entry_zones: [{ low: 70, high: 75 }],
      review_or_invalidation_zones: [{ low: 62, high: 65 }],
      profit_taking_or_reassessment_zones: [{ low: 95, high: 105 }],
      notes: 'Watch daily 50 EMA bounce.',
      active: true,
      created_at: '',
      updated_at: '',
    }

    render(<TechnicalPlanZones plan={plan} currentPrice={73.5} currency="$" />)

    expect(screen.getByText('BULLISH CONTINUATION')).toBeInTheDocument()
    expect(screen.getByText(/62 – 65/)).toBeInTheDocument()
    expect(screen.getByText(/70 – 75/)).toBeInTheDocument()
    expect(screen.getByText(/95 – 105/)).toBeInTheDocument()
    expect(screen.getByText(/Watch daily 50 EMA bounce./)).toBeInTheDocument()
  })
})
