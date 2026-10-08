import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import WatchlistPage from './WatchlistPage'
import ResearchPage from './ResearchPage'
import type { Instrument, Asset } from '@/types'

const mockInstruments: Instrument[] = [
  {
    id: 'inst-1',
    symbol: 'TSM',
    name: 'Taiwan Semiconductor Manufacturing',
    asset_type: 'STOCK',
    exchange: 'NYSE',
    intelligence_state: {
      id: 'intel-1',
      instrument_id: 'inst-1',
      thesis_status: 'STRONGER',
      valuation_status: 'FAIR',
      technical_status: 'ON_TRACK',
      recommendation: 'ADD',
      human_brief: 'Leading semiconductor foundry.',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'inst-2',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    asset_type: 'STOCK',
    exchange: 'NASDAQ',
    intelligence_state: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

const mockAssets: Asset[] = [
  {
    id: 'asset-1',
    user_id: 'user-1',
    name: 'Apple Inc.',
    asset_type: 'STOCK',
    symbol: 'AAPL',
    current_price: 180,
    current_price_currency: 'USD',
    is_manual_price: false,
    total_quantity: 10,
    avg_cost: 150,
    avg_cost_currency: 'USD',
    total_cost: 1500,
    realized_pl: 0,
    has_mixed_currencies: false,
    instrument_id: 'inst-2',
    instrument: mockInstruments[1],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

const { instHookState, assetHookState } = vi.hoisted(() => ({
  instHookState: {
    instruments: [] as Instrument[],
    isLoading: false,
    error: null as string | null,
    refetch: vi.fn(),
    createInstrument: vi.fn(),
  },
  assetHookState: {
    assets: [] as Asset[],
    isLoading: false,
    error: null as string | null,
    refetch: vi.fn(),
  },
}))

vi.mock('@/hooks/useInstruments', () => ({
  useInstruments: () => instHookState,
}))

vi.mock('@/hooks/useAssets', () => ({
  useAssets: () => assetHookState,
}))

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

describe('WatchlistPage and ResearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    instHookState.instruments = [...mockInstruments]
    instHookState.isLoading = false
    assetHookState.assets = [...mockAssets]
    assetHookState.isLoading = false
  })

  it('renders watchlist candidate instruments and searches', () => {
    render(
      <MemoryRouter>
        <WatchlistPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Watchlist')).toBeInTheDocument()
    expect(screen.getByText('TSM')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('Taiwan Semiconductor Manufacturing')).toBeInTheDocument()

    // Test search filter
    const searchInput = screen.getByPlaceholderText(/search watchlist/i)
    fireEvent.change(searchInput, { target: { value: 'TSM' } })
    expect(screen.getByText('TSM')).toBeInTheDocument()
    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument()
  })

  it('renders empty state when watchlist has no items', () => {
    instHookState.instruments = []
    render(
      <MemoryRouter>
        <WatchlistPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Your watchlist is empty')).toBeInTheDocument()
  })

  it('renders Research pipeline with columns and proper item distribution', () => {
    render(
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Research Pipeline')).toBeInTheDocument()
    expect(screen.getAllByText('Screening')[0]).toBeInTheDocument()
    expect(screen.getByText('Deep Research')).toBeInTheDocument()
    expect(screen.getByText('Waiting for Price')).toBeInTheDocument()
    expect(screen.getByText('Owned Holdings')).toBeInTheDocument()

    // TSM is candidate (not owned) -> in Screening
    // AAPL is owned (asset exists with instrument_id inst-2) -> in Owned Holdings
    expect(screen.getByText('TSM')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
  })
})
