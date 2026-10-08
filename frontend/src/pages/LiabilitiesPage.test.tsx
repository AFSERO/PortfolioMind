import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LiabilitiesPage from './LiabilitiesPage'
import type { Liability } from '@/types'


const { hookState } = vi.hoisted(() => ({
  hookState: {
    liabilities: [] as Liability[],
    isLoading: false,
    error: null as string | null,
    refetch: vi.fn(),
    createLiability: vi.fn(),
    updateLiability: vi.fn(),
    deleteLiability: vi.fn(),
  },
}))

vi.mock('@/hooks/useLiabilities', () => ({
  useLiabilities: () => hookState,
}))

vi.mock('@/hooks/useForexRates', () => ({
  useForexRates: () => ({ rates: { 'USD/TRY': 40 }, isLoading: false }),
  convertCurrency: (
    amount: number,
    fromCurrency: string,
    toCurrency: string,
    rates: Record<string, number>,
  ) => {
    if (fromCurrency === toCurrency) return amount
    const rate = rates[`${fromCurrency}/${toCurrency}`]
    return rate && rate > 0 ? amount * rate : null
  },
}))

vi.mock('@/store', () => ({
  useAuthStore: () => ({ user: { base_currency: 'TRY' } }),
}))

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onSelect, ...props }: { children: React.ReactNode; onSelect?: () => void; [key: string]: unknown }) => <button type="button" role="menuitem" onClick={onSelect} {...props}>{children}</button>,
  DropdownMenuSeparator: () => <hr />,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))


const usdLiability: Liability = {
  id: 'liability-usd',
  user_id: 'user-1',
  name: 'Dollar loan',
  liability_type: 'personal_loan',
  currency: 'USD',
  current_balance: 5000,
  original_balance: null,
  interest_rate: null,
  minimum_payment: null,
  due_date: null,
  notes: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}


describe('LiabilitiesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    hookState.liabilities = []
    hookState.isLoading = false
    hookState.error = null
    hookState.deleteLiability.mockResolvedValue(undefined)
  })

  it('renders liabilities and their base-currency equivalent', () => {
    hookState.liabilities = [usdLiability]
    render(<LiabilitiesPage />)

    expect(screen.getByText('Dollar loan')).toBeInTheDocument()
    expect(screen.getAllByText(/200\.000,00/)).not.toHaveLength(0)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows Unavailable instead of a fabricated cross-currency value', () => {
    hookState.liabilities = [
      { ...usdLiability, id: 'liability-gbp', currency: 'GBP', current_balance: 100 },
    ]
    render(<LiabilitiesPage />)
    expect(screen.getAllByText('Unavailable')).not.toHaveLength(0)
  })

  it('renders empty, loading, and API error states safely', () => {
    const { rerender } = render(<LiabilitiesPage />)
    expect(screen.getByText('No liabilities yet')).toBeInTheDocument()

    hookState.isLoading = true
    rerender(<LiabilitiesPage />)
    expect(screen.getByLabelText('Loading liabilities')).toBeInTheDocument()

    hookState.isLoading = false
    hookState.error = 'Liabilities could not be loaded'
    rerender(<LiabilitiesPage />)
    expect(screen.getByRole('alert')).toHaveTextContent('Liabilities could not be loaded')
  })

  it('deletes only after explicit confirmation', async () => {
    hookState.liabilities = [usdLiability]
    render(<LiabilitiesPage />)

    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete Dollar loan' }))
    expect(hookState.deleteLiability).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Delete liability' }))

    await waitFor(() =>
      expect(hookState.deleteLiability).toHaveBeenCalledWith('liability-usd'),
    )
  })
})
