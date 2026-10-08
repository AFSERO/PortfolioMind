import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  BrainCircuit,
  Calendar,
  Check,
  Edit2,
  FileText,
  MinusCircle,
  PlusCircle,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { DecisionEventType, DecisionLogEntry } from '@/types'
import { cn } from '@/utils/cn'

interface Props {
  items: DecisionLogEntry[]
  onUpdateRationale?: (id: string, rationale: string, confidence?: string, expectation?: string) => Promise<any>
}

function getEventBadge(type: DecisionEventType) {
  switch (type) {
    case 'POSITION_OPENED':
    case 'BUY':
      return {
        label: 'Position Opened',
        icon: PlusCircle,
        className: 'border-teal-500/30 text-teal-300 bg-teal-500/10',
      }
    case 'POSITION_ADDED':
      return {
        label: 'Position Added',
        icon: TrendingUp,
        className: 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10',
      }
    case 'POSITION_REDUCED':
      return {
        label: 'Position Reduced',
        icon: TrendingDown,
        className: 'border-amber-500/30 text-amber-300 bg-amber-500/10',
      }
    case 'POSITION_CLOSED':
    case 'SELL':
      return {
        label: 'Position Closed',
        icon: MinusCircle,
        className: 'border-rose-500/30 text-rose-300 bg-rose-500/10',
      }
    case 'THESIS_CHANGED':
    case 'THESIS_REVIEWED':
      return {
        label: 'Thesis Shift',
        icon: BrainCircuit,
        className: 'border-indigo-500/30 text-indigo-300 bg-indigo-500/10',
      }
    case 'VALUATION_CHANGED':
      return {
        label: 'Valuation Update',
        icon: BrainCircuit,
        className: 'border-cyan-500/30 text-cyan-300 bg-cyan-500/10',
      }
    case 'RECOMMENDATION_CHANGED':
      return {
        label: 'Recommendation Change',
        icon: BrainCircuit,
        className: 'border-purple-500/30 text-purple-300 bg-purple-500/10',
      }
    case 'TECHNICAL_PLAN_CHANGED':
      return {
        label: 'Technical Plan',
        icon: TrendingUp,
        className: 'border-blue-500/30 text-blue-300 bg-blue-500/10',
      }
    case 'MANUAL_DECISION_NOTE':
    default:
      return {
        label: 'Decision Note',
        icon: FileText,
        className: 'border-slate-500/30 text-slate-300 bg-slate-500/10',
      }
  }
}

