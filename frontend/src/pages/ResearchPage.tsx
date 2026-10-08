import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  Clock,
  Compass,
  Layers,
  ListOrdered,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import AssetTypeBadge from '@/components/assets/AssetTypeBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { DiscoveryInbox } from '@/components/research/DiscoveryInbox'
import { useAssets } from '@/hooks/useAssets'
import { useInstruments } from '@/hooks/useInstruments'
import { useOpportunities } from '@/hooks/useOpportunities'
import type { ResearchQueueItem } from '@/types'
import { cn } from '@/utils/cn'

export default function ResearchPage() {
  const [activeView, setActiveView] = useState<'pipeline' | 'discovery' | 'queue'>('pipeline')
  const [evaluating, setEvaluating] = useState(false)
  const [launchingId, setLaunchingId] = useState<string | null>(null)

  const { instruments, isLoading: instLoading } = useInstruments()
  const { assets, isLoading: assetsLoading } = useAssets()
  const {
    researchQueue,
    isLoading: queueLoading,
    evaluate,
    launchReview,
  } = useOpportunities()

  const isLoading = instLoading || assetsLoading

  // Pipeline stage items
  const ownedInstrumentIds = new Set(assets.map((a) => a.instrument_id).filter(Boolean))
  const ownedItems = assets.filter((a) => a.instrument != null)
  const candidateItems = instruments.filter((i) => !ownedInstrumentIds.has(i.id))

  const handleEvaluate = async () => {
    setEvaluating(true)
    try {
      const summary = await evaluate({ force_refresh: true })
      const found = summary?.opportunities_found ?? 0
      toast.success(
        found > 0
          ? `Opportunities evaluated: ${found} candidate(s) deserve research.`
          : 'Opportunity evaluation completed. Pipeline is calm.'
      )
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Evaluation failed')
    } finally {
      setEvaluating(false)
    }
  }

  const handleRunSuggested = async (item: ResearchQueueItem) => {
    setLaunchingId(item.instrument_id)
    try {
      await launchReview(item.instrument_id, item.suggested_next_step)
      toast.success(`Formal review (${item.suggested_next_step}) initiated and applied.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to launch review')
    } finally {
      setLaunchingId(null)
    }
  }

  const renderQueueItem = (item: ResearchQueueItem, highlight: boolean = false) => {
    return (
      <div
        key={item.instrument_id}
        className={`rounded-xl border p-4 flex flex-col justify-between transition-all space-y-3 ${
          highlight
            ? 'border-emerald-500/30 bg-emerald-950/15 shadow-sm'
            : 'border-border/60 bg-card/40 hover:border-teal-500/30'
        }`}
      >
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-foreground">
                {item.symbol ?? item.name}
              </span>
              {item.exchange && (
                <span className="text-[10px] font-mono text-muted-foreground px-1.5 py-0.5 rounded bg-muted/40">
                  {item.exchange}
                </span>
              )}
              <Badge variant="outline" className="text-[10px] font-mono">
                {item.research_stage}
              </Badge>
            </div>
            <AssetTypeBadge type={item.asset_type as any} size="sm" />
          </div>
          <p className="text-xs text-muted-foreground truncate">{item.name}</p>

          {(item.target_entry_min != null || item.current_price != null) && (
            <div className="flex items-center justify-between text-[11px] bg-background/50 px-2 py-1 rounded border border-border/30">
              <span className="text-muted-foreground">
                Target: {item.target_entry_min != null && item.target_entry_max != null
                  ? `$${item.target_entry_min}–$${item.target_entry_max}`
                  : 'Flexible'}
              </span>
              {item.current_price != null && (
                <span className="font-mono text-foreground font-semibold">
                  ${item.current_price.toFixed(2)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Why Now / Opportunity Details */}
        <div className="pt-2 border-t border-border/30 space-y-2 text-xs">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground uppercase font-semibold">
                Why now · {item.primary_driver}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
                {item.reason}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-border/20 text-[10px]">
            <span className="flex items-center gap-1 text-muted-foreground">
              <Clock className="size-3" />
              Freshness: {item.research_freshness}
            </span>

            {item.suggested_next_step && item.suggested_next_step !== 'NONE' && (
              <Button
                size="sm"
                variant={highlight ? 'default' : 'outline'}
                disabled={launchingId === item.instrument_id}
                onClick={() => handleRunSuggested(item)}
                className={`h-6 text-[10px] font-semibold gap-1 ${
                  highlight
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    : 'text-teal-400 hover:text-teal-300'
                }`}
              >
                <span>{launchingId === item.instrument_id ? 'Running...' : `Run ${item.suggested_next_step.replace('_', ' ')}`}</span>
                <ArrowUpRight className="size-3" />
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Research Pipeline"
          description="Track active investment theses across discovery, financial modeling, valuation, and thesis formulation."
          actions={
            <div className="flex items-center gap-2">
              <div className="flex items-center rounded-lg border border-border/60 bg-card/40 p-0.5">
                <button
                  type="button"
                  onClick={() => setActiveView('discovery')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    activeView === 'discovery'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Compass className="size-3.5" />
                  <span>Discovery</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView('queue')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    activeView === 'queue'
                      ? 'bg-teal-600 text-white shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <ListOrdered className="size-3.5" />
                  <span>Priority Queue</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView('pipeline')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    activeView === 'pipeline'
                      ? 'bg-teal-600 text-white shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Layers className="size-3.5" />
                  <span>Pipeline Stages</span>
                </button>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={handleEvaluate}
                disabled={evaluating}
                className="h-8 text-xs font-medium gap-1.5 border-border/60 hover:border-teal-500/30"
              >
                <Sparkles className={`size-3.5 text-teal-400 ${evaluating ? 'animate-spin' : ''}`} />
                <span>{evaluating ? 'Evaluating...' : 'Refresh Opportunities'}</span>
              </Button>
            </div>
          }
        />

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-80 rounded-xl bg-card/40 border border-border/60" />
            ))}
          </div>
        ) : activeView === 'discovery' ? (
          <DiscoveryInbox />
        ) : activeView === 'queue' ? (
          /* Prioritized Queue View */
          queueLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-44 rounded-xl bg-card/40 border border-border/60" />
              ))}
            </div>
          ) : (
          <div className="space-y-6">
            {/* Section 1: Research Now */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
                  <h2 className="text-sm font-semibold text-foreground">Research Now</h2>
                  <span className="text-xs text-muted-foreground">
                    Candidates where material evidence or price entry warrants immediate attention
                  </span>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  {researchQueue?.research_now.length ?? 0}
                </Badge>
              </div>

              {!researchQueue || researchQueue.research_now.length === 0 ? (
                <div className="rounded-xl border border-border/40 bg-card/20 p-5 text-center text-xs text-muted-foreground">
                  No candidates currently require immediate research. Active theses are on track.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {researchQueue.research_now.map((item) => renderQueueItem(item, true))}
                </div>
              )}
            </div>

            {/* Section 2: Research Soon */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-amber-400" />
                  <h2 className="text-sm font-semibold text-foreground">Research Soon</h2>
                  <span className="text-xs text-muted-foreground">
                    Stale analyses, emerging catalysts, or screened candidates
                  </span>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  {researchQueue?.research_soon.length ?? 0}
                </Badge>
              </div>

              {!researchQueue || researchQueue.research_soon.length === 0 ? (
                <div className="rounded-xl border border-border/40 bg-card/20 p-4 text-center text-xs text-muted-foreground">
                  No candidates awaiting near-term research review.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {researchQueue.research_soon.map((item) => renderQueueItem(item, false))}
                </div>
              )}
            </div>

            {/* Section 3: Waiting for Price */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-teal-400" />
                  <h2 className="text-sm font-semibold text-foreground">Waiting for Price / In Watch</h2>
                  <span className="text-xs text-muted-foreground">
                    Theses formulated; awaiting target entry bounds before initiating review
                  </span>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  {researchQueue?.waiting.length ?? 0}
                </Badge>
              </div>

              {!researchQueue || researchQueue.waiting.length === 0 ? (
                <div className="rounded-xl border border-border/40 bg-card/20 p-4 text-center text-xs text-muted-foreground">
                  No formulated candidates awaiting entry zone prices.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {researchQueue.waiting.map((item) => renderQueueItem(item, false))}
                </div>
              )}
            </div>
          </div>
          )
        ) : (
          /* Pipeline Stages View (Classic 4 columns) */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-start">
            {/* Stage 1: Screening */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2.5">
                <div>
                  <h3 className="text-xs font-semibold text-foreground">Screening</h3>
                  <p className="text-[10px] text-muted-foreground">Initial candidates</p>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono">
                  {candidateItems.length}
                </Badge>
              </div>

              {candidateItems.length === 0 ? (
                <p className="text-xs text-muted-foreground py-6 text-center">
                  No unowned candidates currently in screening. Add from Watchlist.
                </p>
              ) : (
                <div className="space-y-2">
                  {candidateItems.map((inst) => (
                    <div
                      key={inst.id}
                      className="rounded-lg border border-border/40 bg-background/50 p-2.5 text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground">{inst.symbol ?? inst.name}</span>
                        <AssetTypeBadge type={inst.asset_type} size="sm" />
                      </div>
                      <p className="text-[11px] text-muted-foreground truncate">{inst.name}</p>
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                        <span>{inst.exchange ?? 'Global'}</span>
                        <span className="text-teal-400 font-medium">Screening</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Stage 2: Deep Research */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2.5">
                <div>
                  <h3 className="text-xs font-semibold text-foreground">Deep Research</h3>
                  <p className="text-[10px] text-muted-foreground">Valuation & moat</p>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono">
                  {researchQueue?.stage_counts?.RESEARCHING ?? 0}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground py-6 text-center">
                No active in-depth research runs in progress.
              </p>
            </div>

            {/* Stage 3: Ready / Waiting for Price */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2.5">
                <div>
                  <h3 className="text-xs font-semibold text-foreground">Waiting for Price</h3>
                  <p className="text-[10px] text-muted-foreground">Pre-formulated entry</p>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono">
                  {researchQueue?.stage_counts?.WAITING_FOR_PRICE ?? 0}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground py-6 text-center">
                {researchQueue?.stage_counts?.WAITING_FOR_PRICE
                  ? `${researchQueue.stage_counts.WAITING_FOR_PRICE} candidate(s) awaiting price zone.`
                  : 'No formulated theses awaiting entry zones.'}
              </p>
            </div>

            {/* Stage 4: Owned / Continuous Review */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-border/40 pb-2.5">
                <div>
                  <h3 className="text-xs font-semibold text-foreground">Owned Holdings</h3>
                  <p className="text-[10px] text-muted-foreground">Continuous monitoring</p>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono">
                  {ownedItems.length}
                </Badge>
              </div>

              {ownedItems.length === 0 ? (
                <p className="text-xs text-muted-foreground py-6 text-center">
                  No positions currently owned.
                </p>
              ) : (
                <div className="space-y-2">
                  {ownedItems.map((asset) => {
                    const intel = asset.instrument?.intelligence_state
                    return (
                      <Link
                        key={asset.id}
                        to={`/assets/${asset.id}`}
                        className="block rounded-lg border border-border/40 bg-background/50 p-2.5 text-xs space-y-1.5 hover:border-teal-500/30 transition-all"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-foreground">
                            {asset.symbol ?? asset.name}
                          </span>
                          <span className={cn('text-[10px] font-semibold', intel?.recommendation ? 'text-teal-300' : 'text-muted-foreground/60')}>
                            {intel?.recommendation ?? 'NOT REVIEWED'}
                          </span>
                        </div>
                        <p className="text-[11px] text-muted-foreground truncate">{asset.name}</p>
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                          <span>Thesis: {intel?.thesis_status ?? 'Active'}</span>
                          <ArrowUpRight className="size-3 text-teal-400" />
                        </div>
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
