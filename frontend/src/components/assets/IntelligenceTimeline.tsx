import { useState } from 'react'
import { ChevronDown, ChevronRight, History } from 'lucide-react'
import type { IntelligenceReview } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

interface Props {
  reviews: IntelligenceReview[]
  isLoading: boolean
}

export default function IntelligenceTimeline({ reviews, isLoading }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/60 bg-card/40 p-5 space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border/40 pb-3">
        <div className="flex items-center gap-2">
          <History className="size-4 text-teal-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">
            Intelligence Review History
          </h3>
        </div>
        <span className="text-[11px] text-muted-foreground font-mono">
          {reviews.length} {reviews.length === 1 ? 'audit record' : 'audit records'}
        </span>
      </div>

      {reviews.length === 0 ? (
        <p className="text-xs text-muted-foreground py-3">
          No historical protocol reviews have been recorded for this instrument yet.
        </p>
      ) : (
        <div className="space-y-3">
          {reviews.map((review) => {
            const isExpanded = expandedId === review.id
            const dateStr = new Date(review.created_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })

            return (
              <div
                key={review.id}
                className="rounded-lg border border-border/40 bg-background/40 p-3 text-xs space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground font-mono">
                      {review.protocol}
                    </span>
                    <Badge variant="outline" className="text-[10px] border-teal-500/30 bg-teal-500/10 text-teal-300">
                      {review.status}
                    </Badge>
                    {review.confidence && (
                      <span className="text-[10px] text-muted-foreground">
                        Confidence: <strong className="text-foreground">{review.confidence}</strong>
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground font-mono">{dateStr}</span>
                </div>

                {review.human_brief && (
                  <p className="text-muted-foreground leading-relaxed">
                    {review.human_brief}
                  </p>
                )}

                {/* Machine Record Toggle */}
                {review.machine_record && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : review.id)}
                      className="inline-flex items-center gap-1 text-[11px] text-teal-400 hover:text-teal-300 transition-colors pt-1"
                    >
                      {isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                      <span>{isExpanded ? 'Hide Raw Audit Record' : 'View Protocol Machine Record'}</span>
                    </button>

                    {isExpanded && (
                      <pre className="mt-2 p-2.5 rounded bg-muted/30 border border-border/40 text-[10px] font-mono text-muted-foreground overflow-x-auto max-h-48">
                        {JSON.stringify(review.machine_record, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
