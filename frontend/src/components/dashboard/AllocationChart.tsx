import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency } from '@/utils/format'
import { typeColor, typeLabel } from '@/utils/assetTypes'
import { convertCurrency, type ForexRates } from '@/hooks/useForexRates'
import type { AllocationData } from '@/types'

interface Props {
  data: AllocationData | null
  isLoading: boolean
  currency?: string
  rates?: ForexRates
}

function ChartTooltip({
  active,
  payload,
  currency,
  rates,
  baseCurrency,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number; payload: { percentage: number } }>
  currency: string
  rates: ForexRates
  baseCurrency: string
}) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  const converted = convertCurrency(d.value, baseCurrency, currency, rates)
  return (
    <div className="rounded-lg border border-border/80 bg-popover/95 px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-popover-foreground">{typeLabel(d.name)}</p>
      <p className="text-muted-foreground font-mono">
        {converted == null ? 'Unavailable' : formatCurrency(converted, currency)}
      </p>
      <p className="text-teal-400 font-mono font-medium">{d.payload.percentage.toFixed(1)}%</p>
    </div>
  )
}

function SkeletonView() {
  return (
    <Card className="dashboard-card dashboard-allocation flex h-full min-w-0 flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="flex flex-col sm:flex-row items-center gap-6 py-2">
        <Skeleton className="size-40 shrink-0 rounded-full" />
        <div className="flex w-full flex-1 flex-col gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-6 rounded-md shrink-0" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-1.5 w-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

export default function AllocationChart({
  data,
  isLoading,
  currency = 'TRY',
  rates = {},
}: Props) {
  if (isLoading) return <SkeletonView />

  const baseCurrency = data?.base_currency ?? 'TRY'
  const totalConverted = data?.total_value
    ? convertCurrency(data.total_value, baseCurrency, currency, rates)
    : 0

  if (!data || data.by_type.length === 0) {
    return (
      <Card className="dashboard-card dashboard-allocation flex h-full min-w-0 flex-col gap-4 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Portfolio Allocation</h3>
          <Link
            to="/allocation"
            className="text-xs text-info hover:text-foreground font-medium inline-flex items-center gap-1 transition-colors"
          >
            <span>View details</span>
            <ArrowUpRight className="size-3" />
          </Link>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-6 py-6 text-center sm:text-left">
          <div className="size-36 rounded-full border-2 border-dashed border-border/60 flex items-center justify-center">
            <span className="text-xs text-muted-foreground font-mono">0%</span>
          </div>
          <div className="space-y-2 max-w-xs">
            <p className="text-xs font-medium text-foreground">No allocation data yet</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Add holdings across stocks, funds, crypto, or forex to see your diversified asset breakdown.
            </p>
            <Link
              to="/assets"
              className="inline-flex items-center text-xs font-semibold text-info hover:text-foreground"
            >
              + Add first asset
            </Link>
          </div>
        </div>
      </Card>
    )
  }

  const chartData = data.by_type.map((t) => ({
    name: t.asset_type,
    value: t.value,
    percentage: t.percentage,
  }))

  const sortedCategories = [...data.by_type].sort((a, b) => b.value - a.value)

  return (
    <Card className="dashboard-card dashboard-allocation flex h-full min-w-0 flex-col gap-4 p-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Portfolio Allocation</h3>
        <Link
          to="/allocation"
          className="text-xs text-info hover:text-foreground font-medium inline-flex items-center gap-1 transition-colors"
        >
          <span>View details</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </div>

      {/* Main Content: Left Donut, Right Categories */}
      <div className="dashboard-allocation-body flex min-w-0 flex-1 flex-col items-center justify-center gap-5">
        {/* Donut Chart with Center Total */}
        <div className="dashboard-donut relative size-44 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius="68%"
                outerRadius="90%"
                paddingAngle={1}
                dataKey="value"
                stroke="transparent"
              >
                {chartData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={typeColor(entry.name)}
                  />
                ))}
              </Pie>
              <Tooltip
                content={(
                  <ChartTooltip
                    currency={currency}
                    rates={rates}
                    baseCurrency={baseCurrency}
                  />
                )}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Center text in donut */}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground/80 tracking-wider">
              Total
            </span>
            <span className="financial-value mt-1 max-w-[124px] break-words text-sm font-bold text-foreground">
              {totalConverted == null
                ? 'Unavailable'
                : formatCurrency(totalConverted, currency)}
            </span>
          </div>
        </div>

        {/* Largest categories retain their API percentages and converted balances. */}
        <div className="flex w-full min-w-0 flex-1 flex-col">
          {sortedCategories.slice(0, 4).map((t) => {
            const converted = convertCurrency(t.value, baseCurrency, currency, rates)
            return (
              <div key={t.asset_type} className="flex items-start gap-3 border-b border-border/50 py-2.5 last:border-0">
                <span className="mt-1 size-3 shrink-0 rounded-full" style={{ backgroundColor: typeColor(t.asset_type) }} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <span className="min-w-0 text-xs font-medium leading-5" title={typeLabel(t.asset_type)}>{typeLabel(t.asset_type).split(' / ')[0]}</span>
                    <span className="financial-value shrink-0 text-xs font-semibold leading-5">{t.percentage.toFixed(1)}%</span>
                  </div>
                  <p className="financial-value mt-0.5 break-words text-xs text-muted-foreground">{converted == null ? 'Unavailable' : formatCurrency(converted, currency)}</p>
                </div>
              </div>
            )
          })}
          {sortedCategories.length > 4 && <Link to="/allocation" className="text-xs text-info">+{sortedCategories.length - 4} more categories</Link>}
        </div>
      </div>
    </Card>
  )
}
