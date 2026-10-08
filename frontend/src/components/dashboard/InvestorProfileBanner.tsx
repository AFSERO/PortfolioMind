import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChartNoAxesColumnIncreasing, AlertTriangle, ArrowRight, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { investorProfileService } from '@/services/investorProfileService'
import type { InvestorProfileData } from '@/types/investorProfile'

export default function InvestorProfileBanner() {
  const [profile, setProfile] = useState<InvestorProfileData | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const isDismissed = sessionStorage.getItem('dismiss_investor_profile_banner')
    if (isDismissed) {
      setDismissed(true)
      setLoading(false)
      return
    }

    let isMounted = true
    investorProfileService
      .getCurrentProfile()
      .then((data) => {
        if (isMounted) setProfile(data)
      })
      .catch(() => {
        // Quiet fallback - profile may not exist yet
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  const handleDismiss = () => {
    setDismissed(true)
    sessionStorage.setItem('dismiss_investor_profile_banner', 'true')
  }

  if (loading || dismissed) return null

  const hasConfirmed = Boolean(profile?.version_number)
  const completeness = profile?.completeness_overall_pct ?? 0
  const x01Issue = profile?.issues?.find((i) => i.rule_id === 'X01')

  // If confirmed and has an active contradiction alert (X01)
  if (hasConfirmed && x01Issue) {
    return (
      <div className="relative flex flex-col items-start justify-between gap-3 rounded-lg border border-warning/30 bg-warning/10 p-4 text-xs text-warning sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-4">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
          <span>
            <strong className="font-semibold text-amber-300">Policy Alert:</strong> Risk Tolerance vs Capacity divergence detected. Your portfolio risk may exceed near-term withdrawal needs.
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button asChild variant="outline" size="sm" className="h-7 text-xs border-amber-500/40 text-amber-200 hover:bg-amber-500/20">
            <Link to="/settings/investor-profile">Review Policy</Link>
          </Button>
          <button
            onClick={handleDismiss}
            className="text-amber-400/70 hover:text-amber-300 p-1 rounded transition-colors"
            title="Dismiss notice"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    )
  }

  // If not confirmed or completeness is low (< 50%)
  if (!hasConfirmed || completeness < 50) {
    return (
      <div className="dashboard-card dashboard-profile-banner relative flex flex-col items-start justify-between gap-4 px-4 py-3 text-xs sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-info/10 text-info">
            <ChartNoAxesColumnIncreasing className="size-6" />
          </div>
          <div>
            <div className="text-sm font-semibold text-foreground">
              Personalize PortfolioMind with your Investor Profile
            </div>
            <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {hasConfirmed
                ? `Your profile is ${completeness}% complete. Add more details to unlock tailored Copilot advice and risk alignment.`
                : 'Get more relevant insights and risk analysis based on your goals and risk tolerance.'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
          <Button asChild variant="default" size="sm" className="dashboard-assessment-button gap-3">
            <Link to="/onboarding">
              {hasConfirmed ? 'Improve Profile' : 'Start Assessment'}
              <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
          <button
            onClick={handleDismiss}
            className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
            title="Dismiss for this session"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    )
  }

  return null
}
