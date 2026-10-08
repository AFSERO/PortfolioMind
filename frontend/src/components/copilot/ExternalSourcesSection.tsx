import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, Globe } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { CopilotExternalSource } from '@/types/copilot'
import { cn } from '@/utils/cn'

interface ExternalSourcesSectionProps {
  sources?: CopilotExternalSource[] | null
  className?: string
}

export function ExternalSourcesSection({ sources, className }: ExternalSourcesSectionProps) {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className={cn('mt-2.5 pt-2 border-t border-border/40 text-[11px]', className)}>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors group cursor-pointer"
        aria-expanded={expanded}
      >
        <Globe className="size-3 text-teal-400 group-hover:animate-pulse" />
        <span className="font-medium text-teal-400/90">Kaynaklar</span>
        <Badge
          variant="outline"
          className="text-[9px] py-0 px-1.5 border-teal-500/40 text-teal-400 bg-teal-500/10 font-mono"
        >
          {sources.length}
        </Badge>
        {expanded ? (
          <ChevronUp className="size-3 ml-auto text-muted-foreground" />
        ) : (
          <ChevronDown className="size-3 ml-auto text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 space-y-1.5 animate-in fade-in-50 duration-200">
          {sources.map((src, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-border/50 bg-background/90 p-2 text-[10px] space-y-1 shadow-xs"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 font-medium leading-tight">
                  {src.url ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-400 hover:text-teal-300 hover:underline inline-flex items-center gap-1"
                    >
                      <span>{src.title || 'Harici Kaynak'}</span>
                      <ExternalLink className="size-2.5 shrink-0 opacity-70" />
                    </a>
                  ) : (
                    <span className="text-foreground/90">{src.title || 'Harici Kaynak'}</span>
                  )}
                </div>
                {src.source && (
                  <Badge
                    variant="outline"
                    className="text-[9px] py-0 px-1 shrink-0 text-muted-foreground border-border/60 bg-muted/30"
                  >
                    {src.source}
                  </Badge>
                )}
              </div>

              {src.snippet && (
                <p className="text-muted-foreground/80 line-clamp-2 leading-relaxed">
                  {src.snippet}
                </p>
              )}

              {src.published_at && (
                <div className="text-[9px] text-muted-foreground/60 font-mono">
                  {src.published_at}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
