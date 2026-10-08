import { Skeleton } from '@/components/ui/skeleton'
import { Card } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ChevronRight, Calendar } from 'lucide-react'
import type { Asset } from '@/types'

interface Props {
  assets: Asset[]
  isLoading?: boolean
}

export default function UpcomingEventsCard({ assets, isLoading = false }: Props) {
  // Only show review dates recorded on existing asset intelligence.
  const upcomingReviews = assets
    .filter((a) => a.instrument?.intelligence_state?.next_review_at != null)
    .map((a) => ({
      asset: a,
      date: new Date(a.instrument!.intelligence_state!.next_review_at!),
    }))
    .filter(({ date }) => Number.isFinite(date.getTime()) && date >= new Date(new Date().setHours(0, 0, 0, 0)))
    .sort((a, b) => a.date.getTime() - b.date.getTime())
    .slice(0, 4)

  return (
    <Card id="upcoming-events" className="dashboard-card flex min-h-[250px] flex-col gap-4 p-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Upcoming Events</h3>
        </div>
        <Link
          to="/monitoring"
          className="text-xs text-info hover:text-foreground font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>View all</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Content */}
      {isLoading ? (
        <div aria-label="Loading upcoming events" className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : upcomingReviews.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8 text-center">
          <Calendar className="size-7 text-muted-foreground/60" />
          <p className="text-sm font-medium">No scheduled reviews</p>
          <p className="max-w-64 text-xs leading-relaxed text-muted-foreground">Upcoming review dates will appear here when available for your holdings.</p>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-2">
          {upcomingReviews.map(({ asset, date }) => {
            const month = date.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()
            const day = date.toLocaleDateString('en-US', { day: '2-digit' })

            return (
              <Link
                key={asset.id}
                to={`/assets/${asset.id}`}
                className="group flex items-center justify-between gap-3 p-2 rounded-lg border border-border/30 bg-background/40 hover:border-info/30 hover:bg-muted/20 transition-all text-xs"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex flex-col items-center justify-center size-9 rounded-md bg-teal-500/10 border border-teal-500/20 text-teal-300 text-[9px] uppercase font-bold font-mono shrink-0">
                    <span>{month}</span>
                    <span className="text-xs font-bold leading-none">{day}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-foreground truncate group-hover:text-info transition-colors">
                      {asset.symbol ?? asset.name} Review
                    </p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      Scheduled thesis review
                    </p>
                  </div>
                </div>

                <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground shrink-0 transition-colors" />
              </Link>
            )
          })}
        </div>
      )}
    </Card>
  )
}
