import { Bell, FileText, Calendar, Compass, ChevronRight } from 'lucide-react'
import type { Asset, AllocationData } from '@/types'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'

interface Props {
  assets: Asset[]
  allocation: AllocationData | null
  isLoading: boolean
  briefingAttentionCount?: number
}

export default function PortfolioPulse({ assets, isLoading, briefingAttentionCount = 0 }: Props) {
  if (isLoading) {
    return (
      <div className="dashboard-pulse-grid grid grid-cols-1 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl border border-border/60 bg-card/40 p-3.5 flex items-center gap-3">
            <Skeleton className="size-9 rounded-lg shrink-0" />
            <div className="flex-1 space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-4 w-28" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  // 1. Material Events & Action Required (Assets + Briefing Radar)
  const assetActionCount = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    if (!s) return false
    return (
      s.thesis_status === 'WEAKER' ||
      s.thesis_status === 'INVALIDATED' ||
      s.recommendation === 'REVIEW_REQUIRED' ||
      s.recommendation === 'SELL' ||
      s.technical_status === 'REVIEW_REQUIRED'
    )
  }).length

  const actionRequiredCount = Math.max(assetActionCount, briefingAttentionCount)

  // 2. Thesis Alerts (Weak or Invalidated)
  const thesisAlertsCount = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    if (!s) return false
    return s.thesis_status === 'WEAKER' || s.thesis_status === 'INVALIDATED'
  }).length

  // 3. Upcoming Milestones & Reviews
  const now = new Date()
  const in14Days = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000)
  const upcomingCount = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    if (!s?.next_review_at) return false
    const reviewDate = new Date(s.next_review_at)
    return reviewDate >= now && reviewDate <= in14Days
  }).length

  const indicators = [
    {
      label: 'Material Events',
      title: `${actionRequiredCount} material event${actionRequiredCount === 1 ? '' : 's'}`,
      sub: actionRequiredCount === 0 ? 'Operating normally' : 'Require attention',
      icon: Bell,
      iconBg: 'bg-info/10 text-info',
      href: '/briefing',
    },
    {
      label: 'Thesis Alerts',
      title: `${thesisAlertsCount} thesis alert${thesisAlertsCount === 1 ? '' : 's'}`,
      sub: thesisAlertsCount === 0 ? 'Theses intact' : 'Holdings need review',
      icon: FileText,
      iconBg: 'bg-negative/10 text-negative',
      href: '#needs-attention',
    },
    {
      label: 'Upcoming Events',
      title: `${upcomingCount} upcoming event${upcomingCount === 1 ? '' : 's'}`,
      sub: 'Next 14 days',
      icon: Calendar,
      iconBg: 'bg-info/10 text-info',
      href: '#upcoming-events',
    },
    {
      label: 'Target Alignment',
      title: 'Target alignment',
      sub: 'Not assessed',
      icon: Compass,
      iconBg: 'bg-muted/60 text-muted-foreground',
      href: '/allocation',
    },
  ]

  return (
    <div className="dashboard-pulse-grid grid grid-cols-1 gap-4">
      {indicators.map((item) => {
        const Icon = item.icon
        return (
          <a
            key={item.label}
            href={item.href}
            className={cn(
              'dashboard-card group flex min-h-[76px] min-w-0 items-center justify-between gap-3 p-3.5 transition-colors hover:border-info/40 hover:bg-accent/30'
            )}
          >
            <div className="flex items-center gap-3 min-w-0">
              <span
                className={cn(
                  'flex size-11 shrink-0 items-center justify-center rounded-lg',
                  item.iconBg
                )}
              >
                <Icon className="size-5" />
              </span>
              <div className="min-w-0">
                <span className="sr-only">{item.label}</span>
                <p className="text-[13px] font-semibold text-foreground">
                  {item.title}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.sub}
                </p>
              </div>
            </div>
            <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground shrink-0 transition-colors" />
          </a>
        )
      })}
    </div>
  )
}
