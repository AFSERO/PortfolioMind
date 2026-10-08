import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import Sidebar from './Sidebar'

describe('Sidebar navigation', () => {
  it('renders PortfolioMind brand and hierarchical navigation groups', () => {
    render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>
    )

    // Brand
    expect(screen.getAllByText('PortfolioMind').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Investment Intelligence').length).toBeGreaterThanOrEqual(1)

    // Overview
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThanOrEqual(1)

    // Portfolio
    expect(screen.getAllByText('Holdings').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Allocation').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Cash').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Liabilities').length).toBeGreaterThanOrEqual(1)

    // Intelligence
    expect(screen.getAllByText('Copilot').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Briefing').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Watchlist').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Research').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Monitoring').length).toBeGreaterThanOrEqual(1)

    // Decisions
    expect(screen.getAllByText('Decision Log').length).toBeGreaterThanOrEqual(1)
  })
})
