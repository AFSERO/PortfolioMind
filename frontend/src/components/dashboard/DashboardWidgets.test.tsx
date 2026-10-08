import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AllocationChart from './AllocationChart'
import UpcomingEventsCard from './UpcomingEventsCard'
import ResearchQueueCard from './ResearchQueueCard'
import InvestorProfileBanner from './InvestorProfileBanner'
import { investorProfileService } from '@/services/investorProfileService'
import { formatCurrency } from '@/utils/format'
import type { AllocationData, Asset } from '@/types'

const allocation: AllocationData = {
  total_value: 4000,
  by_type: [{ asset_type: 'STOCK', value: 3000, percentage: 75 }, { asset_type: 'FUND', value: 1000, percentage: 25 }],
  by_asset: [],
  base_currency: 'TRY',
}

describe('Dashboard widgets', () => {
  beforeEach(() => { vi.restoreAllMocks(); sessionStorage.clear() })

  it('shows API allocation percentages and converts category balances with the display currency', () => {
    render(<MemoryRouter><AllocationChart data={allocation} isLoading={false} currency="USD" rates={{ 'USD/TRY': 40 }} /></MemoryRouter>)
    expect(screen.getByText('75.0%')).toBeInTheDocument()
    expect(screen.getByText(formatCurrency(75, 'USD'))).toBeInTheDocument()
    expect(screen.getByText(formatCurrency(25, 'USD'))).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View details' })).toHaveAttribute('href', '/allocation')
  })

  it('provides the existing holdings route for an empty allocation', () => {
    render(<MemoryRouter><AllocationChart data={null} isLoading={false} /></MemoryRouter>)
    expect(screen.getByText('No allocation data yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Add first asset/ })).toHaveAttribute('href', '/assets')
  })

  it('shows empty events without inventing dated portfolio milestones', () => {
    render(<MemoryRouter><UpcomingEventsCard assets={[]} /></MemoryRouter>)
    expect(screen.getByText('No scheduled reviews')).toBeInTheDocument()
    expect(screen.queryByText('Q4 Thesis Review Cadence')).not.toBeInTheDocument()
    expect(screen.queryByText('Semi-Annual Rebalancing')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View all' })).toHaveAttribute('href', '/monitoring')
  })

  it('renders a real scheduled review linked to its existing asset', () => {
    const date = new Date(Date.now() + 7 * 86400000).toISOString()
    const asset = { id: 'holding-1', symbol: 'TEST', instrument: { intelligence_state: { next_review_at: date } } } as Asset
    render(<MemoryRouter><UpcomingEventsCard assets={[asset]} /></MemoryRouter>)
    expect(screen.getByRole('link', { name: /TEST Review/ })).toHaveAttribute('href', '/assets/holding-1')
  })

  it('keeps loading distinct from empty research and events', () => {
    render(<MemoryRouter><ResearchQueueCard assets={[]} isLoading /><UpcomingEventsCard assets={[]} isLoading /></MemoryRouter>)
    expect(screen.getByLabelText('Loading research queue')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading upcoming events')).toBeInTheDocument()
    expect(screen.queryByText('No scheduled reviews')).not.toBeInTheDocument()
  })

  it('preserves assessment navigation and session dismissal', async () => {
    vi.spyOn(investorProfileService, 'getCurrentProfile').mockRejectedValue(new Error('No profile yet'))
    render(<MemoryRouter><InvestorProfileBanner /></MemoryRouter>)
    expect(await screen.findByRole('link', { name: 'Start Assessment' })).toHaveAttribute('href', '/onboarding')
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss for this session' }))
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Start Assessment' })).not.toBeInTheDocument())
    expect(sessionStorage.getItem('dismiss_investor_profile_banner')).toBe('true')
  })
})
