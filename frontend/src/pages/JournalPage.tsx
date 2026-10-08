import { useState, useMemo } from 'react'
import { BookOpen, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import JournalTimeline, { type JournalItem } from '@/components/journal/JournalTimeline'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { useAssets } from '@/hooks/useAssets'

type FilterType = 'ALL' | 'THESIS_REVIEW' | 'POSITION_NOTE'

export default function JournalPage() {
  const { assets, isLoading, updateAsset } = useAssets()
  const [filterType, setFilterType] = useState<FilterType>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Dialog state
  const [selectedAssetId, setSelectedAssetId] = useState('')
  const [noteContent, setNoteContent] = useState('')

  // Construct journal items
  const items = useMemo(() => {
    const list: JournalItem[] = []

    assets.forEach((asset) => {
      const intel = asset.instrument?.intelligence_state

      // 1. Intelligence review / brief
      if (intel?.human_brief) {
        list.push({
          id: `review-${asset.id}`,
          date: intel.updated_at || asset.updated_at || asset.created_at,
          type: 'THESIS_REVIEW',
          assetId: asset.id,
          symbol: asset.symbol,
          name: asset.name,
          title: `Thesis Review: ${asset.symbol ?? asset.name}`,
          content: intel.human_brief,
          recommendation: intel.recommendation,
          thesisStatus: intel.thesis_status,
          valuationStatus: intel.valuation_status,
          technicalStatus: intel.technical_status,
        })
      }

      // 2. Position / holding note
      if (asset.notes && asset.notes.trim()) {
        list.push({
          id: `note-${asset.id}`,
          date: asset.updated_at || asset.created_at,
          type: 'POSITION_NOTE',
          assetId: asset.id,
          symbol: asset.symbol,
          name: asset.name,
          title: `Position Note: ${asset.symbol ?? asset.name}`,
          content: asset.notes,
        })
      }
    })

    return list.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  }, [assets])

  // Filtered items
  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (filterType !== 'ALL' && item.type !== filterType) return false
      if (!searchQuery.trim()) return true
      const q = searchQuery.toLowerCase()
      return (
        item.name.toLowerCase().includes(q) ||
        (item.symbol && item.symbol.toLowerCase().includes(q)) ||
        item.content.toLowerCase().includes(q)
      )
    })
  }, [items, filterType, searchQuery])

  const reviewCount = items.filter((i) => i.type === 'THESIS_REVIEW').length
  const noteCount = items.filter((i) => i.type === 'POSITION_NOTE').length

  const handleSaveNote = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedAssetId) {
      toast.error('Please select an asset')
      return
    }
    if (!noteContent.trim()) {
      toast.error('Note content is required')
      return
    }

    setSubmitting(true)
    try {
      await updateAsset(selectedAssetId, { notes: noteContent.trim() })
      const asset = assets.find((a) => a.id === selectedAssetId)
      toast.success(`Decision note recorded for ${asset?.symbol ?? asset?.name ?? 'position'}`)
      setSelectedAssetId('')
      setNoteContent('')
      setAddOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save note')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Decision Journal"
          description="Audit trail of investment theses, review milestones, and rationale behind portfolio decisions."
          actions={
            <Button
              onClick={() => setAddOpen(true)}
              className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5 h-8 text-xs font-semibold"
            >
              <Plus className="size-3.5" />
              <span>Record Decision Note</span>
            </Button>
          }
        />

        {/* Stats & Filters Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                filterType === 'ALL'
                  ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
                  : 'bg-card/40 text-muted-foreground border border-border/40 hover:text-foreground'
              }`}
            >
              All ({items.length})
            </button>
            <button
              onClick={() => setFilterType('THESIS_REVIEW')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                filterType === 'THESIS_REVIEW'
                  ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
                  : 'bg-card/40 text-muted-foreground border border-border/40 hover:text-foreground'
              }`}
            >
              Thesis Reviews ({reviewCount})
            </button>
            <button
              onClick={() => setFilterType('POSITION_NOTE')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                filterType === 'POSITION_NOTE'
                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                  : 'bg-card/40 text-muted-foreground border border-border/40 hover:text-foreground'
              }`}
            >
              Position Notes ({noteCount})
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search journal entries..."
                className="h-8 w-full rounded-lg border border-border/60 bg-background/50 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="space-y-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32 rounded-xl bg-card/40 border border-border/60" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-border/60 bg-card/40 py-16 px-4 text-center">
            <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-teal-500/10 text-teal-400">
              <BookOpen className="size-5" />
            </div>
            <p className="text-sm font-semibold text-foreground">
              {items.length === 0 ? 'No decision entries recorded yet' : 'No entries matching filter'}
            </p>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground">
              {items.length === 0
                ? 'Record rationale when initiating positions, revising theses, or reviewing intelligence milestones to maintain an immutable decision log.'
                : 'Try adjusting your search query or switching filters.'}
            </p>
            {items.length === 0 && (
              <Button
                size="sm"
                onClick={() => setAddOpen(true)}
                className="mt-4 bg-teal-600 hover:bg-teal-700 text-white text-xs gap-1.5"
              >
                <Plus className="size-3.5" />
                Record First Note
              </Button>
            )}
          </div>
        ) : (
          <JournalTimeline items={filtered} />
        )}

        {/* Record Decision Dialog */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold">Record Decision Note</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                Document your thesis rationale, conviction, or rebalancing reasons for a portfolio holding.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSaveNote} className="space-y-4 py-2 text-xs">
              <div className="space-y-1.5">
                <Label htmlFor="journal-asset" className="text-xs">Select Holding *</Label>
                <select
                  id="journal-asset"
                  value={selectedAssetId}
                  onChange={(e) => setSelectedAssetId(e.target.value)}
                  className="h-8 w-full rounded-md border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  required
                >
                  <option value="">Choose an asset...</option>
                  {assets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.symbol ? `${asset.symbol} — ` : ''}{asset.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="journal-note" className="text-xs">Decision Rationale & Thesis Notes *</Label>
                <textarea
                  id="journal-note"
                  rows={4}
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="e.g. Initiated position following Q3 earnings beat. Thesis centers on recurring revenue expansion and moat widening..."
                  className="w-full rounded-md border border-input bg-background p-2.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none placeholder:text-muted-foreground"
                  required
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
                  {submitting ? 'Saving...' : 'Save to Journal'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
