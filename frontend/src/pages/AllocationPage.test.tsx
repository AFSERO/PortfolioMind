import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import AllocationPage from './AllocationPage'
import type { AllocationData } from '@/types'

const mockAllocation: AllocationData = {
  total_value: 100000,
  by_type: [
    {
      asset_type: 'STOCK',
      value: 60000,
      percentage: 60.0,
    },
    {
      asset_type: 'FUND',
      value: 40000,
      percentage: 40.0,
    },
  ],
  by_asset: [],
  base_currency: 'TRY',
}

const { dashboardHookState } = vi.hoisted(() => ({
  dashboardHookState: {
    data: null as AllocationData | null,
    isLoading: false,
    error: null as string | null,
    refetch: vi.fn(),
  },
}))

vi.mock('@/hooks/useDashboard', () => ({
  useDashboardAllocation: () => dashboardHookState,
}))

vi.mock('@/hooks/useForexRates', () => ({
  useForexRates: () => ({ rates: { 'USD/TRY': 40 }, isLoading: false }),
  convertCurrency: (val: number) => val,
}))

vi.mock('@/store/dashboardStore', () => ({
  useDashboardStore: () => ({
    currency: 'TRY',
    setCurrency: vi.fn(),
  }),
}))

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

// Recharts ResponsiveContainer mock
vi.mock('@/components/dashboard/AllocationChart', () => ({
  default: () => <div data-testid="allocation-chart">Allocation Chart Mock</div>,
}))

describe('AllocationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    dashboardHookState.data = mockAllocation
    dashboardHookState.isLoading = false
  })

  it('renders allocation page with drift analysis and table', () => {
    render(
      <MemoryRouter>
        <AllocationPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Portfolio Allocation')).toBeInTheDocument()
    expect(screen.getByTestId('allocation-chart')).toBeInTheDocument()
    expect(screen.getByText('Target Drift Analysis')).toBeInTheDocument()

    // Stocks (appears in largest category summary & table row)
    expect(screen.getAllByText('Stocks')[0]).toBeInTheDocument()
    expect(screen.getAllByText('60.0%')[0]).toBeInTheDocument()
    expect(screen.getAllByText('Overweight')[0]).toBeInTheDocument()

    // Funds row
    expect(screen.getByText('Funds')).toBeInTheDocument()
    expect(screen.getAllByText('40.0%')[0]).toBeInTheDocument()
  })

  it('renders empty state when no allocation data exists', () => {
    dashboardHookState.data = { total_value: 0, by_type: [], by_asset: [], base_currency: 'TRY' }

    render(
      <MemoryRouter>
        <AllocationPage />
      </MemoryRouter>
    )

    expect(screen.getByText('No asset allocation data found.')).toBeInTheDocument()
  })
})