export default function DecisionTimeline({ items, onUpdateRationale }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editRationale, setEditRationale] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const handleStartEdit = (entry: DecisionLogEntry) => {
    setEditingId(entry.id)
    setEditRationale(entry.user_rationale || '')
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditRationale('')
  }

  const handleSaveEdit = async (id: string) => {
    if (!onUpdateRationale) return
    setIsSaving(true)
    try {
      await onUpdateRationale(id, editRationale.trim())
      toast.success('Rationale updated')
      setEditingId(null)
    } catch {
      toast.error('Failed to update rationale')
    } finally {
      setIsSaving(false)
    }
  }

  if (items.length === 0) {
    return null
  }

  return (
    <div className="relative pl-8 space-y-6 before:absolute before:left-[15px] before:top-3 before:bottom-3 before:w-0.5 before:bg-border/60">
      {items.map((item) => {
        const badge = getEventBadge(item.event_type)
        const Icon = badge.icon
        const dateStr = new Date(item.occurred_at || item.created_at).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
        const timeStr = new Date(item.occurred_at || item.created_at).toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
        })

        const isEditing = editingId === item.id
        const symbolOrName = item.instrument_symbol || item.asset_name || item.instrument_name

        return (
          <div key={item.id} className="relative group">
            {/* Timeline node icon */}
            <div
              className={cn(
                'absolute -left-8 top-3.5 size-8 rounded-full border flex items-center justify-center transition-colors bg-card shadow-sm',
                badge.className
              )}
            >
              <Icon className="size-3.5" />
            </div>

            {/* Main Decision Card */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 sm:p-5 space-y-3.5 hover:border-border/80 transition-all">
              {/* Top metadata bar */}
              <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-border/30 pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className={cn('text-[10px] uppercase font-semibold tracking-wider', badge.className)}>
                    {badge.label}
                  </Badge>
                  {symbolOrName && (
                    <span className="text-xs font-bold text-foreground font-mono">
                      {symbolOrName}
                    </span>
                  )}
                  {item.confidence && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground uppercase font-medium">
                      {item.confidence} confidence
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground ml-auto">
                  <Calendar className="size-3 text-muted-foreground/70" />
                  <span>{dateStr}</span>
                  <span className="text-muted-foreground/50">({timeStr})</span>
                </div>
              </div>

              {/* Title & Automated Summary */}
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-foreground leading-snug">{item.title}</h4>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.summary}</p>
              </div>

              {/* Execution details or metadata if available */}
              {item.metadata && Object.keys(item.metadata).length > 0 && (
                <div className="flex flex-wrap items-center gap-2 rounded-lg bg-background/50 border border-border/40 p-2.5 text-xs font-mono text-muted-foreground">
                  {item.metadata.price_per_unit && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Price: {item.metadata.price_per_unit} {item.metadata.currency}
                    </span>
                  )}
                  {item.metadata.quantity && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Qty: {item.metadata.quantity}
                    </span>
                  )}
                  {item.metadata.previous_quantity && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Prev Qty: {item.metadata.previous_quantity} &rarr; New: {item.metadata.new_quantity}
                    </span>
                  )}
                  {item.metadata.old_recommendation && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Rec: {item.metadata.old_recommendation} &rarr; {item.metadata.new_recommendation}
                    </span>
                  )}
                  {item.metadata.old_thesis && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Thesis: {item.metadata.old_thesis} &rarr; {item.metadata.new_thesis}
                    </span>
                  )}
                  {item.metadata.protocol && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted/40 text-foreground/80">
                      Protocol: {item.metadata.protocol}
                    </span>
                  )}
                </div>
              )}

              {/* User Rationale & Reasoning Box */}
              <div className="rounded-lg bg-teal-950/15 border border-teal-500/20 p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400">
                    User Rationale &amp; Thesis Intent
                  </span>
                  {!isEditing && onUpdateRationale && (
                    <button
                      type="button"
                      onClick={() => handleStartEdit(item)}
                      className="text-xs text-teal-400 hover:text-teal-300 inline-flex items-center gap-1 font-medium transition-colors"
                    >
                      <Edit2 className="size-3" />
                      <span>{item.user_rationale ? 'Edit Rationale' : 'Add Rationale'}</span>
                    </button>
                  )}
                </div>

                {isEditing ? (
                  <div className="space-y-2 pt-1">
                    <Textarea
                      value={editRationale}
                      onChange={(e) => setEditRationale(e.target.value)}
                      placeholder="Why did you take this decision? What were you seeing or expecting?"
                      className="text-xs bg-background/80 min-h-[70px]"
                    />
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={handleCancelEdit}
                        disabled={isSaving}
                      >
                        <X className="size-3 mr-1" />
                        Cancel
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        className="h-7 text-xs bg-teal-600 hover:bg-teal-700 text-white font-medium"
                        onClick={() => handleSaveEdit(item.id)}
                        disabled={isSaving || !editRationale.trim()}
                      >
                        <Check className="size-3 mr-1" />
                        Save Rationale
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-300 leading-relaxed italic">
                    {item.user_rationale ? (
                      `"${item.user_rationale}"`
                    ) : (
                      <span className="text-muted-foreground not-italic">
                        No user rationale recorded yet. Click above to capture your intent.
                      </span>
                    )}
                  </p>
                )}

                {item.expectation && !isEditing && (
                  <div className="text-[11px] text-teal-400/90 pt-1 flex items-center gap-1">
                    <span className="font-semibold">Expectation:</span>
                    <span>{item.expectation}</span>
                  </div>
                )}
              </div>

              {/* Footer: Related review or workstation link */}
              {item.asset_id && (
                <div className="flex items-center justify-end pt-1">
                  <Link
                    to={`/assets/${item.asset_id}`}
                    className="text-xs text-teal-400 hover:text-teal-300 inline-flex items-center gap-1 font-medium transition-colors"
                  >
                    <span>Open Asset Workstation</span>
                    <ArrowUpRight className="size-3.5" />
                  </Link>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
