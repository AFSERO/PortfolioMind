import React from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Calculator,
  DollarSign,
  Info,
  Layers,
  PieChart,
  ShieldCheck,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { SimulationResultData } from '@/types/copilot'
import { cn } from '@/utils/cn'


interface SimulationCardProps {
  simulation: SimulationResultData
}

export const SimulationCard: React.FC<SimulationCardProps> = ({ simulation }) => {
  if (!simulation) return null

  const isSell = simulation.simulation_type === 'SELL'
  const inst = simulation.instrument
  const validation = simulation.validation || { is_valid: true }
  const before = simulation.before
  const after = simulation.after
  const tx = simulation.transaction
  const assumptions = simulation.assumptions || {}
  const warnings = simulation.warnings || []

  const formatNumber = (num?: number, decimals = 2) => {
    if (num === undefined || num === null) return '0'
    return Number(num).toLocaleString('tr-TR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  const formatCurrency = (num?: number, currency = 'TRY') => {
    return `${formatNumber(num, 2)} ${currency}`
  }

  const formatPct = (pct?: number) => {
    if (pct === undefined || pct === null) return '%0.00'
    return `%${formatNumber(pct, 2)}`
  }

  const weightDelta = (after?.target_position?.weight_pct ?? 0) - (before?.target_position?.weight_pct ?? 0)
  const cashWeightDelta = (after?.cash?.cash_weight_pct ?? 0) - (before?.cash?.cash_weight_pct ?? 0)

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-sky-500/30 bg-slate-950/80 shadow-md">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sky-500/20 bg-sky-950/40 px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <Calculator className="size-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-sky-200">
                Portföy Senaryo Simülasyonu
              </span>
              <Badge
                variant="outline"
                className="border-sky-500/40 bg-sky-500/10 text-[10px] text-sky-300 font-mono"
              >
                HİPOTETİK
              </Badge>
            </div>
            <p className="text-[11px] text-sky-400/80">
              Salt matematiksel modelleme — portföy verileriniz değişmez
            </p>
          </div>
        </div>

        <Badge
          variant="outline"
          className="border-emerald-500/30 bg-emerald-500/10 text-[10px] text-emerald-400 flex items-center gap-1"
        >
          <ShieldCheck className="size-3" />
          Mutasyon Yok
        </Badge>
      </div>

      {/* Validation Alert (if invalid scenario) */}
      {!validation.is_valid && (
        <div className="border-b border-amber-500/20 bg-amber-500/10 px-3.5 py-2 text-xs text-amber-300 flex items-start gap-2">
          <AlertTriangle className="size-4 shrink-0 mt-0.5 text-amber-400" />
          <div>
            <span className="font-semibold">Senaryo Uyarısı: </span>
            <span>{validation.message || 'Belirtilen senaryo mevcut portföy durumuyla uygulanamaz.'}</span>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="border-b border-sky-500/20 bg-sky-950/20 px-3.5 py-1.5 text-[11px] text-sky-300 flex items-center gap-1.5">
          <Info className="size-3.5 text-sky-400 shrink-0" />
          <span>{warnings.join(' ')}</span>
        </div>
      )}


      {/* Target Asset Scenario Header */}
      <div className="p-3.5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn(
                'text-xs font-bold font-mono px-2 py-0.5',
                isSell
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                  : 'border-teal-500/40 bg-teal-500/10 text-teal-400'
              )}
            >
              {isSell ? 'SATIŞ SENARYOSU' : 'ALIŞ SENARYOSU'}
            </Badge>
            <span className="text-sm font-semibold text-foreground">
              {inst?.symbol}
            </span>
            <span className="text-xs text-muted-foreground truncate max-w-[200px]">
              {inst?.name}
            </span>
          </div>

          <div className="text-xs text-muted-foreground font-mono">
            {tx?.quantity !== undefined && tx?.quantity > 0 && (
              <span>
                {formatNumber(tx.quantity, 4)} adet @ {formatCurrency(assumptions?.price ?? 0, assumptions?.price_currency || inst?.currency)}
              </span>
            )}
          </div>
        </div>

        {/* 3-Column Before / Scenario / After Comparison Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
          {/* Column 1: Target Position Weight */}
          <div className="rounded-lg border border-border/40 bg-muted/20 p-2.5">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <PieChart className="size-3 text-sky-400" />
                Varlık Ağırlığı
              </span>
              <span
                className={cn(
                  'text-[10px] font-semibold font-mono flex items-center',
                  weightDelta < 0 ? 'text-rose-400' : weightDelta > 0 ? 'text-teal-400' : 'text-muted-foreground'
                )}
              >
                {weightDelta > 0 ? '+' : ''}
                {formatNumber(weightDelta, 2)}%
              </span>
            </div>
            <div className="mt-1.5 flex items-baseline justify-between font-mono">
              <span className="text-xs text-muted-foreground">
                {formatPct(before?.target_position?.weight_pct)}
              </span>
              <ArrowRight className="size-3 text-muted-foreground mx-1" />
              <span className="text-sm font-bold text-sky-300">
                {formatPct(after?.target_position?.weight_pct)}
              </span>
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground font-mono truncate">
              {formatNumber(after?.target_position?.quantity, 2)} adet ({formatCurrency(after?.target_position?.position_value, inst?.currency)})
            </div>
          </div>

          {/* Column 2: Cash Impact */}
          <div className="rounded-lg border border-border/40 bg-muted/20 p-2.5">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <DollarSign className="size-3 text-emerald-400" />
                Nakit Oranı
              </span>
              <span
                className={cn(
                  'text-[10px] font-semibold font-mono flex items-center',
                  cashWeightDelta > 0 ? 'text-emerald-400' : cashWeightDelta < 0 ? 'text-amber-400' : 'text-muted-foreground'
                )}
              >
                {cashWeightDelta > 0 ? '+' : ''}
                {formatNumber(cashWeightDelta, 2)}%
              </span>
            </div>
            <div className="mt-1.5 flex items-baseline justify-between font-mono">
              <span className="text-xs text-muted-foreground">
                {formatPct(before?.cash?.cash_weight_pct)}
              </span>
              <ArrowRight className="size-3 text-muted-foreground mx-1" />
              <span className="text-sm font-bold text-emerald-300">
                {formatPct(after?.cash?.cash_weight_pct)}
              </span>
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground font-mono truncate">
              {tx?.net_cash_delta !== undefined && (
                <span className={tx.net_cash_delta >= 0 ? 'text-emerald-400' : 'text-amber-400'}>
                  {tx.net_cash_delta >= 0 ? '+' : ''}
                  {formatCurrency(tx.net_cash_delta, tx.currency)}
                </span>
              )}
            </div>
          </div>

          {/* Column 3: Total Portfolio Base Value */}
          <div className="rounded-lg border border-border/40 bg-muted/20 p-2.5">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <Layers className="size-3 text-indigo-400" />
                Toplam Portföy
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {before?.base_currency || 'TRY'}
              </span>
            </div>
            <div className="mt-1.5 flex items-baseline justify-between font-mono">
              <span className="text-xs text-muted-foreground">
                {formatNumber(before?.total_value_base, 0)}
              </span>
              <ArrowRight className="size-3 text-muted-foreground mx-1" />
              <span className="text-sm font-bold text-foreground">
                {formatNumber(after?.total_value_base, 0)} {after?.base_currency}
              </span>
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground font-mono truncate">
              {tx?.fee !== undefined && tx.fee > 0 ? (
                <span className="text-rose-400">Komisyon: {formatCurrency(tx.fee, tx.currency)}</span>
              ) : (
                <span className="text-muted-foreground">Değer korundu (Sıfır komisyon)</span>
              )}
            </div>
          </div>
        </div>

        {/* Cash Shortfall Warning if BUY is not affordable */}
        {tx?.is_affordable === false && tx?.cash_shortfall > 0 && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0 text-amber-400" />
              <span>Nakit Bakiyesi Yetersiz (Açık: {formatCurrency(tx.cash_shortfall, tx.currency)})</span>
            </div>
            <Badge variant="outline" className="border-amber-500/40 text-[10px] text-amber-300">
              Ek Fonlama Gerekir
            </Badge>
          </div>
        )}

        {/* Deterministic Allocation Shifts Preview */}
        {simulation.allocation_after?.by_type && simulation.allocation_after.by_type.length > 0 && (
          <div className="rounded-lg border border-border/30 bg-muted/10 p-2.5 space-y-1.5">
            <div className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
              <PieChart className="size-3 text-sky-400" />
              <span>Varlık Türü Dağılım Değişimi:</span>
            </div>
            <div className="flex flex-wrap gap-2 pt-0.5">
              {simulation.allocation_after.by_type.map((item, idx) => {
                const beforeItem = simulation.allocation_before?.by_type?.find(
                  (b) => b.asset_type === item.asset_type
                )
                const delta = item.percentage - (beforeItem?.percentage ?? 0)
                return (
                  <div
                    key={idx}
                    className="flex items-center gap-1.5 rounded bg-background/80 px-2 py-1 text-[11px] border border-border/40 font-mono"
                  >
                    <span className="text-muted-foreground font-sans font-medium">
                      {item.asset_type}:
                    </span>
                    <span className="text-foreground font-semibold">
                      {formatPct(item.percentage)}
                    </span>
                    {Math.abs(delta) >= 0.05 && (
                      <span
                        className={cn(
                          'text-[10px]',
                          delta > 0 ? 'text-teal-400' : 'text-rose-400'
                        )}
                      >
                        ({delta > 0 ? '+' : ''}
                        {formatNumber(delta, 1)}%)
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Assumptions & Notes */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/30 pt-2 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <Info className="size-3 text-sky-400" />
            <span>
              Referans:{' '}
              {assumptions?.price_source === 'EXPLICIT_SCENARIO_PRICE'
                ? 'Senaryo Fiyatı'
                : 'Son Piyasa Fiyatı'}
            </span>
            {assumptions?.price && (
              <span className="font-mono text-foreground font-medium">
                ({formatCurrency(assumptions.price, assumptions?.price_currency || inst?.currency)})
              </span>
            )}
          </div>

          <div className="text-[10px] text-muted-foreground/80 italic">
            Bu senaryo veritabanında saklanmaz ve portföyünüze kaydedilmez.
          </div>
        </div>
      </div>
    </div>
  )
}
