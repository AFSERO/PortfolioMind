import { useState } from 'react'
import { ChevronDown, Sparkles } from 'lucide-react'
import type { Asset } from '@/types'

interface Props {
  asset: Asset
}

export default function ContextualAIActions({ asset }: Props) {
  const [activePrompt, setActivePrompt] = useState<string | null>(null)

  const state = asset.instrument?.intelligence_state
  const isReviewed = Boolean(state && (state.last_review_at || state.thesis_status || state.recommendation))
  const rec = isReviewed ? state?.recommendation : null

  const questions = [
    {
      title: 'What would invalidate this investment thesis?',
      answer:
        state?.human_brief
          ? `For ${asset.name}, thesis invalidation would occur if core operating fundamentals, unit economics, or regulatory standing deviate from the original thesis baseline. The current thesis status is ${state?.thesis_status ?? 'UNCHANGED'}.`
          : `No formal thesis baseline has been registered for ${asset.name} yet. Run a Deep Research protocol to establish invalidation thresholds.`,
    },
    {
      title: rec ? `Why is the current recommendation ${rec}?` : 'Why is this holding Not Reviewed?',
      answer:
        rec && state?.human_brief
          ? `Recommendation ${rec} reflects the combination of thesis status (${state.thesis_status ?? 'UNCHANGED'}), valuation status (${state.valuation_status ?? 'FAIR'}), and technical trend (${state.technical_status ?? 'ON_TRACK'}). Context: ${state.human_brief}`
          : `This holding has not undergone a formal protocol review yet. Run Deep Research to generate a structured recommendation.`,
    },
    {
      title: 'How does this position fit into my portfolio risk?',
      answer: `This holding represents ${asset.total_quantity.toLocaleString()} units of ${asset.name}. Keep concentration aligned with your risk budget for ${asset.asset_type.toLowerCase()} assets.`,
    },
  ]

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-teal-400" />
        <h4 className="text-xs font-semibold uppercase tracking-wider text-foreground">
          Contextual Decision Support
        </h4>
      </div>

      <div className="space-y-2">
        {questions.map((q) => {
          const isOpen = activePrompt === q.title
          return (
            <div key={q.title} className="rounded-lg border border-border/40 bg-background/30 p-2.5 text-xs">
              <button
                type="button"
                onClick={() => setActivePrompt(isOpen ? null : q.title)}
                className="w-full text-left flex items-center justify-between gap-2 font-medium text-foreground hover:text-teal-300 transition-colors"
              >
                <span>{q.title}</span>
                <ChevronDown
                  className={`size-3.5 text-muted-foreground shrink-0 transition-transform ${
                    isOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>
              {isOpen && (
                <p className="mt-2 text-muted-foreground leading-relaxed pt-1 border-t border-border/30">
                  {q.answer}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
