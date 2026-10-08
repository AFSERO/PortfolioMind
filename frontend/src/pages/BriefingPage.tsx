import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  Layers,
  Loader2,
  Newspaper,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { toast } from 'sonner'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAssets } from '@/hooks/useAssets'
import { useBriefing } from '@/hooks/useBriefing'
import { briefingService } from '@/services/briefingService'
import type { BriefingImpact, BriefingItem, BriefingMateriality } from '@/types'
import { cn } from '@/utils/cn'

type FilterTab = 'ALL' | 'ATTENTION' | 'PORTFOLIO' | 'WATCHLIST' | 'EARNINGS' | 'REGULATORY' | 'MACRO' | 'OPERATIONAL'

function formatProtocolName(protocol?: string | null) {
  if (!protocol) return 'Formal Review'
  switch (protocol) {
    case 'valuation-update':
      return 'Valuation Update'
    case 'earnings-review':
      return 'Earnings Review'
    case 'thesis-review':
      return 'Thesis Review'
    case 'technical-review':
      return 'Technical Review'
    case 'deep-research':
      return 'Deep Research'
    default:
      return protocol
        .split('-')
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ')
  }
}

function getItemAttentionState(item: BriefingItem): 'OPEN' | 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' | 'DECISION_REQUIRED' | 'RESOLVED' | 'NONE' {
  if (item.attention_state) {
    return item.attention_state
  }
  if (!item.review_required) {
    return 'NONE'
  }
  const status = item.source_metadata?.review_status
  if (status !== 'COMPLETED') {
    return 'OPEN'
  }
  const summary = item.source_metadata?.review_summary
  if (!summary) {
    return 'OPEN'
  }
  const rec = summary.recommendation?.toUpperCase()
  const thesis = summary.thesis_status?.toUpperCase()
  const tech = summary.technical_status?.toUpperCase()
  if (
    rec === 'REVIEW_REQUIRED' ||
    thesis === 'WEAKER' ||
    thesis === 'INVALIDATED' ||
    tech === 'REVIEW_REQUIRED' ||
    tech === 'DEVIATED'
  ) {
    return 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION'
  }
  if (rec === 'ADD' || rec === 'BUY' || rec === 'REDUCE' || rec === 'SELL') {
    return 'DECISION_REQUIRED'
  }
  return 'RESOLVED'
}

function getReviewActionConfig(item: BriefingItem) {
  const rec = item.source_metadata?.recommended_review?.toUpperCase().replace(/-/g, '_')
  switch (rec) {
    case 'VALUATION_UPDATE':
      return { label: 'Run Valuation Update', protocol: 'valuation-update' }
    case 'EARNINGS_REVIEW':
      return { label: 'Run Earnings Review', protocol: 'earnings-review' }
    case 'TECHNICAL_REVIEW':
      return { label: 'Run Technical Review', protocol: 'technical-review' }
    case 'DEEP_RESEARCH':
      return { label: 'Run Deep Research', protocol: 'deep-research' }
    case 'THESIS_REVIEW':
    default:
      return { label: 'Run Thesis Review', protocol: 'thesis-review' }
  }
}

function getImpactBadge(impact: BriefingImpact) {
  switch (impact) {
    case 'POSITIVE':
      return {
        label: 'Positive Impact',
        icon: TrendingUp,
        className: 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10',
      }
    case 'NEGATIVE':
      return {
        label: 'Negative Impact',
        icon: TrendingDown,
        className: 'border-rose-500/30 text-rose-300 bg-rose-500/10',
      }
    case 'MIXED':
      return {
        label: 'Mixed Signals',
        icon: RefreshCw,
        className: 'border-amber-500/30 text-amber-300 bg-amber-500/10',
      }
    case 'NEUTRAL':
    default:
      return {
        label: 'Neutral',
        icon: Clock,
        className: 'border-slate-500/30 text-slate-300 bg-slate-500/10',
      }
  }
}

function getMaterialityBadge(materiality: BriefingMateriality) {
  switch (materiality) {
    case 'CRITICAL':
    case 'HIGH':
      return {
        label: materiality === 'CRITICAL' ? 'Critical Attention' : 'High Materiality',
        className: 'border-rose-500/40 text-rose-300 bg-rose-500/15 font-bold',
      }
    case 'MEDIUM':
      return {
        label: 'Worth Knowing',
        className: 'border-teal-500/30 text-teal-300 bg-teal-500/10 font-semibold',
      }
    case 'LOW':
    default:
      return {
        label: 'Low Impact',
        className: 'border-slate-500/30 text-slate-400 bg-slate-500/10',
      }
  }
}

