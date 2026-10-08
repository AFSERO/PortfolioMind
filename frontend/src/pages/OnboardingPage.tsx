import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  AlertTriangle,
  Upload,
  MessageSquare,
  FileSpreadsheet,
  Layers,
  ChevronRight,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { financialContextService } from '@/services/financialContextService'
import {
  investorProfileService,
  type QuestionCatalogResponse,
} from '@/services/investorProfileService'
import type {
  InvestorProfileDraft,
  QuestionDefinition,
} from '@/types/investorProfile'

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [catalog, setCatalog] = useState<QuestionCatalogResponse | null>(null)
  const [sectionTab, setSectionTab] = useState<'FINANCIAL_CONTEXT' | 'GOAL_DISCOVERY' | 'ASSESSMENT'>('ASSESSMENT')
  
  // Financial Context Onboarding State
  const [monthlyIncome, setMonthlyIncome] = useState('')
  const [essentialExpenses, setEssentialExpenses] = useState('')
  const [incomeStability, setIncomeStability] = useState<'PREDICTABLE' | 'VARIABLE' | 'AT_RISK' | 'UNKNOWN'>('UNKNOWN')
  
  // Goal Discovery State
  const [selectedGoals, setSelectedGoals] = useState<string[]>([])
  const [goalTargets, setGoalTargets] = useState<Record<string, string>>({})

  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [rawText, setRawText] = useState('')
  const [showOtherText, setShowOtherText] = useState(false)
  const [isReviewMode, setIsReviewMode] = useState(false)
  const [draft, setDraft] = useState<InvestorProfileDraft | null>(null)
  const [confirmedVersion, setConfirmedVersion] = useState<number | null>(null)
  const [showHandoffModal, setShowHandoffModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const cat = await investorProfileService.getQuestions()
      setCatalog(cat)
      const asmt = await investorProfileService.getCurrentAssessment()
      if (asmt.resume_question_id) {
        const idx = cat.questions.findIndex((q) => q.id === asmt.resume_question_id)
        if (idx >= 0) setCurrentIndex(idx)
      }
    } catch (err: any) {
      toast.error('Could not load assessment: ' + (err.message || 'Error'))
    } finally {
      setLoading(false)
    }
  }

  const currentQ: QuestionDefinition | undefined = catalog?.questions[currentIndex]

  // Reset form selections on question step change
  useEffect(() => {
    setSelectedOptions([])
    setRawText('')
    setShowOtherText(false)
  }, [currentIndex])

  const handleOptionToggle = (code: string, exclusive?: boolean) => {
    if (exclusive) {
      setSelectedOptions([code])
      setShowOtherText(false)
      return
    }

    if (currentQ?.question_type === 'single_choice') {
      setSelectedOptions([code])
      return
    }

    // Multi-choice
    let updated = selectedOptions.filter((c) => c !== 'NONE')
    if (updated.includes(code)) {
      updated = updated.filter((c) => c !== code)
    } else {
      updated.push(code)
    }
    setSelectedOptions(updated)
  }

  const handleSaveAndNext = async () => {
    if (!currentQ) return

    try {
      await investorProfileService.saveAnswer({
        question_id: currentQ.id,
        knowledge_state: selectedOptions.length > 0 ? 'KNOWN' : 'DECLINED',
        selected_options: selectedOptions,
        raw_text: rawText || undefined,
      })

      if (catalog && currentIndex < catalog.questions.length - 1) {
        setCurrentIndex(currentIndex + 1)
      } else {
        await openReview()
      }
    } catch (err: any) {
      toast.error('Failed to save answer: ' + err.message)
    }
  }

  const handleSkipQuestion = async () => {
    if (!currentQ) return
    try {
      await investorProfileService.skipQuestion(currentQ.id)
      if (catalog && currentIndex < catalog.questions.length - 1) {
        setCurrentIndex(currentIndex + 1)
      } else {
        await openReview()
      }
    } catch (err: any) {
      toast.error('Failed to skip: ' + err.message)
    }
  }

  const handleSaveFinancialContext = async () => {
    try {
      const payload: any = {}
      if (monthlyIncome.trim()) payload.monthly_net_income = monthlyIncome.trim()
      if (essentialExpenses.trim()) payload.monthly_essential_expenses = essentialExpenses.trim()
      if (incomeStability && incomeStability !== 'UNKNOWN') payload.income_stability = incomeStability
      if (Object.keys(payload).length > 0 && financialContextService?.updateFinancialContext) {
        await financialContextService.updateFinancialContext(payload)
        toast.success('Financial context updated')
      }
    } catch (err: any) {
      console.error('Failed to update financial context:', err)
    }
    setSectionTab('GOAL_DISCOVERY')
  }

  const handleSkipFinancialContext = () => {
    setSectionTab('GOAL_DISCOVERY')
  }

  const toggleGoal = (goalKey: string) => {
    if (selectedGoals.includes(goalKey)) {
      setSelectedGoals(selectedGoals.filter((g) => g !== goalKey))
    } else {
      setSelectedGoals([...selectedGoals, goalKey])
    }
  }

  const handleSaveGoals = async () => {
    try {
      if (financialContextService?.createGoal) {
        for (const gType of selectedGoals) {
          const tgt = goalTargets[gType]
          const nameMap: Record<string, string> = {
            RETIREMENT: 'Retirement Fund',
            HOME_PURCHASE: 'Home Downpayment',
            WEALTH_GROWTH: 'Wealth Accumulation',
            EMERGENCY_RESERVE: 'Emergency Runway',
            FINANCIAL_INDEPENDENCE: 'Financial Independence',
          }
          await financialContextService.createGoal({
            name: nameMap[gType] || 'Financial Goal',
            goal_type: gType as any,
            target_amount: tgt ? tgt : null,
            target_currency: 'TRY',
          })
        }
        if (selectedGoals.length > 0) {
          toast.success('Goals created successfully')
        }
      }
    } catch (err: any) {
      console.error('Failed to create goals:', err)
    }
    setSectionTab('ASSESSMENT')
  }

  const handleSkipGoals = () => {
    setSectionTab('ASSESSMENT')
  }


  const openReview = async () => {
    try {
      setLoading(true)
      const d = await investorProfileService.getDraft()
      setDraft(d)
      setIsReviewMode(true)
    } catch (err: any) {
      toast.error('Failed to load profile draft: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmProfile = async () => {
    try {
      setLoading(true)
      const res = await investorProfileService.confirmProfile('Onboarding profile completed', 'ONBOARDING')
      setConfirmedVersion(res.version_number || 1)
      setShowHandoffModal(true)
      toast.success('Investor profile confirmed successfully!')
    } catch (err: any) {
      toast.error('Failed to confirm profile: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !catalog) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading investor assessment...</p>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Post-Confirmation Handoff Modal
  // ---------------------------------------------------------------------------
  if (showHandoffModal) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background/95 p-4">
        <Card className="max-w-xl border-border/60 shadow-2xl">
          <CardHeader className="text-center pb-3">
            <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
              <CheckCircle className="h-6 w-6" />
            </div>
            <CardTitle className="text-2xl font-bold tracking-tight">
              Investor Profile Confirmed (v{confirmedVersion})
            </CardTitle>
            <CardDescription className="text-sm">
              Your investment goals, risk tolerance, and constraints are now safely recorded.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-2">
            <div className="rounded-lg border border-border/40 bg-muted/20 p-4">
              <h4 className="font-semibold text-sm mb-1 text-foreground">
                Would you like to add your current portfolio now?
              </h4>
              <p className="text-xs text-muted-foreground">
                PortfolioMind can immediately analyze your holdings against your newly confirmed Investor Profile.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <Button
                variant="outline"
                className="justify-start gap-2.5 h-12 text-left"
                onClick={() => navigate('/copilot?intent=portfolio_import')}
              >
                <MessageSquare className="h-4 w-4 text-primary" />
                <div>
                  <div className="text-xs font-semibold">Tell in Copilot Chat</div>
                  <div className="text-[10px] text-muted-foreground">Type or paste what you hold</div>
                </div>
              </Button>

              <Button
                variant="outline"
                className="justify-start gap-2.5 h-12 text-left"
                onClick={() => navigate('/copilot?action=import_csv')}
              >
                <FileSpreadsheet className="h-4 w-4 text-emerald-500" />
                <div>
                  <div className="text-xs font-semibold">Import CSV File</div>
                  <div className="text-[10px] text-muted-foreground">Broker export spreadsheet</div>
                </div>
              </Button>

              <Button
                variant="outline"
                className="justify-start gap-2.5 h-12 text-left opacity-80"
                onClick={() => {
                  toast.info(
                    'Screenshot vision OCR provider is not configured in this environment. Please use CSV or natural-language chat.',
                    { duration: 4500 }
                  )
                }}
              >
                <Upload className="h-4 w-4 text-amber-500" />
                <div>
                  <div className="text-xs font-semibold">Upload Screenshot</div>
                  <div className="text-[10px] text-muted-foreground">Vision OCR (Notice)</div>
                </div>
              </Button>

              <Button
                variant="outline"
                className="justify-start gap-2.5 h-12 text-left"
                onClick={() => navigate('/dashboard')}
              >
                <Layers className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-xs font-semibold">Skip for now</div>
                  <div className="text-[10px] text-muted-foreground">Go directly to Dashboard</div>
                </div>
              </Button>
            </div>
          </CardContent>
          <CardFooter className="flex justify-between border-t border-border/40 pt-4">
            <span className="text-xs text-muted-foreground">You can import assets anytime from the dashboard.</span>
            <Button variant="default" onClick={() => navigate('/dashboard')}>
              Go to Dashboard
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Review Draft Screen
  // ---------------------------------------------------------------------------
  if (isReviewMode && draft) {
    const x01Issue = draft.issues.find((i) => i.rule_id === 'X01')

    return (
      <div className="min-h-screen bg-background text-foreground py-10 px-4">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border/40 pb-5">
            <div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-xs">
                  Review & Confirm
                </Badge>
                <span className="text-xs text-muted-foreground">Investor Profile Draft</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight mt-1">Your Investor Profile — Draft</h1>
              <p className="text-xs text-muted-foreground">
                Check what we understood. Missing answers can stay missing and be updated anytime.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsReviewMode(false)}>
                Back to Questions
              </Button>
              <Button variant="default" size="sm" onClick={handleConfirmProfile}>
                Confirm Profile
              </Button>
            </div>
          </div>

          {/* Completeness & Readiness Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Card className="border-border/60">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold flex items-center justify-between">
                  <span>Core Information Coverage</span>
                  <span className="text-primary font-mono text-base">{draft.completeness.overall_pct}%</span>
                </CardTitle>
                <Progress value={draft.completeness.overall_pct} className="h-2 mt-1" />
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground space-y-1">
                <div className="flex justify-between">
                  <span>Goals & Horizon:</span>
                  <span className="font-mono text-foreground">{draft.completeness.domains.goals_context || 0} / 20 pts</span>
                </div>
                <div className="flex justify-between">
                  <span>Risk Tolerance:</span>
                  <span className="font-mono text-foreground">{draft.completeness.domains.tolerance || 0} / 20 pts</span>
                </div>
                <div className="flex justify-between">
                  <span>Resilience & Capacity:</span>
                  <span className="font-mono text-foreground">{draft.completeness.domains.resilience || 0} / 25 pts</span>
                </div>
                <div className="flex justify-between">
                  <span>Liquidity:</span>
                  <span className="font-mono text-foreground">{draft.completeness.domains.liquidity || 0} / 20 pts</span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/60">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Capability Readiness</CardTitle>
                <CardDescription className="text-xs">Analytical features supported by your profile</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded border border-border/30 p-2 flex flex-col justify-between">
                  <span className="text-muted-foreground text-[11px]">Risk Analysis</span>
                  <Badge variant={draft.readiness.risk_analysis === 'READY' ? 'default' : 'secondary'} className="w-fit text-[10px] mt-1">
                    {draft.readiness.risk_analysis}
                  </Badge>
                </div>
                <div className="rounded border border-border/30 p-2 flex flex-col justify-between">
                  <span className="text-muted-foreground text-[11px]">Capacity Analysis</span>
                  <Badge variant={draft.readiness.capacity_analysis === 'READY' ? 'default' : 'secondary'} className="w-fit text-[10px] mt-1">
                    {draft.readiness.capacity_analysis}
                  </Badge>
                </div>
                <div className="rounded border border-border/30 p-2 flex flex-col justify-between">
                  <span className="text-muted-foreground text-[11px]">Liquidity Needs</span>
                  <Badge variant={draft.readiness.liquidity_analysis === 'READY' ? 'default' : 'secondary'} className="w-fit text-[10px] mt-1">
                    {draft.readiness.liquidity_analysis}
                  </Badge>
                </div>
                <div className="rounded border border-border/30 p-2 flex flex-col justify-between">
                  <span className="text-muted-foreground text-[11px]">Copilot Support</span>
                  <Badge variant="default" className="w-fit text-[10px] mt-1">
                    {draft.readiness.copilot_support}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Contradiction Warning Banner (Rule X01 etc.) */}
          {x01Issue && (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-amber-200">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-400 mt-0.5 shrink-0" />
                <div className="text-xs space-y-1">
                  <div className="font-semibold text-amber-300">
                    Important Insight: Tolerance vs Capacity Divergence (X01)
                  </div>
                  <p className="text-amber-200/90 leading-relaxed">{x01Issue.explanation}</p>
                </div>
              </div>
            </div>
          )}

          {/* Section Breakdown Cards */}
          <div className="space-y-4">
            {/* Goals & Horizon */}
            <Card className="border-border/60">
              <CardHeader className="py-3 px-4 border-b border-border/30">
                <CardTitle className="text-sm font-semibold flex items-center justify-between">
                  <span>1. Goals & Financial Context</span>
                  <Badge variant="outline" className="text-[11px]">
                    {draft.goals.items[0]?.kind || 'GROW'}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="py-3 px-4 text-xs space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-muted-foreground">Time Horizon: </span>
                    <span className="font-medium text-foreground">{draft.goals.items[0]?.horizon || 'Not specified'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Goal Flexibility: </span>
                    <span className="font-medium text-foreground">{draft.goals.items[0]?.flexibility || 'Not specified'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">3-Year Withdrawals: </span>
                    <span className="font-medium text-foreground">{draft.goals.withdrawal_pattern || 'None'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Emergency Reserve: </span>
                    <span className="font-medium text-foreground">{draft.goals.reserve_months_band || 'Not specified'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Risk Profile: Tolerance vs Capacity */}
            <Card className="border-border/60">
              <CardHeader className="py-3 px-4 border-b border-border/30">
                <CardTitle className="text-sm font-semibold">2. Risk Profile (Tolerance & Capacity Separated)</CardTitle>
              </CardHeader>
              <CardContent className="py-3 px-4 text-xs space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-md border border-border/40 p-3 bg-muted/10">
                    <span className="text-[11px] font-semibold text-primary uppercase tracking-wide">
                      Psychological Risk Tolerance
                    </span>
                    <div className="text-base font-bold mt-1 text-foreground">
                      {draft.risk.tolerance_summary}
                    </div>
                    <div className="text-muted-foreground text-[11px] mt-0.5">
                      Stated drawdown comfort: {draft.risk.drawdown_comfort || 'Not specified'}
                    </div>
                  </div>

                  <div className="rounded-md border border-border/40 p-3 bg-muted/10">
                    <span className="text-[11px] font-semibold text-emerald-500 uppercase tracking-wide">
                      Financial Risk Capacity
                    </span>
                    <div className="text-base font-bold mt-1 text-foreground">
                      {draft.risk.capacity_by_goal[0]?.status || 'CONDITIONAL'}
                    </div>
                    <div className="text-muted-foreground text-[11px] mt-0.5">
                      {draft.risk.capacity_by_goal[0]?.reason_codes[0] || 'Evaluated per goal requirements'}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Policy & Preferences */}
            <Card className="border-border/60">
              <CardHeader className="py-3 px-4 border-b border-border/30">
                <CardTitle className="text-sm font-semibold">3. Investment Policy & Preferences</CardTitle>
              </CardHeader>
              <CardContent className="py-3 px-4 text-xs space-y-2">
                <div>
                  <span className="text-muted-foreground">Excluded Topics: </span>
                  <span className="font-medium text-foreground">
                    {draft.policy.restriction_topics.length > 0 ? draft.policy.restriction_topics.join(', ') : 'None'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Decision Involvement: </span>
                  <span className="font-medium text-foreground">{draft.preferences.involvement || 'Standard'}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-between items-center pt-4">
            <Button variant="ghost" onClick={() => navigate('/dashboard')}>
              Skip and go to Dashboard
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setIsReviewMode(false)}>
                Back to Questions
              </Button>
              <Button variant="default" onClick={handleConfirmProfile}>
                Confirm Profile (v1)
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Step-by-Step Question Flow
  // ---------------------------------------------------------------------------
  const currentSection = catalog?.sections.find((s) => s.id === currentQ?.section)
  const progressPct = catalog ? ((currentIndex + 1) / catalog.questions.length) * 100 : 0

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between py-10 px-4">
      <div className="mx-auto max-w-2xl w-full space-y-6">
        {/* Onboarding Stage Stepper */}
        <div className="flex items-center justify-between border-b border-border/40 pb-4 mb-2">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <button
              type="button"
              onClick={() => setSectionTab('FINANCIAL_CONTEXT')}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                sectionTab === 'FINANCIAL_CONTEXT'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'bg-muted/40 text-muted-foreground hover:text-foreground'
              }`}
            >
              1. Financial Context
            </button>
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40" />
            <button
              type="button"
              onClick={() => setSectionTab('GOAL_DISCOVERY')}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                sectionTab === 'GOAL_DISCOVERY'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'bg-muted/40 text-muted-foreground hover:text-foreground'
              }`}
            >
              2. Goals
            </button>
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40" />
            <button
              type="button"
              onClick={() => setSectionTab('ASSESSMENT')}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                sectionTab === 'ASSESSMENT'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'bg-muted/40 text-muted-foreground hover:text-foreground'
              }`}
            >
              3. Investor Assessment
            </button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground hover:text-foreground"
            onClick={() => navigate('/dashboard')}
          >
            Skip to Dashboard
          </Button>
        </div>

        {/* Step 1: Financial Context Card */}
        {sectionTab === 'FINANCIAL_CONTEXT' && (
          <Card className="border-border/60 shadow-lg">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-[10px]">
                  Step 1 of 3 (Optional)
                </Badge>
              </div>
              <CardTitle className="text-xl font-bold tracking-tight">Financial Context & Cash Flow</CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-1">
                Sharing your monthly income and baseline expenses helps PortfolioMind accurately derive your savings rate, emergency runway, and debt capacity. You can leave fields blank or skip this step entirely.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-foreground">Monthly Net Income (TRY)</label>
                  <Input
                    type="number"
                    placeholder="e.g. 100000"
                    value={monthlyIncome}
                    onChange={(e) => setMonthlyIncome(e.target.value)}
                    className="text-xs"
                  />
                  <p className="text-[10px] text-muted-foreground">Take-home earnings after taxes.</p>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-foreground">Monthly Essential Expenses (TRY)</label>
                  <Input
                    type="number"
                    placeholder="e.g. 65000"
                    value={essentialExpenses}
                    onChange={(e) => setEssentialExpenses(e.target.value)}
                    className="text-xs"
                  />
                  <p className="text-[10px] text-muted-foreground">Housing, groceries, bills & obligations.</p>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-border/30">
                <label className="text-xs font-semibold text-foreground">Income Predictability</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { key: 'PREDICTABLE', label: 'Predictable', desc: 'Salaried / Steady' },
                    { key: 'VARIABLE', label: 'Variable', desc: 'Bonus / Freelance' },
                    { key: 'AT_RISK', label: 'At Risk', desc: 'Volatile / Transition' },
                    { key: 'UNKNOWN', label: 'Prefer not to say', desc: 'Keep Unknown' },
                  ].map((s) => (
                    <button
                      key={s.key}
                      type="button"
                      onClick={() => setIncomeStability(s.key as any)}
                      className={`text-left rounded-lg border p-2.5 transition-all text-xs ${
                        incomeStability === s.key
                          ? 'border-primary bg-primary/10 text-foreground ring-1 ring-primary font-medium'
                          : 'border-border/50 bg-card hover:bg-muted/30 text-foreground/80'
                      }`}
                    >
                      <div className="font-semibold text-xs">{s.label}</div>
                      <div className="text-[10px] text-muted-foreground">{s.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between border-t border-border/40 pt-4">
              <Button variant="ghost" size="sm" onClick={handleSkipFinancialContext}>
                Skip Financial Context
              </Button>
              <Button variant="default" size="sm" onClick={handleSaveFinancialContext}>
                Continue to Goals
                <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Step 2: Goal Discovery Card */}
        {sectionTab === 'GOAL_DISCOVERY' && (
          <Card className="border-border/60 shadow-lg">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary text-[10px]">
                  Step 2 of 3 (Optional)
                </Badge>
              </div>
              <CardTitle className="text-xl font-bold tracking-tight">Your Financial Goals</CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-1">
                What are you investing for? Select the outcomes you're working towards. You can create as many goals and mandates as you wish later.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { key: 'RETIREMENT', title: 'Retirement Fund', desc: 'Long-term financial independence' },
                  { key: 'HOME_PURCHASE', title: 'Home Purchase', desc: 'Real estate down payment' },
                  { key: 'WEALTH_GROWTH', title: 'Wealth Growth', desc: 'General compounding and investing' },
                  { key: 'EMERGENCY_RESERVE', title: 'Emergency Reserve', desc: '3-6 months cash buffer' },
                ].map((g) => {
                  const isSelected = selectedGoals.includes(g.key)
                  return (
                    <div
                      key={g.key}
                      className={`rounded-lg border p-3 transition-all ${
                        isSelected
                          ? 'border-primary bg-primary/10 text-foreground ring-1 ring-primary'
                          : 'border-border/50 bg-card text-foreground/80'
                      }`}
                    >
                      <div className="flex items-center justify-between cursor-pointer" onClick={() => toggleGoal(g.key)}>
                        <div>
                          <div className="font-semibold text-xs text-foreground">{g.title}</div>
                          <div className="text-[10px] text-muted-foreground">{g.desc}</div>
                        </div>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleGoal(g.key)}
                          className="h-4 w-4 rounded border-border text-primary cursor-pointer"
                        />
                      </div>
                      {isSelected && (
                        <div className="mt-2.5 pt-2 border-t border-border/30">
                          <label className="text-[10px] text-muted-foreground">Target Amount (TRY, Optional)</label>
                          <Input
                            type="number"
                            placeholder="e.g. 2000000"
                            value={goalTargets[g.key] || ''}
                            onChange={(e) => setGoalTargets({ ...goalTargets, [g.key]: e.target.value })}
                            className="text-xs h-8 mt-1"
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </CardContent>
            <CardFooter className="flex justify-between border-t border-border/40 pt-4">
              <Button variant="outline" size="sm" onClick={() => setSectionTab('FINANCIAL_CONTEXT')}>
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={handleSkipGoals}>
                  Skip Goals
                </Button>
                <Button variant="default" size="sm" onClick={handleSaveGoals}>
                  Continue to Assessment
                  <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </CardFooter>
          </Card>
        )}

        {/* Step 3: Question Flow */}
        {sectionTab === 'ASSESSMENT' && (
          <>
            {/* Header & Progress */}
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  Question {currentIndex + 1} of {catalog?.questions.length}
                </span>
                <Button
                  variant="link"
                  className="text-xs text-muted-foreground hover:text-foreground p-0 h-auto"
                  onClick={() => navigate('/dashboard')}
                >
                  Skip assessment & go to Dashboard
                </Button>
              </div>
              <Progress value={progressPct} className="h-1.5" />
              <div className="text-xs font-semibold uppercase tracking-wider text-primary">
                {currentSection?.title || 'Investor Assessment'}
              </div>
            </div>

            {/* Question Card */}
            {currentQ && (
              <Card className="border-border/60 shadow-lg">
                <CardHeader className="pb-3">
                  <CardTitle className="text-xl font-bold tracking-tight">{currentQ.text}</CardTitle>
                  {currentQ.helper_text && (
                    <CardDescription className="text-xs text-muted-foreground mt-1">
                      {currentQ.helper_text}
                    </CardDescription>
                  )}
                </CardHeader>

                <CardContent className="space-y-3 pt-2">
                  <div className="grid grid-cols-1 gap-2.5">
                    {currentQ.options.map((opt) => {
                      const isSelected = selectedOptions.includes(opt.code)
                      return (
                        <button
                          key={opt.code}
                          type="button"
                          onClick={() => handleOptionToggle(opt.code, opt.exclusive)}
                          className={`text-left rounded-lg border p-3 transition-all flex items-start justify-between gap-3 ${
                            isSelected
                              ? 'border-primary bg-primary/10 text-foreground ring-1 ring-primary'
                              : 'border-border/50 bg-card hover:bg-muted/30 text-foreground/90'
                          }`}
                        >
                          <div>
                            <div className="text-sm font-semibold">{opt.label}</div>
                            {opt.description && (
                              <div className="text-xs text-muted-foreground mt-0.5">{opt.description}</div>
                            )}
                          </div>
                          <div
                            className={`h-4 w-4 rounded-full border mt-0.5 flex items-center justify-center shrink-0 ${
                              isSelected ? 'border-primary bg-primary' : 'border-muted-foreground/40'
                            }`}
                          >
                            {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-background" />}
                          </div>
                        </button>
                      )
                    })}
                  </div>

                  {/* Other / Explain my answer */}
                  {currentQ.has_other && (
                    <div className="pt-2">
                      {!showOtherText ? (
                        <Button
                          variant="link"
                          className="text-xs text-muted-foreground p-0 h-auto"
                          onClick={() => setShowOtherText(true)}
                        >
                          + Explain my answer / Add specific note
                        </Button>
                      ) : (
                        <div className="space-y-1.5">
                          <label className="text-xs text-muted-foreground">Optional note or specific details:</label>
                          <Textarea
                            placeholder="Add any specific context or clarification..."
                            value={rawText}
                            onChange={(e) => setRawText(e.target.value)}
                            className="text-xs h-20 resize-none bg-card border-border/50"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>

                <CardFooter className="flex justify-between border-t border-border/40 pt-4">
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentIndex === 0}
                      onClick={() => setCurrentIndex(currentIndex - 1)}
                    >
                      <ArrowLeft className="h-4 w-4 mr-1" />
                      Back
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleSkipQuestion}>
                      Skip question
                    </Button>
                  </div>

                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={openReview}>
                      Preview Draft
                    </Button>
                    <Button variant="default" size="sm" onClick={handleSaveAndNext}>
                      Continue
                      <ArrowRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </CardFooter>
              </Card>
            )}
          </>
        )}
      </div>

      <footer className="text-center text-[11px] text-muted-foreground/60 py-4">
        PortfolioMind personalizes risk and allocation analysis based on your stated preferences. You can edit this anytime.
      </footer>
    </div>
  )
}
