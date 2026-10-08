import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck,
  Compass,
  AlertTriangle,
  History,
  RefreshCw,
} from 'lucide-react'
import { toast } from 'sonner'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  investorProfileService,
} from '@/services/investorProfileService'
import type {
  InvestorProfileData,
  InvestorProfileVersionSummary,
  ProfileIssue,
} from '@/types/investorProfile'

export default function InvestorProfilePage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [profile, setProfile] = useState<InvestorProfileData | null>(null)
  const [versions, setVersions] = useState<InvestorProfileVersionSummary[]>([])
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    fetchProfileData()
  }, [])

  const fetchProfileData = async () => {
    try {
      setLoading(true)
      const [profData, verData] = await Promise.all([
        investorProfileService.getCurrentProfile().catch(() => null),
        investorProfileService.getVersions().catch(() => []),
      ])
      setProfile(profData)
      setVersions(verData)
    } catch (err: any) {
      toast.error('Failed to load profile: ' + (err.message || 'Error'))
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-96 items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
            <p className="text-xs text-muted-foreground">Loading investor profile...</p>
          </div>
        </div>
      </AppShell>
    )
  }

  const hasProfile = profile && profile.version_number
  const issues: ProfileIssue[] = profile?.issues || []
  const x01Issue = issues.find((i) => i.rule_id === 'X01')

  return (
    <AppShell>
      <div className="app-page max-w-5xl space-y-6">
        <PageHeader
          title="Investor Profile & Policy"
          description="Your personal investment profile, separate risk tolerance & capacity, investment policy rules, and version history."
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => navigate('/onboarding')}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {hasProfile ? 'Retake Assessment' : 'Start Assessment'}
              </Button>
            </div>
          }
        />

        {/* Unconfirmed / Incomplete Profile Notice */}
        {!hasProfile && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardHeader className="py-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <CardTitle className="text-sm font-semibold text-amber-500">
                    No Confirmed Investor Profile Found
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground mt-1">
                    You haven't completed or confirmed your profile assessment yet. Completing the 12-question assessment enables personalized risk analysis, asset suitability checks, and tailored Copilot insights.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardFooter className="py-2.5 px-6 border-t border-border/20 flex justify-end">
              <Button size="sm" onClick={() => navigate('/onboarding')}>
                Complete Assessment Now
              </Button>
            </CardFooter>
          </Card>
        )}

        {/* Top Summary Bar */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">
                Profile Status
              </div>
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <span>Version {profile?.version_number || 1}</span>
                <Badge variant={hasProfile ? 'default' : 'secondary'} className="text-[10px]">
                  {hasProfile ? 'Active & Confirmed' : 'Draft'}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {profile?.confirmed_at ? (
                <span>Confirmed on {new Date(profile.confirmed_at).toLocaleDateString()}</span>
              ) : (
                <span>Not formally confirmed yet</span>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider flex justify-between">
                <span>Profile Completeness</span>
                <span className="font-mono text-foreground font-bold">
                  {profile?.completeness_overall_pct || 0}%
                </span>
              </div>
              <Progress value={profile?.completeness_overall_pct || 0} className="h-2 mt-2" />
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Calculated across goals, tolerance, capacity, liquidity, and preferences.
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader className="pb-2">
              <div className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">
                Copilot Governance
              </div>
              <CardTitle className="text-xl font-bold flex items-center gap-1.5 text-emerald-500">
                <ShieldCheck className="h-5 w-5" />
                <span>Level 2 Protection</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              Conversational changes require explicit confirmation and produce auditable versions.
            </CardContent>
          </Card>
        </div>

        {/* Contradiction Warning (Rule X01 etc.) */}
        {x01Issue && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-amber-200">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-400 mt-0.5 shrink-0" />
              <div className="text-xs space-y-1">
                <div className="font-semibold text-amber-300">
                  Risk Contradiction Detected: Tolerance vs Capacity Divergence (X01)
                </div>
                <p className="text-amber-200/90 leading-relaxed">{x01Issue.explanation}</p>
                <div className="text-[11px] text-amber-300/80 pt-1 font-medium">
                  Recommendation: Stated risk appetite should not exceed near-term liquidity commitments. Consider allocating near-term needs to stable cash equivalents.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Distinct Risk Dimensions: Tolerance vs Capacity (Core Requirement) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card A: Psychological Risk Tolerance */}
          <Card className="border-border/60">
            <CardHeader className="pb-3 border-b border-border/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-primary/10 text-primary">
                    <Compass className="h-4 w-4" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-semibold">Psychological Risk Tolerance</CardTitle>
                    <CardDescription className="text-[11px]">Emotional comfort with volatility</CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className="font-semibold text-xs border-primary/40 text-primary">
                  {profile?.risk?.tolerance_summary || 'MODERATE'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-3 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded border border-border/30 bg-muted/10">
                  <span className="text-muted-foreground text-[10px] uppercase">Comfortable Drawdown</span>
                  <div className="text-sm font-bold text-foreground mt-0.5">
                    {profile?.risk?.drawdown_comfort || 'P15_25'}
                  </div>
                </div>
                <div className="p-2 rounded border border-border/30 bg-muted/10">
                  <span className="text-muted-foreground text-[10px] uppercase">Market Stress Reaction</span>
                  <div className="text-sm font-bold text-foreground mt-0.5">
                    {profile?.risk?.stress_response || 'HOLD'}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Represents your psychological threshold for enduring paper losses during adverse market cycles without panic selling.
              </p>
            </CardContent>
          </Card>

          {/* Card B: Financial Risk Capacity */}
          <Card className="border-border/60">
            <CardHeader className="pb-3 border-b border-border/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-500">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <div>
                    <CardTitle className="text-sm font-semibold">Financial Risk Capacity</CardTitle>
                    <CardDescription className="text-[11px]">Practical ability to absorb loss</CardDescription>
                  </div>
                </div>
                <Badge
                  variant={
                    profile?.risk?.capacity_by_goal?.[0]?.status === 'CONSTRAINED'
                      ? 'destructive'
                      : 'default'
                  }
                  className="font-semibold text-xs"
                >
                  {profile?.risk?.capacity_by_goal?.[0]?.status || 'CONDITIONAL'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-3 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded border border-border/30 bg-muted/10">
                  <span className="text-muted-foreground text-[10px] uppercase">Capacity Status</span>
                  <div className="text-sm font-bold text-foreground mt-0.5">
                    {profile?.risk?.capacity_by_goal?.[0]?.status || 'CONDITIONAL'}
                  </div>
                </div>
                <div className="p-2 rounded border border-border/30 bg-muted/10">
                  <span className="text-muted-foreground text-[10px] uppercase">Key Driver</span>
                  <div className="text-sm font-bold text-foreground mt-0.5">
                    {profile?.risk?.capacity_by_goal?.[0]?.reason_codes?.[0] || 'HORIZON_LONG'}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Determined by hard balance sheet factors: investment horizon, emergency liquidity buffer, and non-portfolio obligations.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Detailed Sections: Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid grid-cols-3 max-w-md">
            <TabsTrigger value="overview">Goals & Policy</TabsTrigger>
            <TabsTrigger value="readiness">Capability Readiness</TabsTrigger>
            <TabsTrigger value="history">Version History</TabsTrigger>
          </TabsList>

          {/* Tab 1: Goals & Policy */}
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Goals & Horizon */}
              <Card className="border-border/60">
                <CardHeader className="py-3 px-4 border-b border-border/30">
                  <CardTitle className="text-sm font-semibold">Goals & Financial Context</CardTitle>
                </CardHeader>
                <CardContent className="py-3 px-4 text-xs space-y-2">
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Primary Goal:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.goals?.items?.[0]?.kind || 'WEALTH_ACCUMULATION'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Investment Horizon:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.goals?.items?.[0]?.horizon || 'H5_10'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Goal Flexibility:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.goals?.items?.[0]?.flexibility || 'FLEXIBLE'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Withdrawal Expectation:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.goals?.withdrawal_pattern || 'NONE'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-muted-foreground">Emergency Reserve:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.goals?.reserve_months_band || 'M6_PLUS'}
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Investment Policy Statement (IPS) */}
              <Card className="border-border/60">
                <CardHeader className="py-3 px-4 border-b border-border/30">
                  <CardTitle className="text-sm font-semibold">Investment Policy Statement (IPS)</CardTitle>
                </CardHeader>
                <CardContent className="py-3 px-4 text-xs space-y-2">
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Allocation Mode:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.policy?.allocation_mode || 'STRATEGIC'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Decision Involvement:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.preferences?.involvement || 'COLLABORATIVE'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/20">
                    <span className="text-muted-foreground">Excluded Assets/Sectors:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.policy?.restriction_topics?.length
                        ? profile.policy.restriction_topics.join(', ')
                        : 'None'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-muted-foreground">Explanation Depth:</span>
                    <span className="font-semibold text-foreground">
                      {profile?.preferences?.explanation_depth || 'BALANCED'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Tab 2: Capability Readiness */}
          <TabsContent value="readiness" className="space-y-4">
            <Card className="border-border/60">
              <CardHeader className="pb-3 border-b border-border/30">
                <CardTitle className="text-sm font-semibold">Capability Readiness Breakdown</CardTitle>
                <CardDescription className="text-xs">
                  How your profile data enables different analytical capabilities across PortfolioMind.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                {profile?.analysis_readiness &&
                  Object.entries(profile.analysis_readiness).map(([cap, status]) => (
                    <div
                      key={cap}
                      className="rounded-lg border border-border/40 p-3 bg-card flex flex-col justify-between"
                    >
                      <div className="font-medium text-foreground capitalize">
                        {cap.replace(/_/g, ' ')}
                      </div>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-[10px] text-muted-foreground">Readiness:</span>
                        <Badge
                          variant={
                            status === 'READY'
                              ? 'default'
                              : status === 'PARTIAL'
                              ? 'secondary'
                              : 'outline'
                          }
                          className="text-[10px]"
                        >
                          {String(status)}
                        </Badge>
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Tab 3: Version History */}
          <TabsContent value="history" className="space-y-4">
            <Card className="border-border/60">
              <CardHeader className="pb-3 border-b border-border/30">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <History className="h-4 w-4" />
                  <span>Material Version History & Audit Trail</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Every change to your Investor Profile is preserved as an immutable version with explicit rationale.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-2">
                {versions.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-4 text-center">
                    No confirmed versions recorded yet.
                  </p>
                ) : (
                  <div className="divide-y divide-border/30 text-xs">
                    {versions.map((ver) => (
                      <div key={ver.id} className="py-3 flex items-center justify-between">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-foreground">
                              Version {ver.version_number}
                            </span>
                            <Badge variant="outline" className="text-[10px]">
                              {ver.change_source}
                            </Badge>
                          </div>
                          <div className="text-muted-foreground text-[11px]">
                            {ver.change_reason || 'Updated profile'}
                          </div>
                        </div>
                        <div className="text-right text-[11px] text-muted-foreground">
                          {new Date(ver.confirmed_at).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
