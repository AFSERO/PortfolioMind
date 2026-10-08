import { Link } from 'react-router-dom'
import { ArrowUpRight, BrainCircuit, FileText, Calendar } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export interface JournalItem {
  id: string
  date: string
  type: 'THESIS_REVIEW' | 'POSITION_NOTE'
  assetId?: string
  symbol?: string | null
  name: string
  title: string
  content: string
  recommendation?: string | null
  thesisStatus?: string | null
  valuationStatus?: string | null
  technicalStatus?: string | null
}

interface Props {
  items: JournalItem[]
}

export default function JournalTimeline({ items }: Props) {
  if (items.length === 0) {
    return null
  }

  return (
    <div className="relative pl-6 space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-border/60">
      {items.map((item) => {
        const isReview = item.type === 'THESIS_REVIEW'
        const dateStr = new Date(item.date).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })

        return (
          <div key={item.id} className="relative group">
            {/* Timeline node icon */}
            <div
              className={`absolute -left-6 top-1.5 size-6 rounded-full border flex items-center justify-center transition-colors ${
                isReview
                  ? 'border-teal-500/40 bg-teal-500/10 text-teal-400 group-hover:border-teal-400'
                  : 'border-blue-500/40 bg-blue-500/10 text-blue-400 group-hover:border-blue-400'
              }`}
            >
              {isReview ? <BrainCircuit className="size-3" /> : <FileText className="size-3" />}
            </div>

            {/* Content card */}
            <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3 hover:border-teal-500/30 transition-all">
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/30 pb-2.5">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`text-[10px] uppercase font-semibold tracking-wider ${
                      isReview
                        ? 'border-teal-500/30 text-teal-300 bg-teal-500/5'
                        : 'border-blue-500/30 text-blue-300 bg-blue-500/5'
                    }`}
                  >
                    {isReview ? 'Thesis Review' : 'Position Note'}
                  </Badge>
                  <span className="text-xs font-bold text-foreground">
                    {item.symbol ?? item.name}
                  </span>
                  {item.symbol && item.name !== item.symbol && (
                    <span className="text-xs text-muted-foreground hidden sm:inline truncate max-w-[200px]">
                      {item.name}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1 text-[11px] font-mono">
                    <Calendar className="size-3 text-muted-foreground" />
                    <span>{dateStr}</span>
                  </div>
                  {item.assetId && (
                    <Link
                      to={`/assets/${item.assetId}`}
                      className="text-[11px] text-teal-400 hover:text-teal-300 inline-flex items-center gap-0.5"
                    >
                      <span>View Asset</span>
                      <ArrowUpRight className="size-3" />
                    </Link>
                  )}
                </div>
              </div>

              {/* Status badges row if available */}
              {(item.recommendation || item.thesisStatus || item.valuationStatus) && (
                <div className="flex flex-wrap items-center gap-2">
                  {item.recommendation && (
                    <span className="text-[11px] px-2 py-0.5 rounded font-mono font-semibold bg-teal-500/10 border border-teal-500/20 text-teal-300">
                      REC: {item.recommendation}
                    </span>
                  )}
                  {item.thesisStatus && (
                    <span className="text-[11px] px-2 py-0.5 rounded font-mono font-medium bg-muted/40 border border-border/40 text-muted-foreground">
                      Thesis: {item.thesisStatus}
                    </span>
                  )}
                  {item.valuationStatus && (
                    <span className="text-[11px] px-2 py-0.5 rounded font-mono font-medium bg-muted/40 border border-border/40 text-muted-foreground">
                      Valuation: {item.valuationStatus}
                    </span>
                  )}
                </div>
              )}

              {/* Main rationale / note */}
              <p className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed">
                {item.content}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
