import { TrendingUp, TrendingDown } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency, formatPercent, plColorClass } from '@/utils/format'
import { convertCurrency, type ForexRates } from '@/hooks/useForexRates'
import { cn } from '@/utils/cn'
import type { DashboardSummary, TypeSummary } from '@/types'

interface Props {
  data: DashboardSummary | null
  isLoading: boolean
  currency?: string
  rates?: ForexRates
}

function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 py-2">
      <Skeleton className="h-4 w-4 rounded-full bg-slate-800" />
      <Skeleton className="h-3 flex-1 bg-slate-800" />
      <Skeleton className="h-3 w-16 bg-slate-800" />
    </div>
  )
}

function TypeRow({
  t,
  showIcon,
  currency,
  rates,
  baseCurrency,
}: {
  t: TypeSummary
  showIcon: 'up' | 'down'
  currency: string
  rates: ForexRates
  baseCurrency: string
}) {
  const Icon = showIcon === 'up' ? TrendingUp : TrendingDown
  const conv = (v: number) => convertCurrency(v, baseCurrency, currency, rates)
  const formatted = (v: number) => {
    const converted = conv(v)
    return converted == null ? 'Unavailable' : formatCurrency(converted, currency)
  }
  const formattedPl = (() => {
    const converted = conv(t.pl)
    if (converted == null) return 'Unavailable'
    return `${t.pl >= 0 ? '+' : ''}${formatCurrency(converted, currency)}`
  })()
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-slate-800 last:border-0">
      <span
        className={cn(
          'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg',
          t.pl >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10',
        )}
      >
        <Icon
          className={cn('h-3.5 w-3.5', t.pl >= 0 ? 'text-emerald-400' : 'text-red-400')}
          strokeWidth={2}
        />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-slate-200 truncate">{t.asset_type}</p>
        <p className="text-xs text-slate-500">{formatted(t.total_value)}</p>
      </div>
      <div className="text-right flex-shrink-0">
        <p className={cn('text-xs font-semibold', plColorClass(t.pl_pct))}>
          {formatPercent(t.pl_pct)}
        </p>
        <p className={cn('text-xs', plColorClass(t.pl))}>
          {formattedPl}
        </p>
      </div>
    </div>
  )
}

export default function PerformersSection({ data, isLoading, currency = 'TRY', rates = {} }: Props) {
  const byType = data?.by_type_summary ?? []
  const baseCurrency = data?.base_currency ?? 'TRY'
  const sorted = [...byType].sort((a, b) => b.pl_pct - a.pl_pct)
  const best = sorted.slice(0, 5)
  const worst = [...byType].sort((a, b) => a.pl_pct - b.pl_pct).slice(0, 5)

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Best */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
          Best Performers
        </h3>
        {isLoading ? (
          <div className="space-y-1">{[0, 1, 2].map((i) => <RowSkeleton key={i} />)}</div>
        ) : best.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">No data yet</p>
        ) : (
          best.map((t) => (
            <TypeRow key={t.asset_type} t={t} showIcon="up" currency={currency} rates={rates} baseCurrency={baseCurrency} />
          ))
        )}
      </div>

      {/* Worst */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
          Worst Performers
        </h3>
        {isLoading ? (
          <div className="space-y-1">{[0, 1, 2].map((i) => <RowSkeleton key={i} />)}</div>
        ) : worst.length === 0 ? (
          <p className="text-sm text-slate-500 py-4">No data yet</p>
        ) : (
          worst.map((t) => (
            <TypeRow key={t.asset_type} t={t} showIcon="down" currency={currency} rates={rates} baseCurrency={baseCurrency} />
          ))
        )}
      </div>
    </div>
  )
}
