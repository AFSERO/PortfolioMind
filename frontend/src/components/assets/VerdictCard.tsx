import { useState } from 'react'
import { AlertTriangle, BrainCircuit, Clock, RefreshCw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import type { InstrumentIntelligenceState } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { assetService } from '@/services/assetService'
import { extractErrorMessage } from '@/services/api'
import { cn } from '@/utils/cn'

interface Props {
  state?: InstrumentIntelligenceState | null
  assetId?: string
  assetType?: string
  assetName?: string
  onRefresh?: () => void
}

function getAssetClassResearchHint(assetType?: string): string {
  switch (assetType) {
    case 'STOCK':
      return 'İş modeli, rekabet avantajı (moat), nakit akış kalitesi, çarpan/DCF değerlemesi ve tezi geçersiz kılacak temel riskler incelenir.'
    case 'CRYPTO':
      return 'Tokenomics, kilit açılış/emisyon takvimi, zincir üstü aktivite, TVL/kullanım ve döngüsel değerleme parametreleri incelenir.'
    case 'FUND':
      return 'Fon yatırım stratejisi, tepe portföy pozisyonları, Sharpe/Sortino oranları, yönetim ücreti ve valör/likidite dinamikleri incelenir.'
    case 'PRECIOUS_METALS':
      return 'Reel faizler (ABD 10Y TIPS), DXY, merkez bankası alımları, USD/TRY kuru ve Kapalıçarşı fiziki makas aralığı incelenir.'
    case 'REAL_ESTATE':
    case 'CUSTOM':
    case 'FOREX':
      return 'Bu varlık sınıfı için Deep Research AI protokolü desteklenmemektedir (Desteklenenler: Hisse, Kripto, Fon, Altın).'
    default:
      return 'Varlık için yatırım tezi, değerleme bantları ve teknik trend stratejisi AI protokolü ile analiz edilir.'
  }
}

export default function VerdictCard({
  state,
  assetId,
  assetType,
  assetName,
  onRefresh,
}: Props) {
  const [isResearching, setIsResearching] = useState(false)

  const handleRunDeepResearch = async () => {
    if (!assetId || isResearching) return
    setIsResearching(true)
    toast.info(`Deep Research başlatılıyor: ${assetName || 'Varlık'}...`)
    try {
      const res = await assetService.runDeepResearch(assetId)
      const summary = res?.summary
      const newRec = summary?.recommendation || 'Tamamlandı'
      toast.success(`Deep Research tamamlandı (${assetName || 'Varlık'}): ${newRec}`)
      if (onRefresh) {
        onRefresh()
      }
    } catch (err: unknown) {
      toast.error(extractErrorMessage(err, 'Deep Research başarısız oldu'))
    } finally {
      setIsResearching(false)
    }
  }

  const isReviewed = Boolean(state && (state.last_review_at || state.thesis_status || state.recommendation))

  if (!isReviewed || !state) {
    return (
      <div className="rounded-xl border border-border/60 bg-card/40 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <BrainCircuit className="size-5" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-foreground">
                Investment Intelligence Verdict
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                No investment review has been completed for this instrument yet.
              </p>
            </div>
          </div>

          {assetId && (
            <Button
              onClick={handleRunDeepResearch}
              disabled={isResearching}
              className="bg-teal-600 hover:bg-teal-700 text-white gap-2 text-xs font-semibold shrink-0"
            >
              {isResearching ? (
                <>
                  <RefreshCw className="size-3.5 animate-spin" />
                  <span>Deep Research Çalışıyor...</span>
                </>
              ) : (
                <>
                  <Sparkles className="size-3.5" />
                  <span>Deep Research Başlat</span>
                </>
              )}
            </Button>
          )}
        </div>

        <div className="rounded-lg border border-border/30 bg-muted/10 p-3.5 text-xs text-muted-foreground flex items-start gap-2.5">
          <Sparkles className="size-4 text-teal-400 mt-0.5 shrink-0" />
          <p className="leading-relaxed">
            <strong className="text-foreground/90 font-medium">Analiz Kapsamı: </strong>
            {getAssetClassResearchHint(assetType)}
          </p>
        </div>
      </div>
    )
  }

  // Formatting dates
  const lastReviewed = state.last_review_at
    ? new Date(state.last_review_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Not recorded'

  const rec = state.recommendation
  const isAlertRec = rec === 'REVIEW_REQUIRED' || rec === 'SELL'
  const isRestrictedOrBlocked =
    state.execution_status === 'RESTRICTED' || state.execution_status === 'BLOCKED'

  return (
    <div className="rounded-xl border border-border/60 bg-card/50 p-5 space-y-4">
      {/* Header with Verdict Badge and Freshness */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-3">
        <div className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <BrainCircuit className="size-4.5" />
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Investment Verdict
            </p>
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              {rec ? (
                <Badge
                  className={cn(
                    'text-xs font-bold px-2.5 py-0.5 uppercase tracking-wider',
                    rec === 'ADD' && 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
                    rec === 'HOLD' && 'bg-teal-500/15 text-teal-300 border-teal-500/30',
                    rec === 'REDUCE' && 'bg-amber-500/15 text-amber-400 border-amber-500/30',
                    isAlertRec && 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  )}
                  variant="outline"
                >
                  {rec.replace('_', ' ')}
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="text-xs font-semibold uppercase bg-muted/20 text-muted-foreground/70 border-border/40"
                >
                  NOT REVIEWED
                </Badge>
              )}

              {/* Execution Status Badge */}
              {state.execution_status && (
                <Badge
                  variant="outline"
                  className={cn(
                    'text-xs font-semibold px-2 py-0.5 uppercase tracking-wider',
                    state.execution_status === 'AVAILABLE' &&
                      'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
                    state.execution_status === 'RESTRICTED' &&
                      'bg-amber-500/15 text-amber-400 border-amber-500/30',
                    state.execution_status === 'BLOCKED' &&
                      'bg-rose-500/15 text-rose-400 border-rose-500/30',
                    state.execution_status === 'UNKNOWN' &&
                      'bg-muted/30 text-muted-foreground border-border/60'
                  )}
                >
                  {state.execution_status === 'RESTRICTED'
                    ? 'UYGULANABİLİRLİK: KISITLI'
                    : state.execution_status === 'BLOCKED'
                    ? 'UYGULANABİLİRLİK: ENGELLİ'
                    : state.execution_status === 'AVAILABLE'
                    ? 'UYGULANABİLİRLİK: AÇIK'
                    : `İŞLEM: ${state.execution_status}`}
                </Badge>
              )}

              {(state.confidence_score != null || state.confidence) && (
                <Badge
                  variant="outline"
                  className="text-xs font-mono border-border/60 bg-muted/30 text-muted-foreground"
                >
                  GÜVEN: %{state.confidence_score != null ? state.confidence_score : state.confidence?.replace('%', '')}
                  {state.confidence_level ? ` (${state.confidence_level})` : ''}
                </Badge>
              )}

              {/* Secondary certainty badge if present */}
              {state.recovery_value_confidence && (
                <Badge
                  variant="outline"
                  className="text-[11px] font-mono border-amber-500/30 bg-amber-500/10 text-amber-300"
                  title="Tahsilat / Kurtarma Değeri Güveni"
                >
                  Kurtarma Güveni: {state.recovery_value_confidence}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
            <Clock className="size-3.5" />
            <span>Reviewed {lastReviewed}</span>
          </div>

          {assetId && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRunDeepResearch}
              disabled={isResearching}
              className="h-7 text-xs font-medium gap-1.5 border-border/60 hover:border-teal-500/40 text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className={cn('size-3', isResearching && 'animate-spin text-teal-400')} />
              <span>{isResearching ? 'Yenileniyor...' : 'Araştırmayı Yenile'}</span>
            </Button>
          )}
        </div>
      </div>

      {/* Execution Alert Banner if restricted or blocked */}
      {isRestrictedOrBlocked && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs flex items-start gap-2.5">
          <AlertTriangle className="size-4 text-amber-400 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold text-amber-300">
              Uygulanabilirlik Bildirimi ({state.execution_status === 'BLOCKED' ? 'İşlem Engelli' : 'İşlem Kısıtlı'}):
            </span>{' '}
            <span className="text-amber-200/90 leading-relaxed">
              Yatırım görüşü pozisyonu kapatmayı ({rec}) işaret etse de, itfa durdurma, tasfiye veya işlem yasağı nedeniyle işlem anında serbest piyasada uygulanamayabilir. Karar ve uygulanabilirlik iki ayrı boyuttur.
            </span>
          </div>
        </div>
      )}

      {/* 3 Status Dimensions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Thesis */}
        <div className="rounded-lg border border-border/40 bg-background/40 p-2.5">
          <p className="text-[10px] uppercase font-semibold text-muted-foreground">Thesis</p>
          <p
            className={cn(
              'text-xs font-semibold mt-0.5',
              state.thesis_status === 'STRONGER' && 'text-emerald-400',
              state.thesis_status === 'UNCHANGED' && 'text-foreground',
              state.thesis_status === 'WEAKER' && 'text-amber-400',
              state.thesis_status === 'INVALIDATED' && 'text-rose-400'
            )}
          >
            {state.thesis_status ?? 'NOT EVALUATED'}
          </p>
        </div>

        {/* Valuation / Assessment */}
        <div className="rounded-lg border border-border/40 bg-background/40 p-2.5">
          <p className="text-[10px] uppercase font-semibold text-muted-foreground">
            {assetType === 'FUND'
              ? 'Underlying & Quality'
              : assetType === 'CRYPTO'
              ? 'Market Attractiveness'
              : assetType === 'PRECIOUS_METALS'
              ? 'Macro Attractiveness'
              : 'Valuation'}
          </p>
          {assetType === 'FUND' ? (
            <div className="text-xs font-semibold mt-0.5 flex items-center gap-1.5 flex-wrap">
              <span className="text-muted-foreground font-normal">UND:</span>
              <span
                className={cn(
                  (state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'ATTRACTIVE' && 'text-emerald-400',
                  (state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'FAIR' && 'text-foreground',
                  (state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'EXPENSIVE' && 'text-amber-400',
                  ((state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'UNKNOWN' ||
                    (state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'N_A') &&
                    'text-muted-foreground/80 italic'
                )}
              >
                {(state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'N_A'
                  ? 'N/A'
                  : (state.asset_class_assessment?.underlying_valuation || state.valuation_status) === 'UNKNOWN'
                  ? 'UNKNOWN'
                  : state.asset_class_assessment?.underlying_valuation || state.valuation_status || '—'}
              </span>
              {state.asset_class_assessment?.fund_quality && (
                <>
                  <span className="text-border">|</span>
                  <span className="text-muted-foreground font-normal">QLT:</span>
                  <span
                    className={cn(
                      state.asset_class_assessment.fund_quality === 'STRONG' && 'text-emerald-400',
                      (state.asset_class_assessment.fund_quality === 'SOLID' || state.asset_class_assessment.fund_quality === 'ACCEPTABLE') && 'text-teal-300',
                      (state.asset_class_assessment.fund_quality === 'WEAK' || state.asset_class_assessment.fund_quality === 'WEAKENING') && 'text-amber-400',
                      state.asset_class_assessment.fund_quality === 'POOR' && 'text-rose-400',
                      state.asset_class_assessment.fund_quality === 'UNKNOWN' && 'text-muted-foreground'
                    )}
                  >
                    {state.asset_class_assessment.fund_quality}
                  </span>
                </>
              )}
            </div>
          ) : (
            <p
              className={cn(
                'text-xs font-semibold mt-0.5',
                (state.asset_class_assessment?.market_attractiveness === 'ATTRACTIVE' ||
                  state.asset_class_assessment?.macro_attractiveness === 'ATTRACTIVE' ||
                  state.valuation_status === 'ATTRACTIVE') &&
                  'text-emerald-400',
                (state.asset_class_assessment?.market_attractiveness === 'NEUTRAL' ||
                  state.asset_class_assessment?.macro_attractiveness === 'NEUTRAL' ||
                  state.valuation_status === 'FAIR') &&
                  'text-foreground',
                (state.asset_class_assessment?.market_attractiveness === 'UNATTRACTIVE' ||
                  state.asset_class_assessment?.macro_attractiveness === 'UNATTRACTIVE' ||
                  state.valuation_status === 'EXPENSIVE') &&
                  'text-amber-400',
                (state.valuation_status === 'UNKNOWN' || state.valuation_status === 'N_A') &&
                  'text-muted-foreground/80 italic'
              )}
            >
              {state.valuation_status === 'N_A'
                ? 'N/A'
                : state.valuation_status === 'UNKNOWN'
                ? 'UNKNOWN'
                : (state.asset_class_assessment?.market_attractiveness ||
                    state.asset_class_assessment?.macro_attractiveness ||
                    state.valuation_status) ??
                  'NOT EVALUATED'}
            </p>
          )}
        </div>

        {/* Technical */}
        <div className="rounded-lg border border-border/40 bg-background/40 p-2.5">
          <p className="text-[10px] uppercase font-semibold text-muted-foreground">Technical Strategy</p>
          <p
            className={cn(
              'text-xs font-semibold mt-0.5',
              state.technical_status === 'ON_TRACK' && 'text-emerald-400',
              state.technical_status === 'NEUTRAL' && 'text-foreground',
              (state.technical_status === 'DEVIATED' || state.technical_status === 'PULLBACK' || state.technical_status === 'EXTENDED') && 'text-amber-400',
              (state.technical_status === 'REVIEW_REQUIRED' || state.technical_status === 'BREAKDOWN') && 'text-rose-400',
              (state.technical_status === 'N_A' || state.technical_status === 'UNKNOWN') && 'text-muted-foreground/70 italic'
            )}
          >
            {state.technical_status === 'N_A'
              ? 'N/A'
              : state.technical_status
              ? state.technical_status.replace('_', ' ')
              : 'NOT EVALUATED'}
          </p>
        </div>
      </div>

      {/* Decision Reasoning */}
      {state.primary_reason && (
        <div className="rounded-lg border border-border/30 bg-muted/10 p-3 space-y-1">
          <p className="text-[10px] uppercase font-semibold text-muted-foreground">Karar Gerekçesi</p>
          <p className="text-xs text-foreground/90 leading-relaxed font-medium">{state.primary_reason}</p>
        </div>
      )}

      {/* Human Brief */}
      {state.human_brief && (
        <div className="rounded-lg border border-border/30 bg-muted/20 p-3">
          <p className="text-xs text-foreground/90 leading-relaxed whitespace-pre-line">
            {state.human_brief}
          </p>
        </div>
      )}
    </div>
  )
}
