import { useState } from 'react'
import { ChevronDown, ChevronUp, Cpu, Wrench } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { CopilotV2Trace } from '@/types/copilot'
import { cn } from '@/utils/cn'

interface V2DiagnosticsSectionProps {
  trace: CopilotV2Trace
  className?: string
}

export function V2DiagnosticsSection({ trace, className }: V2DiagnosticsSectionProps) {
  const [expanded, setExpanded] = useState(false)

  if (!trace) return null

  const profilePath = trace.profile_sequence?.length
    ? trace.profile_sequence.join(' → ')
    : trace.final_profile || 'FAST'

  return (
    <div className={cn('mt-2.5 pt-2 border-t border-border/40 text-[11px]', className)}>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors group"
      >
        <Cpu className="size-3 text-teal-400 group-hover:animate-pulse" />
        <span className="font-medium text-teal-400/90">V2 Telemetry</span>
        <span className="rounded bg-background/80 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border/40">
          {trace.final_profile} · {trace.reasoning_effort} · {Math.round(trace.total_latency_ms || 0)}ms
        </span>
        {trace.escalation_occurred && (
          <Badge variant="outline" className="text-[9px] py-0 px-1 border-teal-500/40 text-teal-400 bg-teal-500/10">
            Escalated
          </Badge>
        )}
        {trace.session_recovery_occurred && (
          <Badge variant="outline" className="text-[9px] py-0 px-1 border-amber-500/40 text-amber-400 bg-amber-500/10">
            Recovered
          </Badge>
        )}
        {expanded ? (
          <ChevronUp className="size-3 ml-auto text-muted-foreground" />
        ) : (
          <ChevronDown className="size-3 ml-auto text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 rounded-lg border border-border/50 bg-background/90 p-2.5 space-y-2 text-[10px] font-mono animate-in fade-in-50 duration-200">
          <div className="grid grid-cols-2 gap-2 text-muted-foreground">
            <div>
              <span className="text-foreground/70 font-semibold block">Model Flow:</span>
              <span className="text-teal-400">{profilePath}</span>
            </div>
            <div>
              <span className="text-foreground/70 font-semibold block">Session Mode:</span>
              <span
                className={cn(
                  trace.session_mode === 'RECOVERED' && 'text-amber-400',
                  trace.session_mode === 'RESUMED' && 'text-teal-400',
                  trace.session_mode === 'NEW' && 'text-sky-400',
                )}
              >
                {trace.session_mode || 'RESUMED'}
              </span>
            </div>
            <div>
              <span className="text-foreground/70 font-semibold block">Codex Invocations:</span>
              <span>{trace.codex_invocation_count || 1} call(s)</span>
            </div>
            <div>
              <span className="text-foreground/70 font-semibold block">Total Latency:</span>
              <span>{trace.total_latency_ms ? `${trace.total_latency_ms} ms` : 'N/A'}</span>
            </div>
            {trace.codex_session_id && (
              <div className="col-span-2">
                <span className="text-foreground/70 font-semibold block">Codex Session:</span>
                <span className="text-muted-foreground truncate block">{trace.codex_session_id}</span>
              </div>
            )}
          </div>

          {/* Tools Called & Latencies */}
          <div className="border-t border-border/30 pt-1.5">
            <span className="text-foreground/70 font-semibold block">Deterministic Tools:</span>
            {trace.tools_called?.length ? (
              <div className="flex flex-wrap gap-1 mt-1">
                {trace.tools_called.map((tool, idx) => {
                  const duration = trace.tool_durations?.[tool]
                  return (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 rounded bg-muted/60 px-1.5 py-0.5 border border-border/40 text-[9px]"
                    >
                      <Wrench className="size-2.5 text-teal-400" />
                      <span>{tool}</span>
                      {duration !== undefined && (
                        <span className="text-muted-foreground font-mono">({duration}ms)</span>
                      )}
                    </span>
                  )
                })}
              </div>
            ) : (
              <span className="text-muted-foreground/80 italic">No external tools required (Pure FAST response)</span>
            )}
            {Boolean(trace.tool_results_reused) && (
              <p className="text-teal-400/90 text-[9px] mt-1">
                ⚡ {trace.tool_results_reused} tool output(s) reused across handoff boundary without refetching
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