export default function BriefingPage() {
  const { briefing, stats, isLoading, isGenerating, generateBriefing, updateBriefingItem } = useBriefing()
  const { assets } = useAssets()
  const [currentTab, setCurrentTab] = useState<FilterTab>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [runningReviewId, setRunningReviewId] = useState<string | null>(null)

  const assetByInstrumentId = useMemo(() => {
    const map = new Map<string, string>()
    for (const a of assets) {
      if (a.instrument_id) {
        map.set(a.instrument_id, a.id)
      }
    }
    return map
  }, [assets])

  const handleRunReview = async (item: BriefingItem, forceRerun = false) => {
    setRunningReviewId(item.id)
    try {
      const res = await briefingService.runItemReview(item.id, forceRerun)
      if (res.status === 'COMPLETED') {
        const protocolLabel = formatProtocolName(res.protocol)
        toast.success(`${protocolLabel} completed successfully!`)

        const rec = res.summary?.recommendation?.toUpperCase()
        const thesis = res.summary?.thesis_status?.toUpperCase()
        const tech = res.summary?.technical_status?.toUpperCase()
        const isStillReviewAttention =
          rec === 'REVIEW_REQUIRED' ||
          thesis === 'WEAKER' ||
          thesis === 'INVALIDATED' ||
          tech === 'REVIEW_REQUIRED' ||
          tech === 'DEVIATED'

        const isActionableDecision =
          rec === 'ADD' || rec === 'BUY' || rec === 'REDUCE' || rec === 'SELL'

        let newAttState: 'OPEN' | 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' | 'DECISION_REQUIRED' | 'RESOLVED' | 'NONE' = 'RESOLVED'
        if (isStillReviewAttention) {
          newAttState = 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION'
        } else if (isActionableDecision) {
          newAttState = 'DECISION_REQUIRED'
        } else {
          newAttState = 'RESOLVED'
        }

        updateBriefingItem(item.id, {
          attention_state: newAttState,
          source_metadata: {
            ...(item.source_metadata || {}),
            triggered_review_id: res.review_id ?? undefined,
            review_status: 'COMPLETED',
            triggered_protocol: res.protocol ?? undefined,
            review_summary: res.summary ?? undefined,
            review_error: undefined,
          },
        })
      } else if (res.status === 'FAILED') {
        toast.error(`Review failed: ${res.error || 'Execution encountered an error'}`)
        updateBriefingItem(item.id, {
          attention_state: 'OPEN',
          source_metadata: {
            ...(item.source_metadata || {}),
            review_status: 'FAILED',
            review_error: res.error ?? 'Execution failed',
          },
        })
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Review execution failed'
      toast.error(msg)
      updateBriefingItem(item.id, {
        attention_state: 'OPEN',
        source_metadata: {
          ...(item.source_metadata || {}),
          review_status: 'FAILED',
          review_error: msg,
        },
      })
    } finally {
      setRunningReviewId(null)
    }
  }

  const handleRefresh = async () => {
    try {
      await generateBriefing(true)
      toast.success('Briefing generated successfully')
    } catch {
      toast.error('Failed to generate briefing')
    }
  }

  const items = briefing?.items ?? []

  const attentionItems = useMemo(() => items.filter((i) => i.review_required), [items])
  const unresolvedAttentionItems = useMemo(
    () =>
      items.filter((i) => {
        const state = getItemAttentionState(i)
        return (
          state === 'OPEN' ||
          state === 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION' ||
          state === 'DECISION_REQUIRED'
        )
      }),
    [items]
  )
  const portfolioItems = useMemo(() => items.filter((i) => i.is_portfolio), [items])
  const watchlistItems = useMemo(() => items.filter((i) => !i.is_portfolio), [items])

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Tab filter
      if (currentTab === 'ATTENTION' && !item.review_required) return false
      if (currentTab === 'PORTFOLIO' && !item.is_portfolio) return false
      if (currentTab === 'WATCHLIST' && item.is_portfolio) return false
      if (currentTab === 'EARNINGS' && item.category !== 'EARNINGS') return false
      if (currentTab === 'REGULATORY' && item.category !== 'REGULATORY') return false
      if (currentTab === 'MACRO' && item.category !== 'MACRO') return false
      if (currentTab === 'OPERATIONAL' && item.category !== 'OPERATIONAL') return false

      // Search filter
      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase()
      return (
        item.headline.toLowerCase().includes(q) ||
        item.summary.toLowerCase().includes(q) ||
        item.why_it_matters.toLowerCase().includes(q) ||
        (item.instrument_symbol && item.instrument_symbol.toLowerCase().includes(q)) ||
        (item.instrument_name && item.instrument_name.toLowerCase().includes(q))
      )
    })
  }, [items, currentTab, searchQuery])

  const attentionCount = stats?.attention_count ?? unresolvedAttentionItems.length
  const shownCount = stats?.items_shown ?? items.length
  const filteredCount = stats?.items_filtered ?? briefing?.items_filtered ?? 0

  const lastGenDate = briefing?.generated_at
    ? new Date(briefing.generated_at).toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        month: 'short',
        day: 'numeric',
      })
    : 'Not yet generated'

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Intelligence Briefing"
          description="Continuous event radar across portfolio holdings and watched securities."
          actions={
            <Button
              onClick={handleRefresh}
              disabled={isGenerating}
              className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5 h-8 text-xs font-semibold"
            >
              <RefreshCw className={cn('size-3.5', isGenerating && 'animate-spin')} />
              <span>{isGenerating ? 'Scanning Feeds...' : 'Refresh Briefing'}</span>
            </Button>
          }
        />

        {/* Pulse Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Needs Attention */}
          <div
            className={cn(
              'rounded-xl border p-4 space-y-2',
              attentionCount > 0 ? 'border-amber-500/40 bg-amber-500/5' : 'border-border/60 bg-card/40'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Needs Attention
              </span>
              {attentionCount > 0 ? (
                <ShieldAlert className="size-4 text-amber-400" />
              ) : (
                <CheckCircle2 className="size-4 text-teal-400" />
              )}
            </div>
            <div className="flex items-baseline gap-2">
              <span className={cn('text-2xl font-bold tracking-tight', attentionCount > 0 ? 'text-amber-400' : 'text-foreground')}>
                {attentionCount}
              </span>
              <span className="text-xs text-muted-foreground">developments</span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {attentionCount > 0 ? 'Material review recommended' : 'Portfolio & watchlist on track'}
            </p>
          </div>

          {/* Card 2: Worth Knowing */}
          <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Worth Knowing
              </span>
              <Newspaper className="size-4 text-teal-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight text-foreground">{shownCount}</span>
              <span className="text-xs text-muted-foreground">digest items</span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Medium &amp; high materiality developments
            </p>
          </div>

          {/* Card 3: Filtered Noise */}
          <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Filtered as Noise
              </span>
              <Layers className="size-4 text-slate-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight text-muted-foreground">{filteredCount}</span>
              <span className="text-xs text-muted-foreground">suppressed</span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Clickbait &amp; non-material mentions removed
            </p>
          </div>

          {/* Card 4: Radar Status */}
          <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Radar As Of
              </span>
              <Clock className="size-4 text-teal-400" />
            </div>
            <div className="text-base font-semibold text-foreground truncate">{lastGenDate}</div>
            <p className="text-[11px] text-teal-400/90 font-medium">
              {briefing?.trigger_type === 'SCHEDULED'
                ? 'Scheduled daily intelligence scan'
                : 'On-demand live intelligence scan'}
            </p>
          </div>
        </div>

        {/* Toolbar: Filters & Search */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-border/40 pb-3">
          {/* Filter tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <button
              type="button"
              onClick={() => setCurrentTab('ALL')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'ALL'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              All ({items.length})
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('ATTENTION')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'ATTENTION'
                  ? 'bg-amber-500/15 text-amber-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Needs Attention ({attentionItems.length})
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('PORTFOLIO')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'PORTFOLIO'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Portfolio ({portfolioItems.length})
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('WATCHLIST')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'WATCHLIST'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Watchlist ({watchlistItems.length})
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('EARNINGS')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'EARNINGS'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Earnings
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('REGULATORY')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'REGULATORY'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Regulatory
            </button>
            <button
              type="button"
              onClick={() => setCurrentTab('OPERATIONAL')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                currentTab === 'OPERATIONAL'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Operational
            </button>
          </div>

          {/* Search bar */}
          <div className="relative w-full sm:w-64 sm:shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search developments, symbols..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-full rounded-lg border border-border/60 bg-background/50 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>

        {/* Development Feed */}
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
        ) : filteredItems.length > 0 ? (
          <div className="space-y-4">
            {filteredItems.map((item) => {
              const impact = getImpactBadge(item.impact)
              const ImpactIcon = impact.icon
              const materiality = getMaterialityBadge(item.materiality)

              const pubDate = item.published_at
                ? new Date(item.published_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                : new Date(item.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                  })

              return (
                <div
                  key={item.id}
                  className={cn(
                    'rounded-xl border bg-card/40 p-4 sm:p-5 space-y-3.5 transition-all hover:border-border/80',
                    item.review_required
                      ? getItemAttentionState(item) === 'RESOLVED'
                        ? 'border-emerald-500/20 bg-emerald-500/[0.01]'
                        : 'border-amber-500/30 bg-amber-500/[0.02] shadow-sm shadow-amber-500/5'
                      : 'border-border/60'
                  )}
                >
                  {/* Top metadata row */}
                  <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-border/30 pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Portfolio vs Watchlist pill */}
                      <Badge
                        variant="outline"
                        className={cn(
                          'text-[10px] uppercase tracking-wider font-semibold',
                          item.is_portfolio
                            ? 'border-teal-500/30 text-teal-300 bg-teal-500/10'
                            : 'border-slate-500/30 text-slate-300 bg-slate-500/10'
                        )}
                      >
                        {item.is_portfolio ? 'Portfolio Holding' : 'Watched Instrument'}
                      </Badge>

                      {/* Instrument symbol */}
                      <span className="text-xs font-bold text-foreground font-mono">
                        {item.instrument_symbol || item.instrument_name}
                      </span>

                      {/* Category */}
                      <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-muted/60 text-muted-foreground font-medium">
                        {item.category}
                      </span>

                      {/* Materiality */}
                      <Badge variant="outline" className={cn('text-[10px] uppercase tracking-wider', materiality.className)}>
                        {materiality.label}
                      </Badge>

                      {/* Impact */}
                      <Badge variant="outline" className={cn('text-[10px] uppercase tracking-wider flex items-center gap-1', impact.className)}>
                        <ImpactIcon className="size-3" />
                        <span>{impact.label}</span>
                      </Badge>

                      {/* AI Assessed Badge if reasoning_source is CODEX or CODEX_CACHED */}
                      {(item.source_metadata?.reasoning_source === 'CODEX' || item.source_metadata?.reasoning_source === 'CODEX_CACHED') && (
                        <Badge
                          variant="outline"
                          className="text-[10px] uppercase tracking-wider flex items-center gap-1 border-violet-500/30 text-violet-300 bg-violet-500/10 font-semibold"
                          title={item.source_metadata.reasoning_source === 'CODEX_CACHED' ? 'AI Assessed (Cached)' : 'AI Assessed via Codex'}
                        >
                          <Sparkles className="size-2.5 text-violet-400" />
                          <span>AI Assessed</span>
                        </Badge>
                      )}

                      {/* Attention State Badge */}
                      {item.review_required && (() => {
                        const attState = getItemAttentionState(item)
                        if (attState === 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION') {
                          return (
                            <Badge variant="outline" className="text-[10px] uppercase tracking-wider flex items-center gap-1 border-amber-500/40 text-amber-300 bg-amber-500/15 font-semibold">
                              <AlertTriangle className="size-2.5 text-amber-400" />
                              <span>Still Needs Attention</span>
                            </Badge>
                          )
                        }
                        if (attState === 'DECISION_REQUIRED') {
                          return (
                            <Badge variant="outline" className="text-[10px] uppercase tracking-wider flex items-center gap-1 border-amber-500/40 text-amber-300 bg-amber-500/15 font-semibold">
                              <AlertCircle className="size-2.5 text-amber-400" />
                              <span>Decision Required</span>
                            </Badge>
                          )
                        }
                        if (attState === 'RESOLVED') {
                          return (
                            <Badge variant="outline" className="text-[10px] uppercase tracking-wider flex items-center gap-1 border-emerald-500/40 text-emerald-300 bg-emerald-500/15 font-semibold">
                              <CheckCircle2 className="size-2.5 text-emerald-400" />
                              <span>Attention Resolved</span>
                            </Badge>
                          )
                        }
                        return (
                          <Badge variant="outline" className="text-[10px] uppercase tracking-wider flex items-center gap-1 border-amber-500/30 text-amber-300 bg-amber-500/10 font-medium">
                            <AlertCircle className="size-2.5 text-amber-400" />
                            <span>Review Required</span>
                          </Badge>
                        )
                      })()}
                    </div>

                    <div className="flex items-center gap-3 text-xs text-muted-foreground ml-auto">
                      <span className="text-[11px] font-mono">{pubDate}</span>
                      {item.source_metadata?.url && (
                        <a
                          href={item.source_metadata.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-muted-foreground hover:text-teal-300 inline-flex items-center gap-1 transition-colors"
                        >
                          <span>{item.source_metadata.source || 'Source'}</span>
                          <ExternalLink className="size-3" />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Headline & Summary */}
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-foreground leading-snug">
                      {item.headline}
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {item.summary}
                    </p>
                  </div>

                  {/* Why it matters thesis explanation box & formal review loop */}
                  <div className="rounded-lg bg-teal-950/15 border border-teal-500/20 p-3 space-y-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400">
                          Why It Matters to Thesis
                        </span>
                        {item.source_metadata?.recommended_review && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            Review suggested: {item.source_metadata.recommended_review}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {item.why_it_matters}
                      </p>
                    </div>

                    {/* Integrated Formal Review Execution Box */}
                    {item.review_required && (
                      <div className="border-t border-teal-500/15 pt-2.5">
                        {(() => {
                          const isRunning = runningReviewId === item.id
                          const hasCompleted = item.source_metadata?.review_status === 'COMPLETED' || Boolean(item.source_metadata?.triggered_review_id)
                          const hasFailed = item.source_metadata?.review_status === 'FAILED'
                          const actionConfig = getReviewActionConfig(item)
                          const summary = item.source_metadata?.review_summary
                          const triggeredProtocol = item.source_metadata?.triggered_protocol || actionConfig.protocol
                          const assetId = assetByInstrumentId.get(item.instrument_id)

                          if (hasCompleted) {
                            const attState = getItemAttentionState(item)
                            const isStillAttention = attState === 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION'
                            const isDecisionRequired = attState === 'DECISION_REQUIRED'

                            return (
                              <div
                                className={cn(
                                  'rounded-lg p-3 space-y-2.5',
                                  isStillAttention || isDecisionRequired
                                    ? 'bg-amber-950/15 border border-amber-500/30'
                                    : 'bg-background/60 border border-emerald-500/20'
                                )}
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span
                                      className={cn(
                                        'inline-flex items-center gap-1.5 text-xs font-semibold',
                                        isStillAttention || isDecisionRequired ? 'text-amber-300' : 'text-emerald-300'
                                      )}
                                    >
                                      {isStillAttention || isDecisionRequired ? (
                                        <AlertTriangle className="size-3.5 text-amber-400 shrink-0" />
                                      ) : (
                                        <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
                                      )}
                                      <span>{formatProtocolName(triggeredProtocol)} Completed</span>
                                    </span>
                                    {isDecisionRequired ? (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] uppercase tracking-wider border-amber-500/40 text-amber-300 bg-amber-500/15 font-semibold"
                                      >
                                        Decision Required
                                      </Badge>
                                    ) : isStillAttention ? (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] uppercase tracking-wider border-amber-500/40 text-amber-300 bg-amber-500/15 font-semibold"
                                      >
                                        Still Requires Attention
                                      </Badge>
                                    ) : (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] uppercase tracking-wider border-emerald-500/40 text-emerald-300 bg-emerald-500/15 font-semibold"
                                      >
                                        Attention Resolved
                                      </Badge>
                                    )}
                                    {summary?.state_updated ? (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] uppercase tracking-wider border-emerald-500/40 text-emerald-300 bg-emerald-500/15 font-semibold"
                                      >
                                        State Updated
                                      </Badge>
                                    ) : (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] uppercase tracking-wider border-slate-500/30 text-slate-400 bg-slate-500/10 font-normal"
                                      >
                                        State Confirmed
                                      </Badge>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-1.5 ml-auto">
                                    <Link to={assetId ? `/assets/${assetId}` : '/watchlist'}>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-6 px-2 text-[11px] border-teal-500/30 text-teal-300 hover:bg-teal-500/10 gap-1"
                                      >
                                        <span>{assetId ? 'View Asset' : 'View Watchlist'}</span>
                                        <ArrowUpRight className="size-3" />
                                      </Button>
                                    </Link>
                                    <Link to="/decisions">
                                      <Button
                                        size="sm"
                                        variant={isDecisionRequired ? 'default' : 'ghost'}
                                        className={cn(
                                          'h-6 px-2 text-[11px] gap-1',
                                          isDecisionRequired
                                            ? 'bg-amber-600 hover:bg-amber-700 text-white font-medium'
                                            : 'text-muted-foreground hover:text-foreground'
                                        )}
                                      >
                                        <span>{isDecisionRequired ? 'Record Decision' : 'Log'}</span>
                                        <ArrowUpRight className="size-3" />
                                      </Button>
                                    </Link>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => handleRunReview(item, true)}
                                      disabled={isRunning}
                                      className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                                      title="Re-run review with fresh data"
                                    >
                                      <RefreshCw className={cn('size-3', isRunning && 'animate-spin')} />
                                    </Button>
                                  </div>
                                </div>

                                {/* Outcome summary tags */}
                                {summary && (
                                  <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                                    {summary.recommendation && (
                                      <span className="px-2 py-0.5 rounded bg-teal-500/10 border border-teal-500/20 text-teal-300 font-medium">
                                        Rec: <strong className="font-semibold">{summary.recommendation}</strong>
                                        {summary.confidence && <span className="opacity-75"> ({summary.confidence})</span>}
                                      </span>
                                    )}
                                    {summary.valuation_status && (
                                      <span className="px-2 py-0.5 rounded bg-muted/60 text-muted-foreground font-medium">
                                        Valuation: <strong className="text-foreground">{summary.valuation_status}</strong>
                                      </span>
                                    )}
                                    {summary.thesis_status && (
                                      <span className="px-2 py-0.5 rounded bg-muted/60 text-muted-foreground font-medium">
                                        Thesis: <strong className="text-foreground">{summary.thesis_status}</strong>
                                      </span>
                                    )}
                                  </div>
                                )}

                                {summary?.human_brief && (
                                  <p className="text-[11px] text-slate-300/90 leading-relaxed italic border-l-2 border-emerald-500/40 pl-2">
                                    "{summary.human_brief}"
                                  </p>
                                )}
                              </div>
                            )
                          }

                          if (hasFailed) {
                            return (
                              <div className="rounded-lg bg-rose-950/20 border border-rose-500/25 p-2.5 flex flex-wrap items-center justify-between gap-2">
                                <div className="flex items-center gap-2 text-xs text-rose-300">
                                  <AlertTriangle className="size-3.5 text-rose-400 shrink-0" />
                                  <span className="line-clamp-1">
                                    Review failed: {item.source_metadata?.review_error || 'Execution encountered an error'}
                                  </span>
                                </div>
                                <Button
                                  size="sm"
                                  onClick={() => handleRunReview(item, true)}
                                  disabled={isRunning}
                                  className="h-6 px-2.5 text-xs bg-rose-600 hover:bg-rose-700 text-white font-medium flex items-center gap-1.5"
                                >
                                  {isRunning ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
                                  <span>Retry Review</span>
                                </Button>
                              </div>
                            )
                          }

                          return (
                            <div className="flex items-center justify-between gap-3 pt-0.5">
                              <p className="text-[11px] text-muted-foreground">
                                Intentional formal review: runs canonical Finance protocol via Codex to update structured intelligence state.
                              </p>
                              <Button
                                size="sm"
                                onClick={() => handleRunReview(item, false)}
                                disabled={isRunning}
                                className="h-7 text-xs bg-amber-600 hover:bg-amber-700 text-white font-medium flex items-center gap-1.5 shrink-0 shadow-sm shadow-amber-600/20"
                              >
                                {isRunning ? (
                                  <>
                                    <Loader2 className="size-3 animate-spin" />
                                    <span>Running {actionConfig.label}...</span>
                                  </>
                                ) : (
                                  <>
                                    <Sparkles className="size-3" />
                                    <span>{actionConfig.label}</span>
                                  </>
                                )}
                              </Button>
                            </div>
                          )
                        })()}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-border/80 p-12 text-center bg-card/20 space-y-4">
            <div className="mx-auto size-12 rounded-full bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400">
              <CheckCircle2 className="size-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-foreground">
                {currentTab === 'ATTENTION'
                  ? '0 developments need attention'
                  : 'No matching briefing items'}
              </h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                {currentTab === 'ATTENTION'
                  ? 'Your portfolio holdings and watchlist securities are currently calm and on track. Noise was filtered out.'
                  : 'Click "Refresh Briefing" above to scan live evidence feeds for your portfolio holdings and watched securities.'}
              </p>
            </div>
            {items.length === 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isGenerating}
                className="h-8 text-xs border-teal-500/30 text-teal-300 hover:bg-teal-500/10"
              >
                <Sparkles className="size-3.5 mr-1" />
                Run First Radar Scan
              </Button>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
