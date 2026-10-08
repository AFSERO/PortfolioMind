import { Card } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { AlertCircle, AlertTriangle, ArrowUpRight, CheckCircle2, ChevronRight, Info } from 'lucide-react'
import type { Asset, BriefingItem } from '@/types'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'

interface Props {
  assets: Asset[]
  isLoading: boolean
  briefingItems?: BriefingItem[]
}

export default function NeedsAttentionSection({ assets, isLoading, briefingItems = [] }: Props) {
  if (isLoading) {
    return (
      <Card className="dashboard-card flex min-h-[250px] flex-col gap-4 p-5">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-16" />
        </div>
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-8 rounded-full shrink-0" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3 w-36" />
                <Skeleton className="h-2.5 w-48" />
              </div>
            </div>
          ))}
        </div>
      </Card>
    )
  }

  // 1. Asset intelligence state alerts
  const assetAttentionItems = assets
    .map((asset) => {
      const state = asset.instrument?.intelligence_state
      if (!state) return null

      const reasons: string[] = []
      let severity: 'Critical' | 'Important' | 'Review' = 'Review'

      if (state.thesis_status === 'INVALIDATED') {
        reasons.push('Thesis invalidated by material event')
        severity = 'Critical'
      } else if (state.thesis_status === 'WEAKER') {
        reasons.push('Investment thesis weakened')
        severity = 'Important'
      }

      if (state.recommendation === 'SELL') {
        reasons.push('Exit recommendation triggered')
        if (severity !== 'Critical') severity = 'Important'
      } else if (state.recommendation === 'REVIEW_REQUIRED') {
        reasons.push('Formal thesis review required')
      }

      if (state.technical_status === 'REVIEW_REQUIRED' || state.technical_status === 'DEVIATED') {
        reasons.push('Price action breached strategy boundary')
      }

      if (reasons.length === 0) return null

      return {
        id: `asset-${asset.id}`,
        symbol: asset.symbol || asset.name,
        severity,
        tagLabel: undefined,
        headline: reasons[0],
        brief: state.human_brief || 'Consider reviewing your thesis against latest data.',
        link: `/assets/${asset.id}`,
        actionLabel: 'Review Asset',
      }
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)

  // 2. Briefing items requiring attention (OPEN, REVIEWED_BUT_STILL_REQUIRES_ATTENTION, or DECISION_REQUIRED)
  const briefingAttentionItems = briefingItems
    .filter((b) => {
      if (b.attention_state) {
        return (
          b.attention_state === 'OPEN' ||
          b.attention_state === 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' ||
          b.attention_state === 'DECISION_REQUIRED'
        )
      }
      if (!b.review_required) return false
      const status = b.source_metadata?.review_status
      if (status !== 'COMPLETED') return true
      const summary = b.source_metadata?.review_summary
      if (!summary) return true
      const rec = summary.recommendation?.toUpperCase()
      const thesis = summary.thesis_status?.toUpperCase()
      const tech = summary.technical_status?.toUpperCase()
      return (
        rec === 'REVIEW_REQUIRED' ||
        rec === 'ADD' ||
        rec === 'BUY' ||
        rec === 'REDUCE' ||
        rec === 'SELL' ||
        thesis === 'WEAKER' ||
        thesis === 'INVALIDATED' ||
        tech === 'REVIEW_REQUIRED' ||
        tech === 'DEVIATED'
      )
    })
    .map((b) => {
      const isDecisionRequired =
        b.attention_state === 'DECISION_REQUIRED' ||
        (!b.attention_state &&
          b.source_metadata?.review_status === 'COMPLETED' &&
          ['ADD', 'BUY', 'REDUCE', 'SELL'].includes(
            b.source_metadata.review_summary?.recommendation?.toUpperCase() || ''
          ))

      const isReviewedStillNeedingAttention =
        b.attention_state === 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' ||
        (!b.attention_state &&
          b.source_metadata?.review_status === 'COMPLETED' &&
          (b.source_metadata.review_summary?.recommendation === 'REVIEW_REQUIRED' ||
            b.source_metadata.review_summary?.thesis_status === 'WEAKER' ||
            b.source_metadata.review_summary?.thesis_status === 'INVALIDATED'))

      const rec = b.source_metadata?.review_summary?.recommendation?.toUpperCase()
      const severity =
        rec === 'SELL' || b.materiality === 'CRITICAL'
          ? ('Critical' as const)
          : ('Important' as const)

      let headline = b.headline
      let tagLabel = 'BRIEFING'
      let actionLabel = 'Review Thesis'
      let link = '/briefing'

      if (isDecisionRequired) {
        tagLabel = 'DECISION'
        headline = `Decision needed · ${rec ? `${rec} recommended` : 'Action recommended'}: ${b.headline}`
        actionLabel = 'Record Decision'
        link = '/decisions'
      } else if (isReviewedStillNeedingAttention) {
        tagLabel = 'REVIEWED'
        headline = `Reviewed · Attention Needed: ${b.headline}`
        actionLabel = 'Review Thesis'
        link = '/briefing'
      }

      return {
        id: `briefing-${b.id}`,
        symbol: b.instrument_symbol || 'Watchlist',
        severity,
        tagLabel,
        headline,
        brief: b.source_metadata?.review_summary?.human_brief || b.why_it_matters,
        link,
        actionLabel,
      }
    })

  const combinedAttention = [...assetAttentionItems, ...briefingAttentionItems]

  return (
    <Card id="needs-attention" className="dashboard-card flex min-h-[250px] flex-col gap-4 p-5">
      {/* Header with title and View all link */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Needs Attention</h3>
          {combinedAttention.length > 0 && (
            <span className="inline-flex items-center justify-center rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[10px] font-mono px-1.5 py-0.5">
              {combinedAttention.length}
            </span>
          )}
        </div>
        <Link
          to="/briefing"
          className="text-xs text-info hover:text-foreground font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>View all</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Content: Active alerts OR Intentional Reassuring Quiet State */}
      {combinedAttention.length === 0 ? (
        <div className="flex-1 flex flex-col justify-center py-2 space-y-3">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-teal-500/5 border border-teal-500/15">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-teal-500/15 text-teal-400 mt-0.5">
              <CheckCircle2 className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
                Nothing currently requires your attention.
              </p>
              <p className="mt-0.5 text-[11px] text-muted-foreground leading-relaxed">
                {assets.length} positions monitored · 0 thesis-breaking events · 0 technical deviations.
              </p>
            </div>
          </div>

          <div className="space-y-1.5 pt-1 text-[11px] text-muted-foreground/80 pl-1">
            <div className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-teal-400" />
              <span>Investment theses intact across all holdings</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-teal-400" />
              <span>Prices trading within normal strategic boundaries</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-teal-400" />
              <span>Intelligence radar scanned and filtered for noise</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-2">
          {combinedAttention.slice(0, 3).map(({ id, symbol, severity, tagLabel, headline, brief, link, actionLabel }) => {
            const isCritical = severity === 'Critical'
            const isImportant = severity === 'Important'

            return (
              <Link
                key={id}
                to={link}
                className="group flex items-center justify-between gap-3 p-2.5 rounded-lg border border-border/30 bg-background/40 hover:border-info/30 hover:bg-muted/20 transition-all text-xs"
              >
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-full border',
                      isCritical
                        ? 'border-rose-500/30 bg-rose-500/15 text-rose-400'
                        : isImportant
                        ? 'border-amber-500/30 bg-amber-500/15 text-amber-400'
                        : 'border-blue-500/30 bg-blue-500/15 text-blue-400'
                    )}
                  >
                    {isCritical ? (
                      <AlertCircle className="size-3.5" />
                    ) : isImportant ? (
                      <AlertTriangle className="size-3.5" />
                    ) : (
                      <Info className="size-3.5" />
                    )}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-foreground truncate font-mono">
                        {symbol}
                      </span>
                      {tagLabel && (
                        <span
                          className={cn(
                            'text-[9px] px-1 rounded font-mono',
                            tagLabel === 'DECISION'
                              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30 font-medium'
                              : tagLabel === 'REVIEWED'
                              ? 'bg-amber-500/10 text-amber-300 font-medium'
                              : 'bg-teal-500/10 text-teal-300'
                          )}
                        >
                          {tagLabel}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] font-semibold text-foreground/90 truncate group-hover:text-info transition-colors">
                      {headline}
                    </p>
                    <p className="text-[11px] text-muted-foreground line-clamp-1">
                      {brief}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="sr-only">
                    {actionLabel}
                  </span>
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
