import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import OnboardingPage from './OnboardingPage'
import InvestorProfilePage from './InvestorProfilePage'
import InvestorProfileBanner from '@/components/dashboard/InvestorProfileBanner'
import { investorProfileService } from '@/services/investorProfileService'

vi.mock('@/components/layout/AppShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

vi.mock('@/services/investorProfileService', () => ({
  investorProfileService: {
    getQuestions: vi.fn(),
    getCurrentAssessment: vi.fn(),
    saveAnswer: vi.fn(),
    skipQuestion: vi.fn(),
    getDraft: vi.fn(),
    confirmProfile: vi.fn(),
    getCurrentProfile: vi.fn(),
    getVersions: vi.fn(),
  },
}))

describe('Phase 4: Investor Profile & Personalization', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  describe('OnboardingPage', () => {
    const mockQuestions = {
      sections: [
        {
          id: 'GOALS',
          title: 'Investment Horizon & Goals',
          description: 'Context',
          question_ids: ['C01'],
        },
      ],
      questions: [
        {
          id: 'C01',
          section: 'GOALS',
          layer: 'CORE',
          priority: 'MANDATORY',
          text: 'What is the primary objective for this portfolio?',
          helper_text: 'Choose the option that best fits your goals.',
          question_type: 'single_choice',
          options: [
            { code: 'WEALTH_ACCUMULATION', label: 'Wealth Accumulation', description: 'Long term growth' },
            { code: 'INCOME_GENERATION', label: 'Income Generation', description: 'Regular cash flow' },
          ],
        },
      ],
    }

    it('renders questions, allows option selection, and advances', async () => {
      vi.mocked(investorProfileService.getQuestions).mockResolvedValue(mockQuestions as any)
      vi.mocked(investorProfileService.getCurrentAssessment).mockResolvedValue({
        id: 'asmt-1',
        user_id: 'user-1',
        status: 'IN_PROGRESS',
        questionnaire_version: 'v1',
        answers: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      vi.mocked(investorProfileService.saveAnswer).mockResolvedValue({ status: 'ok' })

      render(
        <MemoryRouter>
          <OnboardingPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/What is the primary objective for this portfolio\?/i)).toBeInTheDocument()
      })

      expect(screen.getByText(/Wealth Accumulation/i)).toBeInTheDocument()
      expect(screen.getByText(/Investment Horizon & Goals/i)).toBeInTheDocument()

      // Select option
      fireEvent.click(screen.getByText(/Wealth Accumulation/i))

      // Click Continue
      const continueBtn = screen.getByRole('button', { name: /Continue/i })
      fireEvent.click(continueBtn)

      await waitFor(() => {
        expect(investorProfileService.saveAnswer).toHaveBeenCalledWith(
          expect.objectContaining({
            question_id: 'C01',
            selected_options: ['WEALTH_ACCUMULATION'],
          })
        )
      })
    })

    it('allows skipping question', async () => {
      vi.mocked(investorProfileService.getQuestions).mockResolvedValue(mockQuestions as any)
      vi.mocked(investorProfileService.getCurrentAssessment).mockResolvedValue({
        id: 'asmt-1',
        user_id: 'user-1',
        status: 'IN_PROGRESS',
        questionnaire_version: 'v1',
        answers: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      vi.mocked(investorProfileService.skipQuestion).mockResolvedValue({ status: 'skipped' })
      vi.mocked(investorProfileService.getDraft).mockResolvedValue({
        id: 'draft-1',
        user_id: 'user-1',
        goals: { items: [{ kind: 'GROW' }] },
        risk: { tolerance_summary: 'MODERATE', capacity_by_goal: [{ status: 'CONDITIONAL', reason_codes: [] }] },
        policy: { restriction_topics: [] },
        preferences: {},
        issues: [],
        completeness: { overall_pct: 10, domains: {}, missing_field_paths: [] },
        readiness: {
          risk_analysis: 'LIMITED',
          capacity_analysis: 'LIMITED',
          copilot_support: 'READY',
        },
      } as any)

      render(
        <MemoryRouter>
          <OnboardingPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/What is the primary objective/i)).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Skip question/i }))

      await waitFor(() => {
        expect(investorProfileService.skipQuestion).toHaveBeenCalledWith('C01')
      })
    })

    it('confirms profile and presents portfolio handoff modal with choices', async () => {
      vi.mocked(investorProfileService.getQuestions).mockResolvedValue(mockQuestions as any)
      vi.mocked(investorProfileService.getCurrentAssessment).mockResolvedValue({
        id: 'asmt-1',
        user_id: 'user-1',
        status: 'IN_PROGRESS',
        questionnaire_version: 'v1',
        answers: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      vi.mocked(investorProfileService.getDraft).mockResolvedValue({
        id: 'draft-1',
        user_id: 'user-1',
        goals: { items: [{ kind: 'GROW' }] },
        risk: { tolerance_summary: 'HIGH', capacity_by_goal: [{ status: 'UNCONSTRAINED', reason_codes: ['HORIZON_LONG'] }] },
        policy: { restriction_topics: [] },
        preferences: {},
        issues: [],
        completeness: { overall_pct: 85, domains: {}, missing_field_paths: [] },
        readiness: {
          risk_analysis: 'READY',
          capacity_analysis: 'READY',
          copilot_support: 'READY',
        },
      } as any)
      vi.mocked(investorProfileService.confirmProfile).mockResolvedValue({ version_number: 1 })

      render(
        <MemoryRouter>
          <OnboardingPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Preview Draft/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Preview Draft/i }))

      await waitFor(() => {
        expect(screen.getByText(/Your Investor Profile — Draft/i)).toBeInTheDocument()
      })

      // Confirm profile
      const confirmBtns = screen.getAllByRole('button', { name: /Confirm Profile/i })
      fireEvent.click(confirmBtns[0])

      await waitFor(() => {
        expect(screen.getByText(/Investor Profile Confirmed \(v1\)/i)).toBeInTheDocument()
        expect(screen.getByText(/Tell in Copilot Chat/i)).toBeInTheDocument()
        expect(screen.getByText(/Import CSV File/i)).toBeInTheDocument()
        expect(screen.getByText(/Upload Screenshot/i)).toBeInTheDocument()
      })
    })

    it('allows navigating to Financial Context and Goal Discovery steps in onboarding', async () => {
      vi.mocked(investorProfileService.getQuestions).mockResolvedValue(mockQuestions as any)
      vi.mocked(investorProfileService.getCurrentAssessment).mockResolvedValue({
        id: 'asmt-1',
        user_id: 'user-1',
        status: 'IN_PROGRESS',
        questionnaire_version: 'v1',
        answers: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      render(
        <MemoryRouter>
          <OnboardingPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/1\. Financial Context/i)).toBeInTheDocument()
      })

      // Click Financial Context tab
      fireEvent.click(screen.getByText(/1\. Financial Context/i))

      expect(screen.getByText(/Financial Context & Cash Flow/i)).toBeInTheDocument()
      expect(screen.getByText(/Monthly Net Income/i)).toBeInTheDocument()
      expect(screen.getByText(/Skip Financial Context/i)).toBeInTheDocument()

      // Click Skip Financial Context -> navigates to Goal Discovery
      fireEvent.click(screen.getByText(/Skip Financial Context/i))

      expect(screen.getByText(/Your Financial Goals/i)).toBeInTheDocument()
      expect(screen.getByText(/Retirement Fund/i)).toBeInTheDocument()
      expect(screen.getByText(/Skip Goals/i)).toBeInTheDocument()

      // Click Skip Goals -> returns to Assessment
      fireEvent.click(screen.getByText(/Skip Goals/i))

      await waitFor(() => {
        expect(screen.getByText(/What is the primary objective for this portfolio\?/i)).toBeInTheDocument()
      })
    })
  })

  describe('InvestorProfilePage', () => {
    it('renders separate tolerance and capacity cards and contradiction alert X01', async () => {
      vi.mocked(investorProfileService.getCurrentProfile).mockResolvedValue({
        id: 'prof-1',
        user_id: 'user-1',
        version_number: 1,
        completeness_overall_pct: 85,
        analysis_readiness: {
          risk_analysis: 'READY',
          capacity_analysis: 'READY',
          copilot_support: 'READY',
        } as any,
        goals: { items: [{ kind: 'WEALTH_ACCUMULATION', horizon: 'H5_10' }] },
        risk: {
          tolerance_summary: 'HIGH',
          drawdown_comfort: 'P40_PLUS',
          stress_response: 'BUY_MORE',
          capacity_by_goal: [{ status: 'CONSTRAINED', reason_codes: ['WITHDRAWAL_NEAR_TERM_FIXED'] }],
        },
        policy: { restriction_topics: ['TOBACCO', 'GAMBLING'] },
        preferences: { involvement: 'COLLABORATIVE' },
        issues: [
          {
            id: 'iss-1',
            rule_id: 'X01',
            field_paths: ['risk.drawdown_comfort', 'goals.withdrawals'],
            severity: 'WARNING',
            state: 'ACTIVE',
            explanation: 'High drawdown tolerance (40%+) conflicts with near-term fixed liquidity withdrawals.',
          },
        ],
        confirmed_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      vi.mocked(investorProfileService.getVersions).mockResolvedValue([
        {
          id: 'ver-1',
          version_number: 1,
          change_reason: 'Onboarding complete',
          change_source: 'ONBOARDING',
          confirmed_at: new Date().toISOString(),
        },
      ])

      render(
        <MemoryRouter>
          <InvestorProfilePage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/Version 1/i)).toBeInTheDocument()
      })

      // Psychological tolerance
      expect(screen.getByText(/Psychological Risk Tolerance/i)).toBeInTheDocument()
      expect(screen.getByText(/Emotional comfort with volatility/i)).toBeInTheDocument()

      // Financial risk capacity
      expect(screen.getByText(/Financial Risk Capacity/i)).toBeInTheDocument()
      expect(screen.getByText(/Practical ability to absorb loss/i)).toBeInTheDocument()
      expect(screen.getAllByText(/CONSTRAINED/i).length).toBeGreaterThanOrEqual(1)

      // Contradiction X01 banner
      expect(screen.getByText(/Risk Contradiction Detected: Tolerance vs Capacity Divergence \(X01\)/i)).toBeInTheDocument()
      expect(screen.getByText(/High drawdown tolerance \(40%\+\) conflicts with near-term fixed liquidity withdrawals/i)).toBeInTheDocument()
    })
  })

  describe('InvestorProfileBanner', () => {
    it('renders incomplete banner when user has no confirmed profile', async () => {
      vi.mocked(investorProfileService.getCurrentProfile).mockResolvedValue({
        id: 'prof-empty',
        user_id: 'user-1',
        version_number: undefined,
        completeness_overall_pct: 10,
        analysis_readiness: {} as any,
        goals: {},
        risk: {},
        policy: {},
        preferences: {},
        issues: [],
        updated_at: new Date().toISOString(),
      })

      render(
        <MemoryRouter>
          <InvestorProfileBanner />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/Personalize PortfolioMind with your Investor Profile/i)).toBeInTheDocument()
        expect(screen.getByText(/Start Assessment/i)).toBeInTheDocument()
      })
    })

    it('renders policy alert banner when X01 contradiction is active', async () => {
      vi.mocked(investorProfileService.getCurrentProfile).mockResolvedValue({
        id: 'prof-1',
        user_id: 'user-1',
        version_number: 1,
        completeness_overall_pct: 85,
        analysis_readiness: {} as any,
        goals: {},
        risk: {},
        policy: {},
        preferences: {},
        issues: [
          {
            id: 'x01',
            rule_id: 'X01',
            field_paths: [],
            severity: 'WARNING',
            state: 'ACTIVE',
            explanation: 'Divergence detected',
          },
        ],
        updated_at: new Date().toISOString(),
      })

      render(
        <MemoryRouter>
          <InvestorProfileBanner />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/Risk Tolerance vs Capacity divergence detected/i)).toBeInTheDocument()
        expect(screen.getByText(/Review Policy/i)).toBeInTheDocument()
      })
    })
  })
})
