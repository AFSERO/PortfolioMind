import { Link } from 'react-router-dom'
import { ArrowUpRight, ChevronRight, Plus, Sparkles } from 'lucide-react'
import { useInstruments } from '@/hooks/useInstruments'
import { useOpportunities } from '@/hooks/useOpportunities'

export default function WatchlistCard() {
  const { instruments, isLoading: instLoading } = useInstruments()
  const { watchlist, isLoading: oppLoading } = useOpportunities()

  const isLoading = instLoading && oppLoading

  // Active candidates requiring research attention
  const activeOpportunities = (watchlist || []).filter(
    (w) =>
      w.opportunity?.status === 'RESEARCH_NOW' ||
      w.opportunity?.status === 'RESEARCH_SOON'
  )

  const hasWatchlistItems = (watchlist && watchlist.length > 0) || (instruments && instruments.length > 0)

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5 min-h-[260px] flex flex-col justify-between space-y-3.5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/30 pb-2.5">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold text-foreground">Watchlist Opportunities</h3>
          {activeOpportunities.length > 0 && (
            <span className="flex size-2 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </div>
        <Link
          to="/watchlist"
          className="text-xs text-teal-400 hover:text-teal-300 font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>View all</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-2 py-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-9 w-full rounded-md bg-muted/20 animate-pulse" />
          ))}
        </div>
      ) : activeOpportunities.length > 0 ? (
        <div className="space-y-2 flex-1">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground pb-1">
            <span>{activeOpportunities.length} candidate(s) deserve research:</span>
          </div>
          {activeOpportunities.slice(0, 3).map((w) => {
            const opp = w.opportunity
            const isNow = opp?.status === 'RESEARCH_NOW'
            return (
              <Link
                key={w.id}
                to="/watchlist"
                className={`group flex items-center justify-between gap-2 p-2.5 rounded-lg border transition-all text-xs ${
                  isNow
                    ? 'border-emerald-500/30 bg-emerald-950/15 hover:border-emerald-500/50'
                    : 'border-amber-500/30 bg-amber-950/15 hover:border-amber-500/50'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-foreground font-mono">
                      {w.instrument?.symbol ?? w.instrument?.name.slice(0, 5).toUpperCase()}
                    </span>
                    <span className="text-[11px] text-muted-foreground truncate max-w-[120px]">
                      {w.instrument?.name}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                    {opp?.reason}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${
                      isNow
                        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                        : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                    }`}
                  >
                    {isNow ? 'RESEARCH NOW' : 'RESEARCH SOON'}
                  </span>
                  <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-foreground shrink-0 transition-colors" />
                </div>
              </Link>
            )
          })}
        </div>
      ) : hasWatchlistItems ? (
        /* Reassuring calm quiet state when no candidates require research */
        <div className="flex-1 flex flex-col justify-between py-1">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Sparkles className="size-4 text-teal-400" />
              <p className="text-xs font-semibold text-foreground">No Research Attention Needed</p>
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Monitored watchlist candidates are currently quiet. No targets entered or stale analyses detected.
            </p>
          </div>
          <Link
            to="/watchlist"
            className="inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-teal-500/10 hover:bg-teal-500/15 border border-teal-500/20 text-xs font-semibold text-teal-300 transition-colors w-full"
          >
            <Plus className="size-3.5" />
            <span>Manage Watchlist</span>
          </Link>
        </div>
      ) : (
        /* Empty watchlist state */
        <div className="flex-1 flex flex-col justify-between py-1">
          <div className="space-y-2">
            <p className="text-xs font-medium text-foreground">Track Potential Holdings</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Maintain a monitored universe of high-conviction companies and assets awaiting strategic entry valuations.
            </p>
          </div>
          <Link
            to="/watchlist"
            className="inline-flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-teal-500/10 hover:bg-teal-500/15 border border-teal-500/20 text-xs font-semibold text-teal-300 transition-colors w-full"
          >
            <Plus className="size-3.5" />
            <span>Add Candidate Security</span>
          </Link>
        </div>
      )}
    </div>
  )
}
