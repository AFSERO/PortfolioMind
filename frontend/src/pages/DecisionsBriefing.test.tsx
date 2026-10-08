import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import DecisionsPage from './DecisionsPage'
import BriefingPage from './BriefingPage'
import type { DecisionLogEntry, BriefingRun } from '@/types'

const mockDecisions: DecisionLogEntry[] = [
  {
    id: 'dec-1',
    user_id: 'user-1',
    event_type: 'POSITION_OPENED',
    title: 'Opened position in UBER',
    summary: 'BUY 10 @ 75.50 USD',
    user_rationale: 'Long-term thesis on mobility dominance and AV fleet expansion.',
    confidence: 'HIGH',
    expectation: '20% upside in 12M',
    instrument_symbol: 'UBER',
    instrument_name: 'Uber Technologies',
    asset_name: 'Uber Technologies',
    occurred_at: '2026-09-15T10:00:00Z',
    created_at: '2026-09-15T10:00:00Z',
    updated_at: '2026-09-15T10:00:00Z',
    metadata: {
      quantity: '10',
      price_per_unit: '75.50',
      currency: 'USD',
    },
  },
  {
    id: 'dec-2',
    user_id: 'user-1',
    event_type: 'THESIS_CHANGED',
    title: 'Thesis updated to STRONGER',
    summary: 'Thesis changed from UNCHANGED to STRONGER via deep-research',
    user_rationale: 'Autonomous vehicle partnership confirmed.',
    confidence: 'HIGH',
    expectation: 'Accelerating robotaxi margins',
    instrument_symbol: 'UBER',
    instrument_name: 'Uber Technologies',
    occurred_at: '2026-09-15T12:00:00Z',
    created_at: '2026-09-15T12:00:00Z',
    updated_at: '2026-09-15T12:00:00Z',
  },
  {
    id: 'dec-3',
    user_id: 'user-1',
    event_type: 'MANUAL_DECISION_NOTE',
    title: 'Macro interest rate caution',
    summary: 'Holding back new capital until next FOMC rate decision.',
    user_rationale: 'Yield curve steepening.',
    confidence: 'MEDIUM',
    occurred_at: '2026-09-15T14:00:00Z',
    created_at: '2026-09-15T14:00:00Z',
    updated_at: '2026-09-15T14:00:00Z',
  },
]

const mockBriefingRun: BriefingRun = {
  id: 'run-1',
  user_id: 'user-1',
  generated_at: '2026-09-16T08:00:00Z',
  scope: 'PORTFOLIO_AND_WATCHLIST',
  status: 'COMPLETED',
  items_found: 12,
  items_shown: 2,
  items_filtered: 10,
  created_at: '2026-09-16T08:00:00Z',
  items: [
    {
      id: 'item-1',
      briefing_run_id: 'run-1',
      user_id: 'user-1',
      instrument_id: 'inst-1',
      headline: 'Uber and Autonomous Vehicle Partner Sign Multi-Year Agreement',
      summary: 'Commercial deployment expanding across 5 major metro areas.',
      why_it_matters: 'Direct portfolio holding. Operational development with positive bias.',
      impact: 'POSITIVE',
      materiality: 'HIGH',
      time_horizon: 'MEDIUM',
      thesis_impact: 'STRONGER',
      review_required: true,
      category: 'OPERATIONAL',
      is_portfolio: true,
      published_at: '2026-09-16T07:30:00Z',
      created_at: '2026-09-16T08:00:00Z',
      instrument_symbol: 'UBER',
      instrument_name: 'Uber Technologies',
      source_metadata: {
        source: 'SEC EDGAR',
        url: 'https://sec.gov/edgar/item-1',
      },
    },
    {
      id: 'item-2',
      briefing_run_id: 'run-1',
      user_id: 'user-1',
      instrument_id: 'inst-2',
      headline: 'TSMC Announces 2nm Trial Production Ahead of Schedule',
      summary: 'Yields exceeding initial expectations for advanced nodes.',
      why_it_matters: 'Watchlist instrument. Key development to monitor prior to capital allocation.',
      impact: 'POSITIVE',
      materiality: 'MEDIUM',
      time_horizon: 'LONG',
      thesis_impact: 'NOT_EVALUATED',
      review_required: false,
      category: 'OPERATIONAL',
      is_portfolio: false,
      published_at: '2026-09-16T06:00:00Z',
      created_at: '2026-09-16T08:00:00Z',
      instrument_symbol: 'TSM',
      instrument_name: 'Taiwan Semiconductor',
      source_metadata: {
        source: 'Reuters',
        url: 'https://reuters.com/tsm',
      },
    },
  ],
}

