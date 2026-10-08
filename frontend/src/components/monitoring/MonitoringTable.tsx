import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, CheckCircle2, RefreshCw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import type { Asset } from '@/types'
import AssetTypeBadge from '@/components/assets/AssetTypeBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { assetService } from '@/services/assetService'
import { extractErrorMessage } from '@/services/api'
import { cn } from '@/utils/cn'

interface Props {
  assets: Asset[]
  isLoading: boolean
  onRefresh?: () => void
}

type FilterTab = 'all' | 'attention' | 'on_track' | 'unreviewed'

export default function MonitoringTable({ assets, isLoading, onRefresh }: Props) {
  const [filter, setFilter] = useState<FilterTab>('all')
  const [researchingId, setResearchingId] = useState<string | null>(null)

  const handleRunDeepResearch = async (asset: Asset) => {
    if (researchingId !== null) return
    setResearchingId(asset.id)
    toast.info(`Deep Research başlatılıyor: ${asset.symbol || asset.name}...`)
    try {
      const res = await assetService.runDeepResearch(asset.id)
      const summary = res?.summary
      const newRec = summary?.recommendation || 'Tamamlandı'
      toast.success(`Deep Research tamamlandı (${asset.symbol || asset.name}): ${newRec}`)
      if (onRefresh) {
        onRefresh()
      }
    } catch (err: unknown) {
      toast.error(extractErrorMessage(err, 'Deep Research başarısız oldu'))
    } finally {
      setResearchingId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    )
  }

  // Segment assets
  const attentionAssets = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    if (!s || (!s.last_review_at && !s.thesis_status)) return false
    return (
      s.thesis_status === 'WEAKER' ||
      s.thesis_status === 'INVALIDATED' ||
      s.recommendation === 'REVIEW_REQUIRED' ||
      s.recommendation === 'SELL' ||
      s.technical_status === 'REVIEW_REQUIRED' ||
      s.technical_status === 'DEVIATED' ||
      s.technical_status === 'BREAKDOWN' ||
      s.execution_status === 'RESTRICTED' ||
      s.execution_status === 'BLOCKED'
    )
  })

  const onTrackAssets = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    if (!s || (!s.last_review_at && !s.thesis_status)) return false
    return (
      (s.thesis_status === 'STRONGER' || s.thesis_status === 'UNCHANGED') &&
      s.recommendation !== 'REVIEW_REQUIRED' &&
      s.recommendation !== 'SELL' &&
      s.execution_status !== 'RESTRICTED' &&
      s.execution_status !== 'BLOCKED'
    )
  })

  const unreviewedAssets = assets.filter((a) => {
    const s = a.instrument?.intelligence_state
    return !s || (!s.last_review_at && !s.thesis_status && !s.recommendation)
  })

  const filteredAssets =
    filter === 'attention'
      ? attentionAssets
      : filter === 'on_track'
      ? onTrackAssets
      : filter === 'unreviewed'
      ? unreviewedAssets
      : assets

  return (
    <div className="space-y-4">
      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border/40 pb-3">
        <button
          type="button"
          onClick={() => setFilter('all')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            filter === 'all'
              ? 'bg-teal-500/15 text-teal-300 font-semibold'
              : 'text-muted-foreground hover:bg-accent hover:text-foreground'
          )}
        >
          All Monitored ({assets.length})
        </button>

        <button
          type="button"
          onClick={() => setFilter('attention')}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            filter === 'attention'
              ? 'bg-rose-500/15 text-rose-300 font-semibold'
              : 'text-muted-foreground hover:bg-accent hover:text-foreground'
          )}
        >
          {attentionAssets.length > 0 && (
            <span className="size-1.5 rounded-full bg-rose-400" />
          )}
          Attention Required ({attentionAssets.length})
        </button>

        <button
          type="button"
          onClick={() => setFilter('on_track')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            filter === 'on_track'
              ? 'bg-emerald-500/15 text-emerald-300 font-semibold'
              : 'text-muted-foreground hover:bg-accent hover:text-foreground'
          )}
        >
          On Track ({onTrackAssets.length})
        </button>

        <button
          type="button"
          onClick={() => setFilter('unreviewed')}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            filter === 'unreviewed'
              ? 'bg-muted text-foreground font-semibold'
              : 'text-muted-foreground hover:bg-accent hover:text-foreground'
          )}
        >
          Unreviewed ({unreviewedAssets.length})
        </button>
      </div>

      {/* Unreviewed helper banner */}
      {filter === 'unreviewed' && unreviewedAssets.length > 0 && (
        <div className="flex items-center gap-2.5 rounded-lg border border-teal-500/30 bg-teal-950/20 px-3.5 py-2.5 text-xs text-teal-200">
          <Sparkles className="size-4 text-teal-400 shrink-0" />
          <span>
            Bu varlıklar henüz bir AI analiz protokolü ile incelenmedi. İlgili satırdaki <strong>Deep Research</strong> butonuna basarak yatırım tezi, değerleme ve teknik analizi anında başlatabilirsiniz.
          </span>
        </div>
      )}

      {/* Table Container */}
      <div className="rounded-xl border border-border/60 bg-card/40 overflow-hidden">
        {filteredAssets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <CheckCircle2 className="size-6 text-teal-400 mb-2" />
            <p className="text-sm font-semibold text-foreground">
              {filter === 'attention'
                ? 'No holdings currently require attention.'
                : 'No holdings match the selected filter.'}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5 max-w-sm">
              {filter === 'attention'
                ? 'All positions are operating normally within designated thesis boundaries.'
                : 'Switch filters or view your full portfolio in Holdings.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border/40 bg-muted/20 text-[10px] uppercase font-semibold text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Asset</th>
                  <th className="px-3 py-3">Thesis</th>
                  <th className="px-3 py-3">Valuation / Assessment</th>
                  <th className="px-3 py-3">Technical</th>
                  <th className="px-3 py-3">Recommendation</th>
                  <th className="px-3 py-3">Last Reviewed</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {filteredAssets.map((asset) => {
                  const s = asset.instrument?.intelligence_state
                  const isReviewed = Boolean(s && (s.last_review_at || s.thesis_status || s.recommendation))
                  const lastReviewedStr = s?.last_review_at
                    ? new Date(s.last_review_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })
                    : '—'

                  const rec = isReviewed ? s?.recommendation : null
                  const isAlert =
                    isReviewed && (
                      s?.thesis_status === 'INVALIDATED' ||
                      s?.thesis_status === 'WEAKER' ||
                      rec === 'REVIEW_REQUIRED' ||
                      rec === 'SELL'
                    )

                  return (
                    <tr
                      key={asset.id}
                      className={cn(
                        'hover:bg-accent/30 transition-colors',
                        isAlert && 'bg-rose-500/[0.02]'
                      )}
                    >
                      {/* Asset */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div>
                            <span className="font-semibold text-foreground">
                              {asset.symbol ? `${asset.symbol}` : asset.name}
                            </span>
                            {asset.symbol && (
                              <span className="text-[11px] text-muted-foreground ml-1.5 hidden sm:inline">
                                {asset.name}
                              </span>
                            )}
                          </div>
                          <AssetTypeBadge type={asset.asset_type} size="sm" />
                        </div>
                      </td>

                      {/* Thesis */}
                      <td className="px-3 py-3">
                        <span
                          className={cn(
                            'font-semibold text-[11px]',
                            s?.thesis_status === 'STRONGER' && 'text-emerald-400',
                            s?.thesis_status === 'UNCHANGED' && 'text-foreground',
                            s?.thesis_status === 'WEAKER' && 'text-amber-400',
                            s?.thesis_status === 'INVALIDATED' && 'text-rose-400',
                            !s?.thesis_status && 'text-muted-foreground/60'
                          )}
                        >
                          {s?.thesis_status ?? 'NOT REVIEWED'}
                        </span>
                      </td>

                      {/* Valuation / Assessment */}
                      <td className="px-3 py-3">
                        {asset.asset_type === 'FUND' ? (
                          <div className="flex flex-col gap-0.5 text-[10px]" title="Fon Portföy Değerlemesi & Yönetici Kalitesi">
                            <div className="flex items-center gap-1">
                              <span className="text-muted-foreground/70 font-medium">UND:</span>
                              <span
                                className={cn(
                                  'font-semibold',
                                  (s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'ATTRACTIVE' && 'text-emerald-400',
                                  (s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'FAIR' && 'text-muted-foreground',
                                  (s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'EXPENSIVE' && 'text-amber-400',
                                  ((s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'UNKNOWN' ||
                                    (s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'N_A') &&
                                    'text-muted-foreground/80 italic font-normal'
                                )}
                              >
                                {(s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'N_A'
                                  ? 'N/A'
                                  : (s?.asset_class_assessment?.underlying_valuation || s?.valuation_status) === 'UNKNOWN'
                                  ? 'UNKNOWN'
                                  : s?.asset_class_assessment?.underlying_valuation || s?.valuation_status || '—'}
                              </span>
                            </div>
                            {s?.asset_class_assessment?.fund_quality && (
                              <div className="flex items-center gap-1">
                                <span className="text-muted-foreground/70 font-medium">QLT:</span>
                                <span
                                  className={cn(
                                    'font-semibold',
                                    s.asset_class_assessment.fund_quality === 'STRONG' && 'text-emerald-400',
                                    (s.asset_class_assessment.fund_quality === 'SOLID' || s.asset_class_assessment.fund_quality === 'ACCEPTABLE') && 'text-teal-300',
                                    (s.asset_class_assessment.fund_quality === 'WEAK' || s.asset_class_assessment.fund_quality === 'WEAKENING') && 'text-amber-400',
                                    s.asset_class_assessment.fund_quality === 'POOR' && 'text-rose-400',
                                    s.asset_class_assessment.fund_quality === 'UNKNOWN' && 'text-muted-foreground font-normal'
                                  )}
                                >
                                  {s.asset_class_assessment.fund_quality}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : asset.asset_type === 'CRYPTO' ? (
                          <div className="flex flex-col text-[10px]" title="Kripto Piyasa & Ağ Çekiciliği">
                            <span
                              className={cn(
                                'font-semibold text-[11px]',
                                (s?.asset_class_assessment?.market_attractiveness || s?.valuation_status) === 'ATTRACTIVE' && 'text-emerald-400',
                                (s?.asset_class_assessment?.market_attractiveness === 'NEUTRAL' || s?.valuation_status === 'FAIR') && 'text-muted-foreground',
                                (s?.asset_class_assessment?.market_attractiveness === 'UNATTRACTIVE' || s?.valuation_status === 'EXPENSIVE') && 'text-amber-400 font-semibold',
                                (s?.valuation_status === 'UNKNOWN' || s?.valuation_status === 'N_A') && 'text-muted-foreground/80 italic font-normal',
                                !s?.valuation_status && 'text-muted-foreground/60'
                              )}
                            >
                              {s?.valuation_status === 'N_A'
                                ? 'N/A'
                                : s?.valuation_status === 'UNKNOWN'
                                ? 'UNKNOWN'
                                : s?.asset_class_assessment?.market_attractiveness || s?.valuation_status || '—'}
                            </span>
                            <span className="text-[9px] text-muted-foreground/60 uppercase">Market</span>
                          </div>
                        ) : asset.asset_type === 'PRECIOUS_METALS' ? (
                          <div className="flex flex-col text-[10px]" title="Makro Çekicilik & Reel Faiz">
                            <span
                              className={cn(
                                'font-semibold text-[11px]',
                                (s?.asset_class_assessment?.macro_attractiveness || s?.valuation_status) === 'ATTRACTIVE' && 'text-emerald-400',
                                (s?.asset_class_assessment?.macro_attractiveness === 'NEUTRAL' || s?.valuation_status === 'FAIR') && 'text-muted-foreground',
                                (s?.asset_class_assessment?.macro_attractiveness === 'UNATTRACTIVE' || s?.valuation_status === 'EXPENSIVE') && 'text-amber-400 font-semibold',
                                (s?.valuation_status === 'UNKNOWN' || s?.valuation_status === 'N_A') && 'text-muted-foreground/80 italic font-normal',
                                !s?.valuation_status && 'text-muted-foreground/60'
                              )}
                            >
                              {s?.valuation_status === 'N_A'
                                ? 'N/A'
                                : s?.valuation_status === 'UNKNOWN'
                                ? 'UNKNOWN'
                                : s?.asset_class_assessment?.macro_attractiveness || s?.valuation_status || '—'}
                            </span>
                            <span className="text-[9px] text-muted-foreground/60 uppercase">Macro</span>
                          </div>
                        ) : (
                          <span
                            className={cn(
                              'text-[11px]',
                              s?.valuation_status === 'ATTRACTIVE' && 'text-emerald-400 font-semibold',
                              s?.valuation_status === 'FAIR' && 'text-muted-foreground',
                              s?.valuation_status === 'EXPENSIVE' && 'text-amber-400 font-semibold',
                              (s?.valuation_status === 'UNKNOWN' || s?.valuation_status === 'N_A') && 'text-muted-foreground/80 italic',
                              !s?.valuation_status && 'text-muted-foreground/60'
                            )}
                          >
                            {s?.valuation_status === 'N_A'
                              ? 'N/A'
                              : s?.valuation_status === 'UNKNOWN'
                              ? 'UNKNOWN'
                              : s?.valuation_status ?? '—'}
                          </span>
                        )}
                      </td>

                      {/* Technical */}
                      <td className="px-3 py-3">
                        <span
                          className={cn(
                            'text-[11px]',
                            s?.technical_status === 'ON_TRACK' && 'text-emerald-400',
                            s?.technical_status === 'NEUTRAL' && 'text-muted-foreground',
                            (s?.technical_status === 'DEVIATED' || s?.technical_status === 'PULLBACK' || s?.technical_status === 'EXTENDED') && 'text-amber-400 font-semibold',
                            (s?.technical_status === 'REVIEW_REQUIRED' || s?.technical_status === 'BREAKDOWN') && 'text-rose-400 font-semibold',
                            (s?.technical_status === 'N_A' || s?.technical_status === 'UNKNOWN') && 'text-muted-foreground/70 italic',
                            !s?.technical_status && 'text-muted-foreground/60'
                          )}
                        >
                          {s?.technical_status === 'N_A'
                            ? 'N/A'
                            : s?.technical_status
                            ? s.technical_status.replace('_', ' ')
                            : '—'}
                        </span>
                      </td>

                      {/* Recommendation */}
                      <td className="px-3 py-3">
                        {rec ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <Badge
                                variant="outline"
                                className={cn(
                                  'text-[10px] font-semibold uppercase',
                                  rec === 'ADD' && 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
                                  rec === 'HOLD' && 'bg-teal-500/10 text-teal-300 border-teal-500/20',
                                  rec === 'REDUCE' && 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                                  (rec === 'SELL' || rec === 'REVIEW_REQUIRED') &&
                                    'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                )}
                              >
                                {rec.replace('_', ' ')}
                              </Badge>

                              {/* Execution constraint badge */}
                              {s?.execution_status === 'RESTRICTED' && (
                                <Badge
                                  variant="outline"
                                  className="text-[9px] font-semibold uppercase bg-amber-500/10 text-amber-400 border-amber-500/30"
                                  title="İşlem Kısıtlı — pozisyon doğrudan serbest satılamayabilir / itfa kısıtlaması mevcut"
                                >
                                  KISITLI
                                </Badge>
                              )}
                              {s?.execution_status === 'BLOCKED' && (
                                <Badge
                                  variant="outline"
                                  className="text-[9px] font-semibold uppercase bg-rose-500/10 text-rose-400 border-rose-500/30"
                                  title="İşlem Engelli / Kapalı — tasfiye veya dondurulmuş durum"
                                >
                                  ENGELLİ
                                </Badge>
                              )}

                              {(s?.confidence_score != null || s?.confidence) && (
                                <span
                                  className="text-[10px] font-mono font-medium text-muted-foreground bg-muted/40 px-1 py-0.5 rounded border border-border/30"
                                  title="Model Confidence"
                                >
                                  {s?.confidence_score != null
                                    ? `${s.confidence_score}%`
                                    : s.confidence?.includes('%')
                                    ? s.confidence
                                    : `${s.confidence}%`}
                                </span>
                              )}
                            </div>

                            {s?.primary_reason && (
                              <p
                                className="text-[10px] text-muted-foreground line-clamp-1 max-w-[200px]"
                                title={s.primary_reason}
                              >
                                {s.primary_reason}
                              </p>
                            )}
                          </div>
                        ) : (
                          <Badge
                            variant="outline"
                            className="text-[10px] font-semibold uppercase bg-muted/20 text-muted-foreground/70 border-border/40"
                          >
                            NOT REVIEWED
                          </Badge>
                        )}
                      </td>

                      {/* Last Reviewed */}
                      <td className="px-3 py-3 font-mono text-[11px] text-muted-foreground">
                        {lastReviewedStr}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={researchingId !== null}
                            onClick={() => handleRunDeepResearch(asset)}
                            className={cn(
                              'h-7 px-2.5 text-[10px] font-semibold gap-1.5 transition-colors',
                              !isReviewed
                                ? 'border-teal-500/40 bg-teal-500/10 text-teal-300 hover:bg-teal-500/20'
                                : 'border-border/60 text-muted-foreground hover:text-foreground'
                            )}
                            title="Run AI Deep Research on this holding"
                          >
                            {researchingId === asset.id ? (
                              <>
                                <RefreshCw className="size-3 animate-spin text-teal-400" />
                                <span>Araştırılıyor...</span>
                              </>
                            ) : (
                              <>
                                <Sparkles className="size-3 text-teal-400" />
                                <span>Deep Research</span>
                              </>
                            )}
                          </Button>

                          <Link
                            to={`/assets/${asset.id}`}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-400 hover:text-teal-300 transition-colors px-1"
                          >
                            <span>Detay</span>
                            <ArrowUpRight className="size-3" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
