import { Link } from 'react-router-dom'
import { UserCheck, ArrowRight, RefreshCw, Target } from 'lucide-react'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="app-page max-w-4xl space-y-6">
        <PageHeader title="Settings" description="Account, investor profile, and application preferences." />

        {/* Investor Profile & Investment Policy Card */}
        <Card className="shadow-card border-border/60">
          <CardHeader>
            <div className="flex items-center gap-2 text-primary font-semibold text-xs uppercase tracking-wider">
              <UserCheck className="h-4 w-4" />
              <span>Investment Personalization</span>
            </div>
            <CardTitle className="text-lg">Investor Profile & Policy (IPS)</CardTitle>
            <CardDescription>
              Manage your personal investment policy, psychological risk tolerance, balance sheet risk capacity, and decision preferences.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              PortfolioMind uses your confirmed Investor Profile to evaluate portfolio fit, run concentration checks, align Copilot recommendations, and detect contradictions between your risk appetite and liquidity needs.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button asChild variant="default" size="sm">
                <Link to="/settings/investor-profile">
                  View Profile & Policy
                  <ArrowRight className="h-4 w-4 ml-1.5" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to="/onboarding">
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                  Retake Assessment
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Financial Context, Goals & Mandates (Phase 4.1) */}
        <Card className="shadow-card border-border/60">
          <CardHeader>
            <div className="flex items-center gap-2 text-primary font-semibold text-xs uppercase tracking-wider">
              <Target className="h-4 w-4" />
              <span>Financial Life & Planning</span>
            </div>
            <CardTitle className="text-lg">Financial Profile, Goals & Mandates</CardTitle>
            <CardDescription>
              Manage your cash flow context, first-class financial goals (retirement, down payment, emergency), and scoped investment mandates with virtual capital earmarks.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Define outcomes and timelines ('Why / When') independently from investment strategy ('How'). Earmark assets and cash to distinct mandates with zero tax or transaction side-effects.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button asChild variant="default" size="sm">
                <Link to="/settings/financial-profile">
                  Manage Goals & Mandates
                  <ArrowRight className="h-4 w-4 ml-1.5" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Existing General Preferences */}
        <Card className="shadow-card border-border/60">
          <CardHeader>
            <CardTitle className="text-lg">Preferences</CardTitle>
            <CardDescription>General application settings</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Your base currency and visual preferences remain managed through your account settings and profile.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
