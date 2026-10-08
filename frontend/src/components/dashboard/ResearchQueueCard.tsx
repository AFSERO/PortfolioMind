import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ASSET_TYPE_META } from '@/utils/assetTypes'
import { Card } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ChevronRight, Plus } from 'lucide-react'
import type { Asset } from '@/types'

interface Props {
  assets: Asset[]
  isLoading?: boolean
}

export default function ResearchQueueCard({ assets, isLoading = false }: Props) {
  // Find assets with recent intelligence or active thesis monitoring
  const reviewedAssets = assets
    .filter((a) => {
      const s = a.instrument?.intelligence_state
      return Boolean(s && (s.last_review_at || s.thesis_status || s.recommendation))
    })
    .slice(0, 4)

  return (
    <Card className="dashboard-card flex min-h-[250px] flex-col gap-4 p-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Research Queue</h3>
        </div>
        <Link
          to="/research"
          className="text-xs text-info hover:text-foreground font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>View all</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Content */}
      {isLoading ? (
        <div aria-label="Loading research queue" className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : reviewedAssets.length === 0 ? (
        <div className="flex-1 flex flex-col justify-between py-1">
          <div className="space-y-2">
            <p className="text-xs font-medium text-foreground">Investment Thesis Pipeline</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Track candidate securities through four disciplined research stages before deploying capital.
            </p>
            <div className="grid grid-cols-2 gap-1.5 pt-1 text-[10px] text-muted-foreground">
              <div className="p-2 rounded bg-background/40 border border-border/30">
                <span className="font-semibold text-teal-400 block">1. Screening</span>
                <span>Candidate Discovery</span>
              </div>
              <div className="p-2 rounded bg-background/40 border border-border/30">
                <span className="font-semibold text-sky-400 block">2. Deep Research</span>
                <span>Moat & Valuation</span>
              </div>
              <div className="p-2 rounded bg-background/40 border border-border/30">
                <span className="font-semibold text-amber-400 block">3. Price Wait</span>
                <span>Strategy Entry Zones</span>
              </div>
              <div className="p-2 rounded bg-background/40 border border-border/30">
                <span className="font-semibold text-purple-400 block">4. Monitored</span>
                <span>Continuous Review</span>
              </div>
            </div>
          </div>

          <Link
            to="/watchlist"
            className="inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-teal-500/10 hover:bg-teal-500/15 border border-teal-500/20 text-xs font-semibold text-teal-300 transition-colors w-full mt-2"
          >
            <Plus className="size-3.5" />
            <span>Add Research Candidate</span>
          </Link>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-2">
          {reviewedAssets.map((asset) => {
            const AssetIcon = ASSET_TYPE_META[asset.asset_type]?.icon
            const state = asset.instrument?.intelligence_state
            const recommendation = state?.recommendation ?? 'NOT REVIEWED'
            const brief = state?.human_brief || 'Active thesis monitoring in progress'

            let badgeStyle = 'bg-teal-500/10 text-teal-300 border-teal-500/20'
            if (recommendation === 'ADD') badgeStyle = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
            else if (recommendation === 'REDUCE' || recommendation === 'SELL') badgeStyle = 'bg-rose-500/10 text-rose-300 border-rose-500/20'
            else if (recommendation === 'REVIEW_REQUIRED') badgeStyle = 'bg-amber-500/10 text-amber-300 border-amber-500/20'
            else if (recommendation === 'NOT REVIEWED') badgeStyle = 'bg-muted/20 text-muted-foreground/70 border-border/40'

            return (
              <Link
                key={asset.id}
                to={`/assets/${asset.id}`}
                className="group flex min-h-14 items-center justify-between gap-3 p-2 rounded-lg border border-border/30 bg-background/40 hover:border-info/30 hover:bg-muted/20 transition-all text-xs"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-info/10 text-info">{AssetIcon && <AssetIcon className="size-4" />}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="max-w-[50%] shrink-0 truncate font-semibold text-foreground group-hover:text-info transition-colors">
                      {asset.symbol ?? asset.name}
                    </span>
                    <span className="text-[11px] text-muted-foreground truncate max-w-[120px]">
                      {asset.name}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                    {brief}
                  </p>
                </div>

                <div className="flex max-w-[35%] shrink-0 items-center gap-2">
                  <Badge variant="secondary" className={`min-w-0 max-w-full rounded-md px-2 text-[10px] [overflow-wrap:anywhere] ${badgeStyle}`}>
                    {recommendation}
                  </Badge>
                  <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground shrink-0 transition-colors" />
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </Card>
  )
}
