import { useState } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency } from '@/utils/format'
import { convertCurrency, type ForexRates } from '@/hooks/useForexRates'
import { useDashboardTimeline } from '@/hooks/useDashboard'
import { cn } from '@/utils/cn'

const TIME_FILTERS: { label: string; days: number }[] = [
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
]

const CURRENCY_SYMBOLS: Record<string, string> = { TRY: '₺', USD: '$', EUR: '€', GBP: '£' }

function ChartTooltip({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean
  payload?: Array<{
    value: number
    payload?: { valueSemantics?: 'gross_assets' | 'net_worth' }
  }>
  label?: string
  currency: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-popover/95 px-3 py-2 text-xs shadow-card">
      <p className="mb-1 text-muted-foreground">{label}</p>
      <p className="financial-value font-semibold text-popover-foreground">
        {formatCurrency(payload[0].value, currency)}
      </p>
      <p className="mt-1 text-muted-foreground">
        {payload[0].payload?.valueSemantics === 'gross_assets'
          ? 'Legacy gross assets'
          : 'Net worth'}
      </p>
    </div>
  )
}

function formatAxisDate(dateStr: string) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' })
}

function formatAxisValue(v: number, currency: string) {
  const sym = CURRENCY_SYMBOLS[currency] ?? currency
  if (v >= 1_000_000) return `${sym}${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${sym}${(v / 1_000).toFixed(0)}K`
  return `${sym}${v}`
}

interface Props {
  currency?: string
  rates?: ForexRates
}

export default function TimelineChart({ currency = 'TRY', rates = {} }: Props) {
  const [activeDays, setActiveDays] = useState(90)
  const { data, isLoading } = useDashboardTimeline(activeDays)

  const convertedData = data?.map((point) => {
    const tryValue = point.net_worth_try ?? point.total_value_try
    const usdValue = point.net_worth_usd ?? point.total_value_usd
    let value: number | null
    if (currency === 'USD') {
      value = usdValue
    } else if (currency === 'TRY') {
      value = tryValue
    } else {
      value = convertCurrency(tryValue, 'TRY', currency, rates)
    }
    return {
      date: point.date,
      value,
      valueSemantics: point.value_semantics ?? 'gross_assets',
    }
  })
  const hasUnavailableRate = convertedData?.some((point) => point.value == null) ?? false
  const hasLegacyPoints =
    convertedData?.some((point) => point.valueSemantics === 'gross_assets') ?? false
  const chartData = hasUnavailableRate
    ? null
    : convertedData as Array<{
        date: string
        value: number
        valueSemantics: 'gross_assets' | 'net_worth'
      }> | undefined

  return (
    <div className="data-surface p-5">
      {/* Header */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold">
          Net Worth Timeline
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          {hasLegacyPoints && (
            <span className="text-xs text-muted-foreground">Includes legacy gross-assets data</span>
          )}
          <div className="flex gap-1">
          {TIME_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setActiveDays(f.days)}
              className={cn(
                'px-2.5 py-1 text-xs rounded-md font-medium transition-all duration-150',
                activeDays === f.days
                      ? 'border border-primary/30 bg-primary/15 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              {f.label}
            </button>
          ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      {isLoading ? (
        <Skeleton className="h-48 w-full rounded-lg" />
      ) : hasUnavailableRate ? (
        <div className="flex h-48 items-center justify-center">
          <p className="text-sm text-muted-foreground">Exchange rate unavailable</p>
        </div>
      ) : !chartData || chartData.length === 0 ? (
        <div className="flex h-48 items-center justify-center">
          <p className="text-sm text-muted-foreground">
            No snapshot data yet — use &ldquo;Refresh snapshot&rdquo; to record today&apos;s value
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="tlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatAxisDate}
              tick={{ fontSize: 10, fill: '#475569' }}
              axisLine={false}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              tickFormatter={(v) => formatAxisValue(v, currency)}
              tick={{ fontSize: 10, fill: '#475569' }}
              axisLine={false}
              tickLine={false}
              width={60}
            />
            <Tooltip content={<ChartTooltip currency={currency} />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#10B981"
              strokeWidth={2}
              fill="url(#tlGrad)"
              dot={false}
              activeDot={{ r: 4, fill: '#10B981', stroke: '#0f172a', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
