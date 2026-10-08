import { useState } from 'react'
import {
  Clock,
  Crosshair,
  Edit2,
  Eye,
  Plus,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import AssetTypeBadge from '@/components/assets/AssetTypeBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { useInstruments } from '@/hooks/useInstruments'
import { useOpportunities } from '@/hooks/useOpportunities'
import type {
  AssetType,
  ResearchStage,
  WatchlistItem,
  WatchlistPriority,
} from '@/types'

export default function WatchlistPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const { instruments, isLoading: instLoading, createInstrument } = useInstruments()
  const {
    watchlist,
    isLoading: oppLoading,
    evaluate,
    addToWatchlist,
    updateWatchlistItem,
    launchReview,
  } = useOpportunities()

  const [addOpen, setAddOpen] = useState(false)
  const [editItem, setEditItem] = useState<WatchlistItem | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [launchingId, setLaunchingId] = useState<string | null>(null)

  // Form state for adding
  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('')
  const [assetType, setAssetType] = useState<AssetType>('STOCK')
  const [exchange, setExchange] = useState('')
  const [researchStage, setResearchStage] = useState<ResearchStage>('DISCOVERED')
  const [priority, setPriority] = useState<WatchlistPriority>('MEDIUM')
  const [whyInteresting, setWhyInteresting] = useState('')
  const [targetMin, setTargetMin] = useState('')
  const [targetMax, setTargetMax] = useState('')

  // Form state for editing
  const [editStage, setEditStage] = useState<ResearchStage>('DISCOVERED')
  const [editPriority, setEditPriority] = useState<WatchlistPriority>('MEDIUM')
  const [editWhy, setEditWhy] = useState('')
  const [editMin, setEditMin] = useState('')
  const [editMax, setEditMax] = useState('')
  const [editCatalyst, setEditCatalyst] = useState('')

  const isLoading = instLoading && oppLoading

  // Combined candidates: prefer structured watchlist items, fallback to instruments
  const candidates: Array<{
    id: string
    instrument_id: string
    name: string
    symbol?: string | null
    asset_type: AssetType
    exchange?: string | null
    research_stage: ResearchStage
    priority: WatchlistPriority
    why_interesting?: string | null
    target_entry_min?: number | null
    target_entry_max?: number | null
    current_price?: number | null
    current_price_currency?: string | null
    opportunity?: any
    intelligence_state?: any
    watchlistItem?: WatchlistItem
  }> = []

  if (watchlist && watchlist.length > 0) {
    for (const w of watchlist) {
      const inst = w.instrument
      candidates.push({
        id: w.id,
        instrument_id: w.instrument_id,
        name: inst?.name || 'Unknown',
        symbol: inst?.symbol,
        asset_type: inst?.asset_type || 'STOCK',
        exchange: inst?.exchange,
        research_stage: w.research_stage,
        priority: w.priority,
        why_interesting: w.why_interesting,
        target_entry_min: w.target_entry_min,
        target_entry_max: w.target_entry_max,
        current_price: w.current_price,
        current_price_currency: w.current_price_currency,
        opportunity: w.opportunity,
        intelligence_state: inst?.intelligence_state,
        watchlistItem: w,
      })
    }
  } else if (instruments && instruments.length > 0) {
    for (const inst of instruments) {
      candidates.push({
        id: inst.id,
        instrument_id: inst.id,
        name: inst.name,
        symbol: inst.symbol,
        asset_type: inst.asset_type,
        exchange: inst.exchange,
        research_stage: 'DISCOVERED',
        priority: 'MEDIUM',
        opportunity: null,
        intelligence_state: inst.intelligence_state,
      })
    }
  }

  const filtered = candidates.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      c.name.toLowerCase().includes(q) ||
      (c.symbol && c.symbol.toLowerCase().includes(q))
    )
  })

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Instrument name is required')
      return
    }
    setSubmitting(true)
    try {
      if (addToWatchlist) {
        await addToWatchlist({
          name: name.trim(),
          symbol: symbol.trim() ? symbol.trim().toUpperCase() : undefined,
          asset_type: assetType,
          exchange: exchange.trim() ? exchange.trim().toUpperCase() : undefined,
          research_stage: researchStage,
          priority,
          why_interesting: whyInteresting.trim() || undefined,
          target_entry_min: targetMin ? parseFloat(targetMin) : undefined,
          target_entry_max: targetMax ? parseFloat(targetMax) : undefined,
        })
      } else {
        await createInstrument({
          name: name.trim(),
          symbol: symbol.trim() ? symbol.trim().toUpperCase() : undefined,
          asset_type: assetType,
          exchange: exchange.trim() ? exchange.trim().toUpperCase() : undefined,
        })
      }
      toast.success(`${name} added to watchlist`)
      setName('')
      setSymbol('')
      setExchange('')
      setWhyInteresting('')
      setTargetMin('')
      setTargetMax('')
      setAddOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add instrument')
    } finally {
      setSubmitting(false)
    }
  }

  const openEdit = (c: typeof candidates[0]) => {
    if (c.watchlistItem) {
      setEditItem(c.watchlistItem)
      setEditStage(c.research_stage)
      setEditPriority(c.priority)
      setEditWhy(c.why_interesting || '')
      setEditMin(c.target_entry_min != null ? String(c.target_entry_min) : '')
      setEditMax(c.target_entry_max != null ? String(c.target_entry_max) : '')
      setEditCatalyst(c.watchlistItem.key_catalyst || '')
    }
  }

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editItem) return
    setSubmitting(true)
    try {
      await updateWatchlistItem(editItem.id, {
        research_stage: editStage,
        priority: editPriority,
        why_interesting: editWhy.trim() || undefined,
        target_entry_min: editMin ? parseFloat(editMin) : undefined,
        target_entry_max: editMax ? parseFloat(editMax) : undefined,
        key_catalyst: editCatalyst.trim() || undefined,
      })
      toast.success('Candidate updated')
      setEditItem(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update candidate')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEvaluateAll = async () => {
    setEvaluating(true)
    try {
      const summary = await evaluate({ force_refresh: true })
      const found = summary?.opportunities_found ?? 0
      toast.success(
        found > 0
          ? `Opportunity evaluation complete: ${found} candidate(s) deserve research.`
          : 'Opportunity evaluation complete. Watchlist is calm and up-to-date.'
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Opportunity evaluation failed')
    } finally {
      setEvaluating(false)
    }
  }

  const handleLaunchReview = async (instrumentId: string, protocol?: string) => {
    setLaunchingId(instrumentId)
    try {
      await launchReview(instrumentId, protocol)
      toast.success('Formal research review launched and applied.')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to launch review')
    } finally {
      setLaunchingId(null)
    }
  }

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Watchlist"
          description="Evaluate and monitor investment candidates awaiting desirable valuation or strategic entry zones."
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleEvaluateAll}
                disabled={evaluating}
                className="h-8 text-xs font-medium gap-1.5 border-border/60 hover:border-teal-500/30"
              >
                <Sparkles className={`size-3.5 text-teal-400 ${evaluating ? 'animate-spin' : ''}`} />
                <span>{evaluating ? 'Evaluating...' : 'Evaluate Opportunities'}</span>
              </Button>
              <Button
                onClick={() => setAddOpen(true)}
                className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5 h-8 text-xs font-semibold"
              >
                <Plus className="size-3.5" />
                <span>Add Candidate</span>
              </Button>
            </div>
          }
        />

        {/* Search & Stats Filter */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search watchlist by ticker or name..."
              className="h-8 w-full rounded-lg border border-border/60 bg-background/50 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <span className="text-xs text-muted-foreground font-mono">
            {filtered.length} candidates tracked
          </span>
        </div>

        {/* Candidate Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-44 rounded-xl bg-card/50 border border-border/60" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-border/60 bg-card/40 py-16 px-4 text-center">
            <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-teal-500/10 text-teal-400">
              <Eye className="size-5" />
            </div>
            <p className="text-sm font-semibold text-foreground">Your watchlist is empty</p>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground">
              Add securities you are evaluating or awaiting favorable entry prices before initiating a position.
            </p>
            <Button
              size="sm"
              onClick={() => setAddOpen(true)}
              className="mt-4 bg-teal-600 hover:bg-teal-700 text-white text-xs gap-1.5"
            >
              <Plus className="size-3.5" />
              Add First Candidate
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((c) => {
              const opp = c.opportunity
              const oppStatus = opp?.status || 'NO_CHANGE'
              const freshness = opp?.research_freshness || 'UNKNOWN'

              let oppBadge = (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted/40 text-muted-foreground">
                  MONITORING
                </span>
              )
              if (oppStatus === 'RESEARCH_NOW') {
                oppBadge = (
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    <Zap className="size-2.5" /> RESEARCH NOW
                  </span>
                )
              } else if (oppStatus === 'RESEARCH_SOON') {
                oppBadge = (
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    RESEARCH SOON
                  </span>
                )
              } else if (oppStatus === 'WATCH') {
                oppBadge = (
                  <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20">
                    WATCH
                  </span>
                )
              }

              return (
                <div
                  key={c.id}
                  className={`rounded-xl border bg-card/40 p-4 flex flex-col justify-between transition-all space-y-3 ${
                    oppStatus === 'RESEARCH_NOW'
                      ? 'border-emerald-500/30 bg-emerald-950/10 shadow-sm'
                      : oppStatus === 'RESEARCH_SOON'
                      ? 'border-amber-500/30 bg-amber-950/10 shadow-sm'
                      : 'border-border/60 hover:border-teal-500/30'
                  }`}
                >
                  <div className="space-y-2">
                    {/* Header: Symbol & Badges */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-foreground">
                          {c.symbol ?? c.name}
                        </span>
                        {c.exchange && (
                          <span className="text-[10px] font-mono text-muted-foreground px-1 py-0.5 rounded bg-muted/40">
                            {c.exchange}
                          </span>
                        )}
                        <Badge variant="outline" className="text-[10px] font-mono text-xs">
                          {c.research_stage}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <AssetTypeBadge type={c.asset_type} size="sm" />
                        {c.watchlistItem && (
                          <button
                            type="button"
                            onClick={() => openEdit(c)}
                            title="Edit Candidate Parameters"
                            className="p-1 rounded text-muted-foreground/60 hover:text-foreground hover:bg-muted/40 transition-colors"
                          >
                            <Edit2 className="size-3" />
                          </button>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground truncate">{c.name}</p>

                    {/* Target Range & Price context */}
                    {(c.target_entry_min != null || c.target_entry_max != null || c.current_price != null) && (
                      <div className="flex items-center justify-between text-[11px] bg-background/50 px-2.5 py-1.5 rounded-lg border border-border/30">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Crosshair className="size-3 text-teal-400" />
                          <span>Target:</span>
                          <span className="font-mono text-foreground font-medium">
                            {c.target_entry_min != null && c.target_entry_max != null
                              ? `$${c.target_entry_min} – $${c.target_entry_max}`
                              : c.target_entry_min != null
                              ? `> $${c.target_entry_min}`
                              : `< $${c.target_entry_max}`}
                          </span>
                        </div>
                        {c.current_price != null && (
                          <div className="font-mono text-xs font-semibold text-foreground">
                            ${c.current_price.toFixed(2)}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Opportunity & Freshness */}
                  <div className="pt-2 border-t border-border/30 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground uppercase font-semibold">
                        Opportunity Status
                      </span>
                      {oppBadge}
                    </div>

                    {opp?.reason && (
                      <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
                        {opp.reason}
                      </p>
                    )}

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" />
                        Freshness: {freshness}
                      </span>
                      {opp?.suggested_next_step && opp.suggested_next_step !== 'NONE' && (
                        <button
                          type="button"
                          disabled={launchingId === c.instrument_id}
                          onClick={() => handleLaunchReview(c.instrument_id, opp.suggested_next_step)}
                          className="font-medium text-teal-400 hover:text-teal-300 underline underline-offset-2 transition-colors disabled:opacity-50"
                        >
                          {launchingId === c.instrument_id ? 'Launching...' : `Run ${opp.suggested_next_step.replace('_', ' ')} →`}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Add Candidate Dialog */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold">Add Watchlist Candidate</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Track a security or research candidate awaiting desirable valuation or strategic entry zones.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleAdd} className="space-y-4 py-2 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="inst-name" className="text-xs">Instrument Name *</Label>
                <Input
                  id="inst-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Taiwan Semiconductor Manufacturing"
                  className="h-8 text-xs"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="inst-symbol" className="text-xs">Ticker / Symbol</Label>
                  <Input
                    id="inst-symbol"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="e.g. TSM"
                    className="h-8 text-xs font-mono uppercase"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="inst-exchange" className="text-xs">Exchange / Venue</Label>
                  <Input
                    id="inst-exchange"
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    placeholder="e.g. NYSE, NASDAQ"
                    className="h-8 text-xs font-mono uppercase"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="inst-type" className="text-xs">Asset Category</Label>
                <select
                  id="inst-type"
                  value={assetType}
                  onChange={(e) => setAssetType(e.target.value as AssetType)}
                  className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="STOCK">Stock / Equity</option>
                  <option value="CRYPTO">Crypto</option>
                  <option value="PRECIOUS_METALS">Precious Metals</option>
                  <option value="FUND">Fund / ETF</option>
                  <option value="FOREX">Forex</option>
                  <option value="REAL_ESTATE">Real Estate</option>
                  <option value="CUSTOM">Custom</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="inst-stage" className="text-xs">Research Stage</Label>
                  <select
                    id="inst-stage"
                    value={researchStage}
                    onChange={(e) => setResearchStage(e.target.value as ResearchStage)}
                    className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="DISCOVERED">1. DISCOVERED</option>
                    <option value="SCREENED">2. SCREENED</option>
                    <option value="RESEARCHING">3. RESEARCHING</option>
                    <option value="VALUED">4. VALUED</option>
                    <option value="READY">5. READY</option>
                    <option value="WAITING_FOR_PRICE">6. WAITING FOR PRICE</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="inst-priority" className="text-xs">Watchlist Priority</Label>
                  <select
                    id="inst-priority"
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as WatchlistPriority)}
                    className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High (Active Research)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="target-min" className="text-xs">Target Entry Min ($)</Label>
                  <Input
                    id="target-min"
                    type="number"
                    step="any"
                    value={targetMin}
                    onChange={(e) => setTargetMin(e.target.value)}
                    placeholder="e.g. 140.00"
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="target-max" className="text-xs">Target Entry Max ($)</Label>
                  <Input
                    id="target-max"
                    type="number"
                    step="any"
                    value={targetMax}
                    onChange={(e) => setTargetMax(e.target.value)}
                    placeholder="e.g. 150.00"
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="why-interesting" className="text-xs">Why Interesting / Thesis Hook</Label>
                <Input
                  id="why-interesting"
                  value={whyInteresting}
                  onChange={(e) => setWhyInteresting(e.target.value)}
                  placeholder="e.g. Dominant foundry moat, AI packaging inflection"
                  className="h-8 text-xs"
                />
              </div>

              <DialogFooter className="pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAddOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={submitting}
                  className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold"
                >
                  {submitting ? 'Adding...' : 'Add to Watchlist'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Edit Candidate Dialog */}
        <Dialog open={editItem != null} onOpenChange={(open) => !open && setEditItem(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold">
                Edit Candidate Parameters
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Update research stage, target entry bounds, or conviction notes.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSaveEdit} className="space-y-4 py-2 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Research Stage</Label>
                  <select
                    value={editStage}
                    onChange={(e) => setEditStage(e.target.value as ResearchStage)}
                    className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="DISCOVERED">DISCOVERED</option>
                    <option value="SCREENED">SCREENED</option>
                    <option value="RESEARCHING">RESEARCHING</option>
                    <option value="VALUED">VALUED</option>
                    <option value="READY">READY</option>
                    <option value="WAITING_FOR_PRICE">WAITING FOR PRICE</option>
                    <option value="OWNED">OWNED</option>
                    <option value="REJECTED">REJECTED</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Priority</Label>
                  <select
                    value={editPriority}
                    onChange={(e) => setEditPriority(e.target.value as WatchlistPriority)}
                    className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High (Immediate)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Target Entry Min ($)</Label>
                  <Input
                    type="number"
                    step="any"
                    value={editMin}
                    onChange={(e) => setEditMin(e.target.value)}
                    placeholder="Min entry"
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Target Entry Max ($)</Label>
                  <Input
                    type="number"
                    step="any"
                    value={editMax}
                    onChange={(e) => setEditMax(e.target.value)}
                    placeholder="Max entry"
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Why Interesting / Thesis Notes</Label>
                <Input
                  value={editWhy}
                  onChange={(e) => setEditWhy(e.target.value)}
                  placeholder="Thesis hook or catalyst"
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Key Catalyst</Label>
                <Input
                  value={editCatalyst}
                  onChange={(e) => setEditCatalyst(e.target.value)}
                  placeholder="e.g. Next earnings, product launch"
                  className="h-8 text-xs"
                />
              </div>

              <DialogFooter className="pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditItem(null)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={submitting}
                  className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold"
                >
                  {submitting ? 'Saving...' : 'Save Changes'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
