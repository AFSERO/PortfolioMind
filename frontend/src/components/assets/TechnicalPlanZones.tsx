import { Compass, TrendingUp } from 'lucide-react'
import type { TechnicalPlan } from '@/types'
import { Badge } from '@/components/ui/badge'

interface Props {
  plan?: TechnicalPlan | null
  currentPrice?: number | null
  currency?: string
}

function formatZone(zone: any): string {
  if (typeof zone === 'number') return zone.toString()
  if (typeof zone === 'object' && zone !== null) {
    if (zone.low != null && zone.high != null) {
      return `${zone.low} – ${zone.high}`
    }
    if (zone.price != null) return `${zone.price}`
    if (zone.level != null) return `${zone.level}`
  }
  return JSON.stringify(zone)
}

export default function TechnicalPlanZones({ plan, currentPrice, currency = '$' }: Props) {
  if (!plan) {
    return (
      <div className="rounded-xl border border-border/60 bg-card/40 p-5">
        <div className="flex items-center gap-2 mb-2">
          <Compass className="size-4 text-muted-foreground" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Technical Strategy Zones
          </h3>
        </div>
        <p className="text-xs text-muted-foreground py-2">
          No active technical plan or price zones recorded for this instrument.
        </p>
      </div>
    )
  }

  const entries = plan.entry_zones ?? []
  const invalidations = plan.review_or_invalidation_zones ?? []
  const profitTakings = plan.profit_taking_or_reassessment_zones ?? []

  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/40 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-7 items-center justify-center rounded-md bg-teal-500/10 text-teal-400">
            <Compass className="size-4" />
          </span>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Technical Strategy Zones
            </h3>
            <p className="text-[10px] text-muted-foreground">
              Pre-defined decision boundaries: Entry, Invalidation, and Profit-taking.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {currentPrice != null && (
            <span className="text-xs font-mono text-muted-foreground mr-1 hidden sm:inline">
              Current: <strong className="text-foreground">{currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {currency}</strong>
            </span>
          )}
          {plan.trend_expectation && (
            <Badge variant="outline" className="border-teal-500/30 bg-teal-500/10 text-teal-300 text-[10px]">
              <TrendingUp className="size-3 mr-1" />
              {plan.trend_expectation.replace('_', ' ')}
            </Badge>
          )}
        </div>
      </div>

      {/* Strategy Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        {/* Invalidation / Stop */}
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3">
          <p className="text-[10px] uppercase font-semibold text-rose-400">Stop / Invalidation</p>
          <div className="mt-1 font-mono font-bold text-rose-300">
            {invalidations.length > 0 ? (
              invalidations.map((z, idx) => <span key={idx}>{formatZone(z)} {currency}</span>)
            ) : (
              <span className="text-muted-foreground text-xs font-normal">Not defined</span>
            )}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">Breach invalidates current setup</p>
        </div>

        {/* Entry / Accumulation */}
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
          <p className="text-[10px] uppercase font-semibold text-emerald-400">Accumulation / Entry</p>
          <div className="mt-1 font-mono font-bold text-emerald-300">
            {entries.length > 0 ? (
              entries.map((z, idx) => <span key={idx}>{formatZone(z)} {currency}</span>)
            ) : (
              <span className="text-muted-foreground text-xs font-normal">Not defined</span>
            )}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">Favorable risk/reward entry zone</p>
        </div>

        {/* Take Profit / Reassessment */}
        <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 p-3">
          <p className="text-[10px] uppercase font-semibold text-teal-400">Profit / Reassessment</p>
          <div className="mt-1 font-mono font-bold text-teal-300">
            {profitTakings.length > 0 ? (
              profitTakings.map((z, idx) => <span key={idx}>{formatZone(z)} {currency}</span>)
            ) : (
              <span className="text-muted-foreground text-xs font-normal">Not defined</span>
            )}
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">Target zone for sizing review</p>
        </div>
      </div>

      {/* Plan Notes */}
      {plan.notes && (
        <div className="text-xs text-muted-foreground bg-muted/20 border border-border/30 rounded-lg p-2.5">
          <span className="font-semibold text-foreground/80">Strategy Notes: </span>
          {plan.notes}
        </div>
      )}
    </div>
  )
}
