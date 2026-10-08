import { useMemo } from 'react'

import AllocationChart from '@/components/dashboard/AllocationChart'
import NeedsAttentionSection from '@/components/dashboard/NeedsAttentionSection'
import PortfolioPulse from '@/components/dashboard/PortfolioPulse'
import PortfolioRiskCard from '@/components/dashboard/PortfolioRiskCard'
import RecentJournalCard from '@/components/dashboard/RecentJournalCard'
import ResearchQueueCard from '@/components/dashboard/ResearchQueueCard'
import SummaryCards from '@/components/dashboard/SummaryCards'
import UpcomingEventsCard from '@/components/dashboard/UpcomingEventsCard'
import WatchlistCard from '@/components/dashboard/WatchlistCard'
import InvestorProfileBanner from '@/components/dashboard/InvestorProfileBanner'
import AppShell from '@/components/layout/AppShell'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAssets } from '@/hooks/useAssets'
import { useBriefing } from '@/hooks/useBriefing'
import { useDashboardAllocation, useDashboardSummary } from '@/hooks/useDashboard'
import { useDecisions } from '@/hooks/useDecisions'
import { useForexRates } from '@/hooks/useForexRates'
import { useAuthStore } from '@/store'
import { useDashboardStore } from '@/store/dashboardStore'

export default function DashboardPage() {
  const summary = useDashboardSummary()
  const allocation = useDashboardAllocation()
  const { assets, isLoading: assetsLoading } = useAssets()
  const { briefing, stats: briefingStats } = useBriefing()
  const { decisions } = useDecisions({ limit: 5 })
  const { currency } = useDashboardStore()
  const { rates } = useForexRates()
  const { user } = useAuthStore()

  const financialError = summary.error ?? allocation.error

  const { dateStr, greeting } = useMemo(() => {
    const now = new Date()
    const dStr = new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(now)

    const hour = now.getHours()
    const timeOfDay = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
    const name = user?.display_name ?? user?.email?.split('@')[0] ?? 'there'

    return {
      dateStr: dStr,
      greeting: `${timeOfDay}, ${name}.`,
    }
  }, [user])

  return (
    <AppShell>
      <div className="app-page dashboard-page">
        {/* Header with Title and Date/Greeting */}
        <div className="flex flex-col gap-3 pb-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Your portfolio at a glance. Smarter insights for better decisions.
            </p>
          </div>

          <div className="flex min-w-0 flex-col gap-1 text-left sm:max-w-[40%] sm:items-end sm:text-right">
            <span className="text-xs font-medium text-foreground/80">{dateStr}</span>
            <span className="text-xs text-muted-foreground">{greeting}</span>
          </div>
        </div>

        {/* Investor Profile Setup & Alignment Banner */}
        <InvestorProfileBanner />

        {/* Row 1: Portfolio Pulse Attention Layer (4 metric cards) */}
        <PortfolioPulse
          assets={assets}
          allocation={allocation.data}
          isLoading={assetsLoading || allocation.isLoading}
          briefingAttentionCount={briefingStats?.attention_count ?? (briefing?.items.filter(i => i.review_required).length ?? 0)}
        />

        {financialError ? (
          <Card role="alert">
            <CardHeader>
              <CardTitle>Financial totals unavailable</CardTitle>
              <CardDescription>{financialError}</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <>
            {/* Row 2: Master Financial Hero (left 7-8 cols) + Portfolio Allocation (right 4-5 cols) */}
            <div className="dashboard-portfolio-grid grid min-w-0 grid-cols-1 items-stretch gap-4">
              <div className="flex min-w-0 flex-col">
                <SummaryCards
                  data={summary.data}
                  isLoading={summary.isLoading}
                  currency={currency}
                  rates={rates}
                />
              </div>
              <div className="flex min-w-0 flex-col">
                <AllocationChart
                  data={allocation.data}
                  isLoading={allocation.isLoading}
                  currency={currency}
                  rates={rates}
                />
              </div>
            </div>

            {/* Row 3: Action & Attention Grid (3 equal columns) */}
            <div className="dashboard-bottom-grid grid min-w-0 grid-cols-1 items-stretch gap-4">
              <NeedsAttentionSection
                assets={assets}
                isLoading={assetsLoading}
                briefingItems={briefing?.items ?? []}
              />
              <ResearchQueueCard assets={assets} isLoading={assetsLoading} />
              <UpcomingEventsCard assets={assets} isLoading={assetsLoading} />
            </div>

            {/* Row 4: Watchlist, Context & Decisions Grid (3 equal columns) */}
            <div className="dashboard-bottom-grid grid min-w-0 grid-cols-1 items-stretch gap-4">
              <WatchlistCard />
              <PortfolioRiskCard allocation={allocation.data} summary={summary.data} />
              <RecentJournalCard decisions={decisions} />
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}