vi.mock('@/hooks/useDecisions', () => ({
  useDecisions: () => ({
    decisions: mockDecisions,
    total: mockDecisions.length,
    isLoading: false,
    error: null,
    createDecision: vi.fn(),
    updateRationale: vi.fn(),
  }),
}))

vi.mock('@/hooks/useBriefing', () => ({
  useBriefing: () => ({
    briefing: mockBriefingRun,
    stats: {
      attention_count: 1,
      items_shown: 2,
      items_filtered: 10,
      last_generated_at: '2026-09-16T08:00:00Z',
    },
    isLoading: false,
    isGenerating: false,
    error: null,
    generateBriefing: vi.fn(),
    updateBriefingItem: vi.fn(),
  }),
}))

vi.mock('@/hooks/useAssets', () => ({
  useAssets: () => ({
    assets: [],
    isLoading: false,
  }),
}))

describe('DecisionsPage', () => {
  it('renders Decision Log header, counts, and timeline items', () => {
    render(
      <MemoryRouter>
        <DecisionsPage />
      </MemoryRouter>
    )

    expect(screen.getAllByText('Decision Log').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/3 Logged Decisions/i)).toBeInTheDocument()
    expect(screen.getByText('Opened position in UBER')).toBeInTheDocument()
    expect(screen.getByText('Thesis updated to STRONGER')).toBeInTheDocument()
    expect(screen.getByText('Macro interest rate caution')).toBeInTheDocument()
    expect(screen.getByText(/"Long-term thesis on mobility dominance and AV fleet expansion."/)).toBeInTheDocument()
  })

  it('filters decisions by category tabs', () => {
    render(
      <MemoryRouter>
        <DecisionsPage />
      </MemoryRouter>
    )

    // Click Trades filter tab
    const tradesTab = screen.getByRole('button', { name: /Trades/i })
    fireEvent.click(tradesTab)

    expect(screen.getByText('Opened position in UBER')).toBeInTheDocument()
    expect(screen.queryByText('Thesis updated to STRONGER')).not.toBeInTheDocument()
    expect(screen.queryByText('Macro interest rate caution')).not.toBeInTheDocument()

    // Click Manual Notes filter tab
    const notesTab = screen.getByRole('button', { name: /Manual Notes/i })
    fireEvent.click(notesTab)

    expect(screen.queryByText('Opened position in UBER')).not.toBeInTheDocument()
    expect(screen.getByText('Macro interest rate caution')).toBeInTheDocument()
  })
})

describe('BriefingPage', () => {
  it('renders Intelligence Briefing with pulse metrics and feed items', () => {
    render(
      <MemoryRouter>
        <BriefingPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Intelligence Briefing')).toBeInTheDocument()
    expect(screen.getByText('Needs Attention')).toBeInTheDocument()
    expect(screen.getAllByText('Worth Knowing').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Filtered as Noise')).toBeInTheDocument()

    // Development headlines
    expect(screen.getByText('Uber and Autonomous Vehicle Partner Sign Multi-Year Agreement')).toBeInTheDocument()
    expect(screen.getByText('TSMC Announces 2nm Trial Production Ahead of Schedule')).toBeInTheDocument()

    // Thesis reasoning
    expect(screen.getByText(/Direct portfolio holding. Operational development with positive bias./)).toBeInTheDocument()
    expect(screen.getByText('Run Thesis Review')).toBeInTheDocument()
  })

  it('filters developments by Attention tab', () => {
    render(
      <MemoryRouter>
        <BriefingPage />
      </MemoryRouter>
    )

    const attentionTab = screen.getByRole('button', { name: /Needs Attention/i })
    fireEvent.click(attentionTab)

    // Only UBER has review_required: true
    expect(screen.getByText('Uber and Autonomous Vehicle Partner Sign Multi-Year Agreement')).toBeInTheDocument()
    expect(screen.queryByText('TSMC Announces 2nm Trial Production Ahead of Schedule')).not.toBeInTheDocument()
  })
})
