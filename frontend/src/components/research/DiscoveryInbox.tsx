import { useState } from 'react'
import {
  Compass,
  Search,
  ShieldAlert,
  HelpCircle,
  RefreshCw,
  BookmarkPlus,
  ChevronDown,
  ChevronUp,
  Newspaper,
  TrendingDown,
  AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useDiscovery } from '@/hooks/useDiscovery'
import type { DiscoveryCandidate, DiscoveryUniverse } from '@/types'

const UNIVERSE_LABELS: Record<DiscoveryUniverse, { label: string; desc: string }> = {
  US_LARGE_CAP: {
    label: 'US Large Cap',
    desc: 'S&P 500 Leaders & Established Compounders',
  },
  US_TECH_GROWTH: {
    label: 'US Tech / Growth',
    desc: 'Cloud Software, AI & Semiconductor Leaders',
  },
  BIST_LIQUID: {
    label: 'BIST Liquid',
    desc: 'BIST 30 High-Liquidity Equities',
  },
  CUSTOM: {
    label: 'Custom Universe',
    desc: 'User-specified search universe',
  },
}

export function DiscoveryInbox() {
  const {
    run,
    isLoading,
    isScanning,
    actionInProgress,
    error,
    triggerScan,
    addToWatchlist,
    dismissCandidate,
    screenCandidate,
  } = useDiscovery()

  const [selectedUniverse, setSelectedUniverse] = useState<DiscoveryUniverse>('US_LARGE_CAP')
  const [expandedNews, setExpandedNews] = useState<Record<string, boolean>>({})

  const handleScan = async (force: boolean = false) => {
    try {
      const res = await triggerScan(selectedUniverse, force)
      const count = res?.candidates_surfaced ?? 0
      toast.success(
        count > 0
          ? `Discovery scan complete: ${count} candidate(s) surfaced for research.`
          : 'Discovery scan completed. No candidates met the strict dislocation criteria.',
      )
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Discovery scan failed')
    }
  }

  const handleAddToWatchlist = async (cand: DiscoveryCandidate) => {
    try {
      await addToWatchlist(cand.id)
      toast.success(`${cand.symbol} added to Watchlist in DISCOVERED stage.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to add to watchlist')
    }
  }

  const handleDismiss = async (cand: DiscoveryCandidate) => {
    try {
      await dismissCandidate(cand.id)
      toast.info(`${cand.symbol} dismissed and suppressed from discovery inbox.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to dismiss candidate')
    }
  }

  const handleScreen = async (cand: DiscoveryCandidate) => {
    try {
      await screenCandidate(cand.id)
      toast.success(`Formal preliminary screening initiated for ${cand.symbol}.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Screening failed')
    }
  }

  const toggleNews = (candId: string) => {
    setExpandedNews((prev) => ({ ...prev, [candId]: !prev[candId] }))
  }

  const activeCandidates = (run?.candidates || []).filter(
    (c) => c.candidate_state === 'SURFACED',
  )

  const formatPrice = (price?: number | null, curr?: string | null) => {
    if (price == null) return '-'
    const c = curr === 'TRY' ? '₺' : '$'
    return `${c}${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'HIGH_PRIORITY_SCREEN':
        return (
          <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-xs font-semibold">
            HIGH PRIORITY SCREEN
          </Badge>
        )
      case 'SCREEN':
        return (
          <Badge className="bg-sky-500/15 text-sky-400 border-sky-500/30 text-xs font-semibold">
            SCREEN CANDIDATE
          </Badge>
        )
      case 'WATCH':
        return (
          <Badge className="bg-purple-500/15 text-purple-400 border-purple-500/30 text-xs font-semibold">
            WATCHLIST CANDIDATE
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-rose-500/30 bg-rose-950/20 text-xs text-rose-300">
          <AlertTriangle className="h-4 w-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Header & Universe Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl border border-border/60 bg-card/30 backdrop-blur-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Compass className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold tracking-tight text-foreground">Market-Wide Discovery</h2>
            <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/30 text-emerald-400">
              v1 Upstream Intelligence
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground max-w-xl">
            Surfaces research-worthy assets outside your current portfolio and watchlist. Applies strict multi-factor
            drawdown screening, valuation compression signals, and selective AI reasoning.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-muted/40 p-1 rounded-xl border border-border/50 text-xs">
            {(['US_LARGE_CAP', 'US_TECH_GROWTH', 'BIST_LIQUID'] as DiscoveryUniverse[]).map((u) => (
              <button
                key={u}
                onClick={() => setSelectedUniverse(u)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                  selectedUniverse === u
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {UNIVERSE_LABELS[u]?.label ?? u}
              </button>
            ))}
          </div>

          <Button
            size="sm"
            onClick={() => handleScan(false)}
            disabled={isScanning || isLoading}
            className="bg-emerald-600 hover:bg-emerald-500 text-white gap-2 font-medium"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            {isScanning ? 'Screening Universe...' : 'Scan Market Universe'}
          </Button>
        </div>
      </div>

      {/* Funnel Metrics Banner */}
      {run && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-border/50 bg-card/20 p-3.5 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-muted-foreground">Universe Scanned</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-foreground font-mono">
                {run.instruments_scanned}
              </span>
              <span className="text-[10px] text-muted-foreground">candidates</span>
            </div>
            <span className="text-[10px] text-muted-foreground/80 mt-1 truncate">
              {UNIVERSE_LABELS[run.universe as DiscoveryUniverse]?.label ?? run.universe}
            </span>
          </div>

          <div className="rounded-xl border border-border/50 bg-card/20 p-3.5 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-muted-foreground">Deterministic Signals</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-foreground font-mono">
                {run.candidates_filtered || run.candidates_surfaced}
              </span>
              <span className="text-[10px] text-emerald-400">passed filters</span>
            </div>
            <span className="text-[10px] text-muted-foreground/80 mt-1">Drawdowns, 52w lows & MAs</span>
          </div>

          <div className="rounded-xl border border-border/50 bg-card/20 p-3.5 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-muted-foreground">Deep AI Reasoning</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-foreground font-mono">
                {run.candidates_reasoned}
              </span>
              <span className="text-[10px] text-sky-400">shortlisted</span>
            </div>
            <span className="text-[10px] text-muted-foreground/80 mt-1">Codex Discovery Protocol</span>
          </div>

          <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3.5 flex flex-col justify-between">
            <span className="text-[11px] font-medium text-emerald-400">Surfaced in Inbox</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-emerald-300 font-mono">
                {activeCandidates.length}
              </span>
              <span className="text-[10px] text-muted-foreground">actionable</span>
            </div>
            <span className="text-[10px] text-emerald-400/70 mt-1">
              Last updated: {new Date(run.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-2xl border border-border/50 p-5 space-y-4 bg-card/30">
              <div className="flex justify-between items-center">
                <Skeleton className="h-6 w-28" />
                <Skeleton className="h-5 w-20" />
              </div>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-12 w-full" />
              <div className="flex gap-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-8 w-24" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Candidates List */}
      {!isLoading && activeCandidates.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {activeCandidates.map((cand) => {
            const isActing = actionInProgress === cand.id
            const news = cand.source_metadata?.recent_news || []
            const isNewsOpen = expandedNews[cand.id] || false

            return (
              <Card
                key={cand.id}
                className="border-border/60 bg-card/40 hover:border-emerald-500/30 transition-all rounded-2xl flex flex-col justify-between overflow-hidden shadow-sm"
              >
                <CardHeader className="p-5 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-base font-bold tracking-tight text-foreground font-mono">
                          {cand.symbol}
                        </span>
                        {cand.market_data_snapshot?.exchange && (
                          <span className="text-[10px] font-mono text-muted-foreground px-1.5 py-0.5 rounded bg-muted/40">
                            {cand.market_data_snapshot.exchange}
                          </span>
                        )}
                        {getStatusBadge(cand.status)}
                      </div>
                      <p className="text-xs text-muted-foreground truncate">{cand.name}</p>
                    </div>

                    <div className="text-right">
                      <div className="text-sm font-bold font-mono text-foreground">
                        {formatPrice(cand.current_price, cand.current_price_currency)}
                      </div>
                      <span className="text-[10px] text-muted-foreground">Current Price</span>
                    </div>
                  </div>

                  {/* Signals badges */}
                  <div className="flex flex-wrap gap-1.5 pt-2">
                    {(cand.signals || []).map((sig, idx) => (
                      <Badge
                        key={idx}
                        variant="secondary"
                        className="text-[10px] font-medium bg-muted/50 border-border/40 text-muted-foreground"
                      >
                        <TrendingDown className="h-2.5 w-2.5 mr-1 text-amber-400" />
                        {sig.label}
                      </Badge>
                    ))}
                    {cand.confidence && (
                      <Badge variant="outline" className="text-[10px] font-mono text-muted-foreground">
                        {cand.confidence} CONFIDENCE
                      </Badge>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="p-5 pt-1 space-y-3.5 flex-1 flex flex-col justify-between">
                  <div className="space-y-3">
                    {/* Primary reason */}
                    <div className="rounded-xl border border-border/50 bg-background/50 p-3 text-xs leading-relaxed text-foreground/90">
                      <span className="font-semibold text-foreground mr-1">Signal Context:</span>
                      {cand.primary_reason}
                    </div>

                    {/* Key Question & Risk */}
                    <div className="space-y-2 text-xs">
                      {cand.key_question && (
                        <div className="flex items-start gap-2 text-muted-foreground">
                          <HelpCircle className="h-3.5 w-3.5 text-sky-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold text-foreground/90">Key Question: </span>
                            {cand.key_question}
                          </div>
                        </div>
                      )}
                      {cand.key_risk && (
                        <div className="flex items-start gap-2 text-muted-foreground">
                          <ShieldAlert className="h-3.5 w-3.5 text-rose-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold text-foreground/90">Key Risk: </span>
                            {cand.key_risk}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Recent News preview if available */}
                    {news.length > 0 && (
                      <div className="pt-1">
                        <button
                          onClick={() => toggleNews(cand.id)}
                          className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground font-medium"
                        >
                          <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{news.length} Recent Headlines / Disclosures</span>
                          {isNewsOpen ? (
                            <ChevronUp className="h-3 w-3 ml-0.5" />
                          ) : (
                            <ChevronDown className="h-3 w-3 ml-0.5" />
                          )}
                        </button>

                        {isNewsOpen && (
                          <div className="mt-2 space-y-1.5 pl-2 border-l border-border/60">
                            {news.map((n: any, nIdx: number) => (
                              <div key={nIdx} className="text-[11px] text-muted-foreground">
                                <span className="font-medium text-foreground/80">{n.headline}</span>
                                {n.source && <span className="text-[10px] text-muted-foreground/60 ml-1.5">({n.source})</span>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions Bar (Strict Research & Watchlist Invariants: NO Buy/Sell!) */}
                  <div className="pt-3 border-t border-border/50 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        onClick={() => handleAddToWatchlist(cand)}
                        disabled={isActing}
                        className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 h-8 text-xs font-medium gap-1.5"
                      >
                        <BookmarkPlus className="h-3.5 w-3.5" />
                        Add to Watchlist
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleScreen(cand)}
                        disabled={isActing}
                        className="h-8 text-xs font-medium gap-1.5 text-sky-400 border-sky-500/30 hover:bg-sky-500/10"
                      >
                        <Search className="h-3.5 w-3.5" />
                        Screen Candidate
                      </Button>
                    </div>

                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDismiss(cand)}
                      disabled={isActing}
                      className="h-8 text-xs text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10"
                    >
                      Dismiss
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Calm Empty State */}
      {!isLoading && activeCandidates.length === 0 && (
        <div className="flex flex-col items-center justify-center p-12 text-center rounded-2xl border border-dashed border-border/60 bg-card/20 space-y-4">
          <div className="h-12 w-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Compass className="h-6 w-6" />
          </div>
          <div className="space-y-1 max-w-md">
            <h3 className="text-base font-bold text-foreground">Discovery Inbox is Calm</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              No assets in the screened universe currently satisfy the strict multi-factor dislocation and
              research-worthiness criteria. Next scheduled scan will run with your daily briefing.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => handleScan(true)}
            disabled={isScanning}
            variant="outline"
            className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 text-xs font-medium gap-1.5"
          >
            <RefreshCw className={`h-3 w-3 ${isScanning ? 'animate-spin' : ''}`} />
            Run On-Demand Scan Now
          </Button>
        </div>
      )}
    </div>
  )
}
