import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import FinancialProfilePage from './FinancialProfilePage'
import { financialContextService } from '@/services/financialContextService'

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

vi.mock('@/services/financialContextService', () => ({
  financialContextService: {
    getFinancialContext: vi.fn(),
    listGoals: vi.fn(),
    listMandates: vi.fn(),
    getFinancialIntelligenceSummary: vi.fn(),
    getUnassignedResources: vi.fn(),
    createGoal: vi.fn(),
    deleteGoal: vi.fn(),
    createMandate: vi.fn(),
    transferCapital: vi.fn(),
    updateFinancialContext: vi.fn(),
    confirmFinancialContext: vi.fn(),
  },
}))

describe('Phase 4.1: FinancialProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders KPI bar, goals, and mandates correctly', async () => {
    vi.mocked(financialContextService.getFinancialContext).mockResolvedValue({
      id: 'ctx-1',
      user_id: 'user-1',
      financial_scope: 'INDIVIDUAL',
      spending_currencies: ['TRY'],
      planning_currency: 'TRY',
      monthly_net_income: '100000.00',
      monthly_essential_expenses: '65000.00',
      monthly_discretionary_expenses: '15000.00',
      income_stability: 'PREDICTABLE',
      last_confirmed_at: '2026-09-29T12:00:00Z',
      created_at: '2026-09-29T10:00:00Z',
      updated_at: '2026-09-29T10:00:00Z',
    })

    vi.mocked(financialContextService.getFinancialIntelligenceSummary).mockResolvedValue({
      user_id: 'user-1',
      net_worth: '450000.00',
      liquid_net_worth: '350000.00',
      monthly_surplus: '35000.00',
      savings_rate_pct: '35.0',
      emergency_coverage_months: '5.4',
      debt_to_income_pct: '4.2',
      currency: 'TRY',
      issues: [],
    })

    vi.mocked(financialContextService.listGoals).mockResolvedValue([
      {
        id: 'goal-1',
        user_id: 'user-1',
        name: 'Home Down Payment',
        goal_type: 'HOME_PURCHASE',
        mode: 'TARGET_AMOUNT',
        target_amount: '500000.00',
        target_currency: 'TRY',
        target_date: '2028-12-31',
        priority: 'ESSENTIAL',
        date_flexibility: 'LIMITED',
        amount_flexibility: 'FIXED',
        status: 'ACTIVE',
        current_funding: '200000.00',
        funded_ratio: 0.4,
        status_assessment: 'ON_TRACK',
        created_at: '2026-09-29T10:00:00Z',
        updated_at: '2026-09-29T10:00:00Z',
        mandates: [
          {
            id: 'mandate-1',
            user_id: 'user-1',
            goal_id: 'goal-1',
            name: 'Home Preservation Sleeve',
            mandate_type: 'PRESERVATION',
            risk_capacity: 'LOW',
            status: 'ACTIVE',
            target_allocation: {},
            concentration_limits: {},
            policy_rules: {},
            created_at: '2026-09-29T10:00:00Z',
            updated_at: '2026-09-29T10:00:00Z',
            assignments: [],
            total_assigned_value: '200000.00',
          },
        ],
      },
    ])

    vi.mocked(financialContextService.listMandates).mockResolvedValue([
      {
        id: 'mandate-1',
        user_id: 'user-1',
        goal_id: 'goal-1',
        name: 'Home Preservation Sleeve',
        mandate_type: 'PRESERVATION',
        risk_capacity: 'LOW',
        status: 'ACTIVE',
        target_allocation: {},
        concentration_limits: {},
        policy_rules: {},
        created_at: '2026-09-29T10:00:00Z',
        updated_at: '2026-09-29T10:00:00Z',
        assignments: [],
        total_assigned_value: '200000.00',
      },
    ])

    vi.mocked(financialContextService.getUnassignedResources).mockResolvedValue({
      assets: [
        {
          asset_id: 'asset-1',
          symbol: 'THYAO',
          name: 'Türk Hava Yolları',
          total_quantity: '1000',
          assigned_quantity: '400',
          unassigned_quantity: '600',
          currency: 'TRY',
        },
      ],
      cash_accounts: [
        {
          cash_account_id: 'cash-1',
          currency: 'TRY',
          total_balance: '200000.00',
          assigned_amount: '100000.00',
          unassigned_amount: '100000.00',
        },
      ],
    })

    render(
      <MemoryRouter>
        <FinancialProfilePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Finansal Profil, Hedefler ve Mandatler')).toBeInTheDocument()
      expect(screen.getByText('Home Down Payment')).toBeInTheDocument()
      expect(screen.getAllByText('Home Preservation Sleeve').length).toBeGreaterThan(0)
      expect(screen.getByText('5.4 Ay')).toBeInTheDocument()
    })
  })
})
