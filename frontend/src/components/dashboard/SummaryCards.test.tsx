import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import SummaryCards from './SummaryCards'
import type { DashboardSummary, TimelinePoint } from '@/types'
import { formatCurrency } from '@/utils/format'
import { dashboardService } from '@/services/dashboardService'


function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    total_value: 500000,
    total_assets: 500000,
    total_liabilities: 20000,
    net_worth: 480000,
    total_cost: 400000,
    total_pl: 100000,
    total_pl_pct: 25,
    unrealized_pl: 100000,
    realized_pl: 0,
    total_cash: 0,
    asset_count: 1,
    liability_count: 1,
    best_performer: null,
    worst_performer: null,
    by_type_summary: [],
    base_currency: 'TRY',
    exchange_rates: { status: 'complete', rates: [] },
    ...overrides,
  }
}


describe('SummaryCards liabilities', () => {
  it('renders total assets, total liabilities, and net worth separately', () => {
    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    expect(screen.getAllByText('Total Assets')).not.toHaveLength(0)
    expect(screen.getAllByText('Total Liabilities')).not.toHaveLength(0)
    expect(screen.getByText('Net Worth')).toBeInTheDocument()
    expect(screen.getAllByText(formatCurrency(500000, 'TRY'))).not.toHaveLength(0)
    expect(screen.getAllByText(formatCurrency(20000, 'TRY'))).not.toHaveLength(0)
    expect(screen.getByText(formatCurrency(480000, 'TRY'))).toBeInTheDocument()
  })

  it('renders a negative net worth as a valid financial value', () => {
    render(
      <SummaryCards
        data={summary({ total_assets: 10000, total_value: 10000, total_liabilities: 20000, net_worth: -10000 })}
        isLoading={false}
        currency="TRY"
        rates={{}}
      />,
    )

    expect(screen.getByText(formatCurrency(-10000, 'TRY'))).toBeInTheDocument()
  })
})

