import { Link } from 'react-router-dom'
import { ArrowUpRight, BookOpen, ChevronRight, Plus } from 'lucide-react'
import type { DecisionLogEntry } from '@/types'

interface Props {
  decisions?: DecisionLogEntry[]
}

export default function RecentJournalCard({ decisions = [] }: Props) {
  const topDecisions = decisions.slice(0, 3)

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5 min-h-[260px] flex flex-col justify-between space-y-3.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/30 pb-2.5">
        <div className="flex items-center gap-2">
          <BookOpen className="size-4 text-teal-400" />
          <h3 className="text-xs font-semibold text-foreground">Recent Decisions</h3>
          {topDecisions.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-300 font-mono">
              {decisions.length}
            </span>
          )}
        </div>
        <Link
          to="/decisions"
          className="text-xs text-teal-400 hover:text-teal-300 font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>Decision Log</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Content */}
      {topDecisions.length === 0 ? (
        <div className="flex-1 flex flex-col justify-between py-1 space-y-2">
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-foreground">Decision Audit Trail</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Every portfolio buy, sell, or thesis revision is logged here to track the "Why" behind your investment outcomes.
            </p>
          </div>
          <Link
            to="/decisions"
            className="inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-teal-500/10 hover:bg-teal-500/15 border border-teal-500/20 text-xs font-semibold text-teal-300 transition-colors w-full"
          >
            <Plus className="size-3.5" />
            <span>Record Decision Note</span>
          </Link>
        </div>
      ) : (
        <div className="space-y-1.5 flex-1">
          {topDecisions.map((decision) => {
            const date = new Date(decision.occurred_at || decision.created_at)
            const month = date.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()
            const day = date.toLocaleDateString('en-US', { day: '2-digit' })
            const symbol = decision.instrument_symbol || decision.asset_name || 'DEC'

            return (
              <Link
                key={decision.id}
                to="/decisions"
                className="group flex items-center justify-between gap-3 p-2 rounded-lg border border-border/30 bg-background/40 hover:border-teal-500/30 hover:bg-muted/20 transition-all text-xs"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex flex-col items-center justify-center size-9 rounded-md bg-muted/40 border border-border/40 text-muted-foreground text-[9px] uppercase font-bold font-mono shrink-0">
                    <span>{month}</span>
                    <span className="text-xs font-bold leading-none">{day}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-foreground truncate group-hover:text-teal-300 transition-colors">
                      {symbol}: {decision.title}
                    </p>
                    <p className="text-[11px] text-muted-foreground line-clamp-1">
                      {decision.user_rationale ? `"${decision.user_rationale}"` : decision.summary}
                    </p>
                  </div>
                </div>

                <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground shrink-0 transition-colors" />
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
