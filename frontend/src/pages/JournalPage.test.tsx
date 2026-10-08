import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import JournalPage from './JournalPage'
import type { Asset } from '@/types'

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
    notes: 'Long-term thesis on services ecosystem growth.',
    instrument_id: 'inst-1',
    instrument: {
      id: 'inst-1',
      symbol: 'AAPL',
      name: 'Apple Inc.',
      asset_type: 'STOCK',
      intelligence_state: {
        id: 'intel-1',
        instrument_id: 'inst-1',
        thesis_status: 'STRONGER',
        valuation_status: 'FAIR',
        technical_status: 'ON_TRACK',
        recommendation: 'HOLD',
        human_brief: 'Services revenue acceleration confirms capital allocation moat.',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

const { assetHookState } = vi.hoisted(() => ({
  assetHookState: {
    assets: [] as Asset[],
    isLoading: false,
    error: null as string | null,
    refetch: vi.fn(),
    updateAsset: vi.fn(),
  },
}))

vi.mock('@/hooks/useAssets', () => ({
  useAssets: () => assetHookState,
}))

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('JournalPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    assetHookState.assets = [...mockAssets]
    assetHookState.isLoading = false
    assetHookState.updateAsset.mockResolvedValue(mockAssets[0])
  })

  it('renders decision journal entries for thesis review and position notes', () => {
    render(
      <MemoryRouter>
        <JournalPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Decision Journal')).toBeInTheDocument()
    // Thesis review entry
    expect(screen.getByText(/Services revenue acceleration confirms capital allocation moat/i)).toBeInTheDocument()
    // Position note entry
    expect(screen.getByText(/Long-term thesis on services ecosystem growth/i)).toBeInTheDocument()
    // Filter counters
    expect(screen.getByText(/All \(2\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Thesis Reviews \(1\)/i)).toBeInTheDocument()
    expect(screen.getByText(/Position Notes \(1\)/i)).toBeInTheDocument()
  })

  it('filters entries when switching filter tabs', () => {
    render(
      <MemoryRouter>
        <JournalPage />
      </MemoryRouter>
    )

    // Filter to Thesis Reviews only
    fireEvent.click(screen.getByText(/Thesis Reviews \(1\)/i))
    expect(screen.getByText(/Services revenue acceleration confirms capital allocation moat/i)).toBeInTheDocument()
    expect(screen.queryByText(/Long-term thesis on services ecosystem growth/i)).not.toBeInTheDocument()

    // Filter to Position Notes only
    fireEvent.click(screen.getByText(/Position Notes \(1\)/i))
    expect(screen.queryByText(/Services revenue acceleration confirms capital allocation moat/i)).not.toBeInTheDocument()
    expect(screen.getByText(/Long-term thesis on services ecosystem growth/i)).toBeInTheDocument()
  })

  it('filters entries when searching text', () => {
    render(
      <MemoryRouter>
        <JournalPage />
      </MemoryRouter>
    )

    const searchInput = screen.getByPlaceholderText(/search journal entries/i)
    fireEvent.change(searchInput, { target: { value: 'services ecosystem' } })

    expect(screen.getByText(/Long-term thesis on services ecosystem growth/i)).toBeInTheDocument()
    expect(screen.queryByText(/Services revenue acceleration confirms capital allocation moat/i)).not.toBeInTheDocument()
  })

  it('records a new decision note', async () => {
    render(
      <MemoryRouter>
        <JournalPage />
      </MemoryRouter>
    )

    fireEvent.click(screen.getByText('Record Decision Note'))
    expect(screen.getByText('Document your thesis rationale, conviction, or rebalancing reasons for a portfolio holding.')).toBeInTheDocument()

    const select = screen.getByLabelText(/select holding/i)
    fireEvent.change(select, { target: { value: 'asset-1' } })

    const textarea = screen.getByLabelText(/decision rationale/i)
    fireEvent.change(textarea, { target: { value: 'Trimmed 10% after reaching upper valuation band.' } })

    fireEvent.click(screen.getByText('Save to Journal'))

    await waitFor(() => {
      expect(assetHookState.updateAsset).toHaveBeenCalledWith('asset-1', {
        notes: 'Trimmed 10% after reaching upper valuation band.',
      })
    })
  })

  it('renders reassuring empty state when no notes or reviews exist', () => {
    assetHookState.assets = []
    render(
      <MemoryRouter>
        <JournalPage />
      </MemoryRouter>
    )

    expect(screen.getByText('No decision entries recorded yet')).toBeInTheDocument()
  })
})