describe('SummaryCards timeline & history rendering', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('triggers createSnapshot on mount and refetches timeline upon completion', async () => {
    const createSnapshotSpy = vi.spyOn(dashboardService, 'createSnapshot').mockResolvedValue({ message: 'Snapshot recorded' })
    const getTimelineSpy = vi.spyOn(dashboardService, 'getTimeline').mockResolvedValue([])

    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    expect(createSnapshotSpy).toHaveBeenCalled()
    await waitFor(() => {
      // initial getTimeline call + refetch after createSnapshot completes
      expect(getTimelineSpy.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders single snapshot point without empty-box placeholder', async () => {
    vi.spyOn(dashboardService, 'createSnapshot').mockResolvedValue({})
    const singlePoint: TimelinePoint[] = [
      {
        date: '2026-09-29',
        total_value_try: 500000,
        total_value_usd: 15000,
        total_assets_try: 500000,
        total_assets_usd: 15000,
        total_liabilities_try: 20000,
        total_liabilities_usd: 600,
        net_worth_try: 480000,
        net_worth_usd: 14400,
        value_semantics: 'net_worth',
      },
    ]
    vi.spyOn(dashboardService, 'getTimeline').mockResolvedValue(singlePoint)

    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    await waitFor(() => expect(screen.queryByLabelText('Loading portfolio history')).not.toBeInTheDocument())
    expect(screen.queryByText('No portfolio history yet')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Portfolio history chart')).toBeInTheDocument()
    expect(screen.getByText('Snapshot change unavailable')).toBeInTheDocument()
  })

  it('renders an honest empty state when timeline has no data', async () => {
    vi.spyOn(dashboardService, 'createSnapshot').mockResolvedValue({})
    vi.spyOn(dashboardService, 'getTimeline').mockResolvedValue([])

    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    await waitFor(() => {
      expect(screen.getByText('No portfolio history yet')).toBeInTheDocument()
    })
  })

  it('requests correct days for timeframes including 1825 for ALL', async () => {
    vi.spyOn(dashboardService, 'createSnapshot').mockResolvedValue({})
    const getTimelineSpy = vi.spyOn(dashboardService, 'getTimeline').mockResolvedValue([])

    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    for (const [name, days] of [['1W', 7], ['1M', 30], ['3M', 90], ['6M', 180], ['1Y', 365], ['ALL', 1825]] as const) {
      const option = screen.getByRole('radio', { name })
      fireEvent.click(option)
      await waitFor(() => expect(getTimelineSpy).toHaveBeenCalledWith(days))
      expect(option).toHaveAttribute('aria-checked', 'true')
    }
  })
})


describe('SummaryCards display states', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(dashboardService, 'createSnapshot').mockResolvedValue({})
    vi.spyOn(dashboardService, 'getTimeline').mockResolvedValue([])
  })

  it('shows a loading skeleton before summary data arrives', () => {
    render(<SummaryCards data={null} isLoading />)
    expect(screen.getByLabelText('Loading portfolio summary')).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByText('Total Portfolio Value')).not.toBeInTheDocument()
  })

  it('preserves TRY and USD balance conversion including cash and P/L', async () => {
    const data = summary({ total_cash: 50000 })
    const { rerender } = render(<SummaryCards data={data} isLoading={false} currency="TRY" rates={{ 'USD/TRY': 40 }} />)
    expect(screen.getByText(formatCurrency(480000, 'TRY'))).toBeInTheDocument()
    rerender(<SummaryCards data={data} isLoading={false} currency="USD" rates={{ 'USD/TRY': 40 }} />)
    expect(screen.getByText(formatCurrency(12000, 'USD'))).toBeInTheDocument()
    expect(screen.getByText(formatCurrency(500, 'USD'))).toBeInTheDocument()
    expect(screen.getByText(formatCurrency(1250, 'USD'))).toBeInTheDocument()
    expect(screen.getByText('+' + formatCurrency(2500, 'USD'))).toBeInTheDocument()
    expect(screen.getByText('10.0% of portfolio')).toBeInTheDocument()
    await screen.findByText('No portfolio history yet')
  })

  it('distinguishes a timeline API failure from empty history', async () => {
    vi.spyOn(dashboardService, 'getTimeline').mockRejectedValue(new Error('Offline'))
    render(<SummaryCards data={summary()} isLoading={false} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Historical data unavailable')
    expect(screen.queryByText('No portfolio history yet')).not.toBeInTheDocument()
    expect(screen.getByText(formatCurrency(480000, 'TRY'))).toBeInTheDocument()
  })

  it('hides and restores balances through the existing control', async () => {
    render(<SummaryCards data={summary()} isLoading={false} />)
    await screen.findByText('No portfolio history yet')
    fireEvent.click(screen.getByRole('button', { name: 'Hide balances' }))
    expect(screen.queryByText(formatCurrency(480000, 'TRY'))).not.toBeInTheDocument()
    expect(screen.getByText('Balances hidden')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show balances' }))
    expect(screen.getByText(formatCurrency(480000, 'TRY'))).toBeInTheDocument()
  })

  it('preserves snapshots in cache across timeframe switching to seed forward fill', async () => {
    // Initial 3M fetch returns snapshots including an older one from Sep 20
    const snapSep20: TimelinePoint = {
      date: '2026-09-20',
      total_value_try: 375000,
      total_value_usd: 12500,
      total_assets_try: 375000,
      total_assets_usd: 12500,
      total_liabilities_try: 0,
      total_liabilities_usd: 0,
      net_worth_try: 375000,
      net_worth_usd: 12500,
      value_semantics: 'net_worth',
    }
    const snapSep27: TimelinePoint = {
      date: '2026-09-27',
      total_value_try: 382000,
      total_value_usd: 12733,
      total_assets_try: 382000,
      total_assets_usd: 12733,
      total_liabilities_try: 0,
      total_liabilities_usd: 0,
      net_worth_try: 382000,
      net_worth_usd: 12733,
      value_semantics: 'net_worth',
    }

    const getTimelineSpy = vi.spyOn(dashboardService, 'getTimeline')
    // First call (days=90): returns both Sep 20 and Sep 27
    getTimelineSpy.mockResolvedValueOnce([snapSep20, snapSep27])
    // Second call on snapshot creation refetch: returns same
    getTimelineSpy.mockResolvedValueOnce([snapSep20, snapSep27])
    // Third call when user clicks 1W: backend only returns Sep 27 (since cutoff is Sep 24)
    getTimelineSpy.mockResolvedValueOnce([snapSep27])

    render(<SummaryCards data={summary()} isLoading={false} currency="TRY" rates={{}} />)

    await waitFor(() => {
      expect(screen.getByLabelText('Portfolio history chart')).toBeInTheDocument()
    })

    // Click 1W
    const option1W = screen.getByRole('radio', { name: '1W' })
    fireEvent.click(option1W)

    await waitFor(() => {
      expect(getTimelineSpy).toHaveBeenCalledWith(7)
    })

    // Chart remains visible and renders history smoothly without falling back to empty state
    expect(screen.getByLabelText('Portfolio history chart')).toBeInTheDocument()
    expect(screen.queryByText('No portfolio history yet')).not.toBeInTheDocument()
  })
})

