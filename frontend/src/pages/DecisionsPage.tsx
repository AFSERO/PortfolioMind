import { useMemo, useState } from 'react'
import { BookOpen, FileText, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import DecisionTimeline from '@/components/decisions/DecisionTimeline'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useAssets } from '@/hooks/useAssets'
import { useDecisions } from '@/hooks/useDecisions'
import { cn } from '@/utils/cn'

type FilterCategory = 'ALL' | 'TRADES' | 'INTELLIGENCE' | 'NOTES'

export default function DecisionsPage() {
  const { assets } = useAssets()
  const { decisions, total, isLoading, createDecision, updateRationale } = useDecisions()

  const [filterCategory, setFilterCategory] = useState<FilterCategory>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Dialog Form state
  const [selectedAssetId, setSelectedAssetId] = useState<string>('none')
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [rationale, setRationale] = useState('')
  const [confidence, setConfidence] = useState('MEDIUM')
  const [expectation, setExpectation] = useState('')

  const filteredDecisions = useMemo(() => {
    return decisions.filter((d) => {
      // Category filter
      if (filterCategory === 'TRADES') {
        if (!['POSITION_OPENED', 'POSITION_ADDED', 'POSITION_REDUCED', 'POSITION_CLOSED', 'BUY', 'SELL'].includes(d.event_type)) {
          return false
        }
      } else if (filterCategory === 'INTELLIGENCE') {
        if (!['THESIS_CHANGED', 'THESIS_REVIEWED', 'VALUATION_CHANGED', 'RECOMMENDATION_CHANGED', 'TECHNICAL_PLAN_CHANGED', 'INTELLIGENCE_REVIEW_COMPLETED'].includes(d.event_type)) {
          return false
        }
      } else if (filterCategory === 'NOTES') {
        if (d.event_type !== 'MANUAL_DECISION_NOTE') {
          return false
        }
      }

      // Search query filter
      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase()
      return (
        d.title.toLowerCase().includes(q) ||
        d.summary.toLowerCase().includes(q) ||
        (d.user_rationale && d.user_rationale.toLowerCase().includes(q)) ||
        (d.instrument_symbol && d.instrument_symbol.toLowerCase().includes(q)) ||
        (d.asset_name && d.asset_name.toLowerCase().includes(q))
      )
    })
  }, [decisions, filterCategory, searchQuery])

  const tradeCount = useMemo(
    () => decisions.filter((d) => ['POSITION_OPENED', 'POSITION_ADDED', 'POSITION_REDUCED', 'POSITION_CLOSED', 'BUY', 'SELL'].includes(d.event_type)).length,
    [decisions]
  )
  const intelCount = useMemo(
    () => decisions.filter((d) => ['THESIS_CHANGED', 'VALUATION_CHANGED', 'RECOMMENDATION_CHANGED', 'TECHNICAL_PLAN_CHANGED'].includes(d.event_type)).length,
    [decisions]
  )
  const notesCount = useMemo(
    () => decisions.filter((d) => d.event_type === 'MANUAL_DECISION_NOTE').length,
    [decisions]
  )

  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !summary.trim()) {
      toast.error('Title and summary are required')
      return
    }

    setSubmitting(true)
    try {
      const chosenAsset = selectedAssetId !== 'none' ? assets.find((a) => a.id === selectedAssetId) : undefined
      await createDecision({
        asset_id: chosenAsset?.id,
        instrument_id: chosenAsset?.instrument_id ?? undefined,
        event_type: 'MANUAL_DECISION_NOTE',
        title: title.trim(),
        summary: summary.trim(),
        user_rationale: rationale.trim() || undefined,
        confidence: confidence || undefined,
        expectation: expectation.trim() || undefined,
      })

      toast.success('Decision note recorded')
      setTitle('')
      setSummary('')
      setRationale('')
      setExpectation('')
      setSelectedAssetId('none')
      setIsDialogOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to record decision')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Decision Log"
          description="Persistent audit trail of portfolio transactions, thesis shifts, and investment rationale."
          actions={
            <Button
              onClick={() => setIsDialogOpen(true)}
              className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5 h-8 text-xs font-semibold"
            >
              <Plus className="size-3.5" />
              <span>Record Decision Note</span>
            </Button>
          }
        />

        {/* Filters & Search Toolbar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-border/40 pb-3">
          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <button
              type="button"
              onClick={() => setFilterCategory('ALL')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                filterCategory === 'ALL'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              All ({total})
            </button>
            <button
              type="button"
              onClick={() => setFilterCategory('TRADES')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                filterCategory === 'TRADES'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Trades ({tradeCount})
            </button>
            <button
              type="button"
              onClick={() => setFilterCategory('INTELLIGENCE')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                filterCategory === 'INTELLIGENCE'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Intelligence Shifts ({intelCount})
            </button>
            <button
              type="button"
              onClick={() => setFilterCategory('NOTES')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap',
                filterCategory === 'NOTES'
                  ? 'bg-teal-500/15 text-teal-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              )}
            >
              Manual Notes ({notesCount})
            </button>
          </div>

          {/* Search & Counter */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
            <div className="relative w-full sm:w-64 sm:shrink-0">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search decisions, symbols, rationale..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-full rounded-lg border border-border/60 bg-background/50 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
            <span className="text-xs text-muted-foreground font-mono whitespace-nowrap">
              {total} Logged Decisions
            </span>
          </div>
        </div>

        {/* Main Content Timeline or Empty State */}
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ) : filteredDecisions.length > 0 ? (
          <DecisionTimeline
            items={filteredDecisions}
            onUpdateRationale={(id, rationale, confidence, expectation) =>
              updateRationale(id, { user_rationale: rationale, confidence, expectation })
            }
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border/80 p-12 text-center bg-card/20 space-y-4">
            <div className="mx-auto size-12 rounded-full bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400">
              <BookOpen className="size-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-foreground">
                {searchQuery || filterCategory !== 'ALL'
                  ? 'No matching decisions found'
                  : 'No decisions recorded yet'}
              </h3>
              <p className="text-xs text-muted-foreground max-w-md mx-auto">
                {searchQuery || filterCategory !== 'ALL'
                  ? 'Try adjusting your search query or filter tab to view other events.'
                  : 'Portfolio actions (buys, sells, thesis changes) are automatically logged here to preserve your decision trail.'}
              </p>
            </div>
            {!searchQuery && filterCategory === 'ALL' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDialogOpen(true)}
                className="h-8 text-xs border-teal-500/30 text-teal-300 hover:bg-teal-500/10"
              >
                <Plus className="size-3.5 mr-1" />
                Record First Decision Note
              </Button>
            )}
          </div>
        )}

        {/* Record Decision Note Modal */}
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileText className="size-5 text-teal-400" />
                <span>Record Investment Decision Note</span>
              </DialogTitle>
              <DialogDescription>
                Document your reasoning, confidence, and expectations to review later.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleCreateNote} className="space-y-3.5 py-2">
              {/* Optional Asset selection */}
              <div className="space-y-1.5">
                <Label htmlFor="asset-select" className="text-xs font-medium">Related Holding (Optional)</Label>
                <Select value={selectedAssetId} onValueChange={setSelectedAssetId}>
                  <SelectTrigger id="asset-select" className="h-8 text-xs">
                    <SelectValue placeholder="General / Portfolio-wide" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">General / Portfolio-wide</SelectItem>
                    {assets.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.symbol ? `${a.symbol} — ${a.name}` : a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Title */}
              <div className="space-y-1.5">
                <Label htmlFor="title" className="text-xs font-medium">Decision Title *</Label>
                <Input
                  id="title"
                  placeholder="e.g. Initiating watchlist position, Trimming risk"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="h-8 text-xs"
                  required
                />
              </div>

              {/* Summary */}
              <div className="space-y-1.5">
                <Label htmlFor="summary" className="text-xs font-medium">Summary of Action / Observation *</Label>
                <Textarea
                  id="summary"
                  placeholder="What specifically did you decide or observe?"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  className="text-xs min-h-[60px]"
                  required
                />
              </div>

              {/* User Rationale */}
              <div className="space-y-1.5">
                <Label htmlFor="rationale" className="text-xs font-medium">Your Rationale &amp; Thesis Intent</Label>
                <Textarea
                  id="rationale"
                  placeholder="Why did you make this decision? What gave you conviction?"
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  className="text-xs min-h-[60px]"
                />
              </div>

              {/* Confidence & Expectation */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="confidence" className="text-xs font-medium">Confidence</Label>
                  <Select value={confidence} onValueChange={setConfidence}>
                    <SelectTrigger id="confidence" className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="HIGH">High Conviction</SelectItem>
                      <SelectItem value="MEDIUM">Medium / Moderate</SelectItem>
                      <SelectItem value="LOW">Speculative / Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="expectation" className="text-xs font-medium">Expectation / Target Outcome</Label>
                  <Input
                    id="expectation"
                    placeholder="e.g. 15% ROIC within 12M"
                    value={expectation}
                    onChange={(e) => setExpectation(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>

              <DialogFooter className="pt-3 gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setIsDialogOpen(false)}
                  disabled={submitting}
                  className="h-8 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submitting}
                  className="h-8 text-xs bg-teal-600 hover:bg-teal-700 text-white font-semibold"
                >
                  {submitting ? 'Recording...' : 'Record Decision'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
