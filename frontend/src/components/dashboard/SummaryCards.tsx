import { useState, useMemo, useEffect } from 'react'
import { Eye, EyeOff, TrendingUp, TrendingDown } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/utils/cn'
import { Skeleton } from '@/components/ui/skeleton'
import { convertCurrency, type ForexRates } from '@/hooks/useForexRates'
import { useDashboardTimeline } from '@/hooks/useDashboard'
import { dashboardService } from '@/services/dashboardService'
import type { DashboardSummary, TimelinePoint } from '@/types'
import { formatCurrency, formatPercent } from '@/utils/format'
import { buildTimelinePoints, convertSnapshotValue } from '@/utils/timeline'

interface Props {
  data: DashboardSummary | null
  isLoading: boolean
  currency?: string
  rates?: ForexRates
}

const TIMEFRAMES = [
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: 'ALL', days: 1825 },
]

export default function SummaryCards({
  data,
  isLoading,
  currency = 'TRY',
  rates = {},
}: Props) {
  const [showValues, setShowValues] = useState(true)
  const [selectedDays, setSelectedDays] = useState(90)
  const [cachedSnapshots, setCachedSnapshots] = useState<Map<string, TimelinePoint>>(new Map())

  const timeline = useDashboardTimeline(selectedDays)

  useEffect(() => {
    let isMounted = true
    dashboardService.createSnapshot()
      .then(() => {
        if (isMounted) {
          timeline.refetch()
        }
      })
      .catch(() => {
        // Silently ignore snapshot errors on initial load (e.g. guest or offline)
      })
    return () => {
      isMounted = false
    }
  }, [timeline.refetch])

  // Accumulate known snapshots across timeframe switches to support forward-fill across range boundaries
  useEffect(() => {
    const incoming = timeline.data
    if (incoming && incoming.length > 0) {
      setCachedSnapshots((prev) => {
        let changed = false
        const next = new Map(prev)
        for (const pt of incoming) {
          if (!next.has(pt.date)) {
            next.set(pt.date, pt)
            changed = true
          }
        }
        return changed ? next : prev
      })
    }
  }, [timeline.data])

  const allSnapshots = useMemo(() => {
    const map = new Map(cachedSnapshots)
    if (timeline.data) {
      for (const pt of timeline.data) {
        map.set(pt.date, pt)
      }
    }
    return Array.from(map.values())
  }, [cachedSnapshots, timeline.data])

  const baseCurrency = data?.base_currency ?? 'TRY'
  const convert = (amount: number) => convertCurrency(amount, baseCurrency, currency, rates)

  const totalAssets = convert(data?.total_assets ?? data?.total_value ?? 0)
  const totalLiabilities = convert(data?.total_liabilities ?? 0)
  const netWorth = convert(data?.net_worth ?? 0)
  const totalCash = convert(data?.total_cash ?? 0)
  const totalPl = convert(data?.total_pl ?? 0)
  const totalPlPct = data?.total_pl_pct ?? 0

  const cashPct = (totalAssets != null && totalAssets > 0 && totalCash != null)
    ? (totalCash / totalAssets) * 100
    : 0

  // Raw recorded snapshots in current timeline data, converted to display currency
  const recordedPoints = useMemo(() => {
    if (!timeline.data || timeline.data.length === 0) return []
    return timeline.data.map((pt) => ({
      date: pt.date,
      value: convertSnapshotValue(pt, currency, rates),
    }))
  }, [timeline.data, currency, rates])

  const hasUnavailableRate = recordedPoints.some((point) => point.value == null)

  // Continuous calendar points with forward fill for the selected timeframe
  const chartPoints = useMemo(() => {
    return buildTimelinePoints(allSnapshots, selectedDays, currency, rates)
  }, [allSnapshots, selectedDays, currency, rates])

  const displayPoints = useMemo(() => {
    if (chartPoints.length === 1) {
      // Recharts Area cannot render a 0-width single point.
      // Providing a start-to-end duplicate allows the baseline level to render.
      return [
        { ...chartPoints[0], _span: 'start' },
        { ...chartPoints[0], _span: 'end' },
      ]
    }
    return chartPoints
  }, [chartPoints])

  const nonNullPoints = useMemo(() => {
    return displayPoints.filter((p) => p.value != null)
  }, [displayPoints])

  const hasAnyHistory = nonNullPoints.length > 0
  const allSameValue = nonNullPoints.length > 0 && nonNullPoints.every((p) => p.value === nonNullPoints[0].value)
  const singleTick = allSameValue && nonNullPoints.length > 0 ? [nonNullPoints[0].value as number] : undefined

  // Change between the two recorded snapshots; do not invent a daily return.
  const snapshotChange = useMemo(() => {
    if (recordedPoints.length >= 2) {
      const current = recordedPoints[recordedPoints.length - 1].value
      const prev = recordedPoints[recordedPoints.length - 2].value
      if (current == null || prev == null) return null
      const diff = current - prev
      const pct = prev > 0 ? (diff / prev) * 100 : 0
      return { diff, pct }
    }
    return null
  }, [recordedPoints])

  if (isLoading) {
    return (
      <Card className="dashboard-card flex h-full min-h-[330px] flex-col" aria-label="Loading portfolio summary" aria-busy="true">
        <CardHeader className="p-5 pb-2"><Skeleton className="h-5 w-40" /></CardHeader>
        <CardContent className="flex flex-1 flex-col gap-4 px-5 pb-4">
          <Skeleton className="h-10 w-52" />
          <Skeleton className="h-36 w-full" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        </CardContent>
      </Card>
    )
  }

  const isPositivePl = (totalPl ?? 0) >= 0
  const isPositiveDay = (snapshotChange?.diff ?? 0) >= 0
  const balance = (value: number | null) => !showValues ? '••••' : value == null ? 'Unavailable' : formatCurrency(value, currency)

  return (
    <Card className="dashboard-card dashboard-summary flex h-full min-w-0 flex-col" aria-label="Portfolio value and history">
      <CardHeader className="dashboard-summary-header flex flex-row flex-wrap items-center justify-between gap-2 p-5 pb-0">
        <div className="flex items-center gap-1">
          <CardTitle className="dashboard-card-title">Total Portfolio Value</CardTitle>
          <span className="sr-only">Net Worth</span>
          <Button variant="ghost" size="icon" className="size-7" onClick={() => setShowValues(!showValues)}
            title={showValues ? 'Hide balances' : 'Show balances'} aria-label={showValues ? 'Hide balances' : 'Show balances'}>
            {showValues ? <Eye /> : <EyeOff />}
          </Button>
        </div>
        <ToggleGroup type="single" size="sm" value={String(selectedDays)} aria-label="History timeframe"
          onValueChange={(value) => { if (value) setSelectedDays(Number(value)) }} className="dashboard-timeframes">
          {TIMEFRAMES.map((tf) => <ToggleGroupItem key={tf.label} value={String(tf.days)}>{tf.label}</ToggleGroupItem>)}
        </ToggleGroup>
      </CardHeader>
      <CardContent className="flex min-w-0 flex-1 flex-col gap-2 px-5 pb-2 pt-1">
        <div className="flex flex-col gap-1">
          <p className="financial-value break-words text-3xl font-bold sm:text-4xl">{balance(netWorth)}</p>
          {snapshotChange && !timeline.isLoading && !timeline.error ? (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              {isPositiveDay ? <TrendingUp className="size-3.5 text-positive" /> : <TrendingDown className="size-3.5 text-negative" />}
              <span className={cn('financial-value font-medium', isPositiveDay ? 'text-positive' : 'text-negative')}>
                {showValues ? `${isPositiveDay ? '+' : ''}${formatCurrency(snapshotChange.diff, currency)} (${formatPercent(snapshotChange.pct)})` : '••••'}
              </span>
              <span className="text-muted-foreground">Since previous snapshot</span>
            </div>
          ) : <p className="text-xs text-muted-foreground">Snapshot change unavailable</p>}
        </div>
        <div className="mt-1 h-[156px] min-w-0 w-full" aria-label="Portfolio history chart">
          {timeline.isLoading ? <Skeleton className="h-full w-full" aria-label="Loading portfolio history" />
            : timeline.error ? <div role="alert" className="flex h-full items-center justify-center text-sm text-muted-foreground">Historical data unavailable</div>
            : hasUnavailableRate ? <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Exchange rate unavailable</div>
            : !showValues ? <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Balances hidden</div>
            : hasAnyHistory ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={displayPoints} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="heroGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--info))" stopOpacity={0.26} />
                      <stop offset="100%" stopColor="hsl(var(--info))" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeOpacity={0.6} strokeDasharray="2 4" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} minTickGap={55}
                    tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    tickFormatter={(date: string) => new Date(date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} />
                  <YAxis width={48} axisLine={false} tickLine={false} tickCount={4} domain={['auto', 'auto']}
                    ticks={singleTick}
                    tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    tickFormatter={(value: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)} />
                  <Tooltip content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    const val = payload[0].value as number | null
                    return <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-card">
                      <p className="mb-1 text-muted-foreground">{label}</p>
                      <p className="financial-value font-semibold">
                        {val == null ? 'Unavailable' : formatCurrency(val, currency)}
                      </p>
                    </div>
                  }} />
                  <Area type="monotone" dataKey="value" stroke="hsl(var(--info))" strokeWidth={2}
                    fill="url(#heroGradient)" isAnimationActive={false} connectNulls={false}
                    dot={nonNullPoints.length === 1 ? { r: 3, fill: 'hsl(var(--info))' } : false}
                    activeDot={{ r: 4, strokeWidth: 4, stroke: 'hsl(var(--info) / 0.25)' }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <p className="text-sm text-muted-foreground">No portfolio history yet</p>
              <p className="text-xs text-muted-foreground">Recorded snapshots will appear here.</p>
            </div>}
        </div>
      </CardContent>
      <div className="px-5"><Separator /></div>
      <CardFooter className="dashboard-metrics grid grid-cols-2 gap-x-4 gap-y-4 p-5 pb-4 pt-3 sm:grid-cols-4 sm:divide-x sm:divide-border/60 [&>div]:min-w-0 sm:[&>div:not(:first-child)]:pl-4">
        <div><p className="dashboard-metric-label">Total Assets</p><p className="dashboard-metric-value">{balance(totalAssets)}</p></div>
        <div><p className="dashboard-metric-label">Total Liabilities</p><p className="dashboard-metric-value">{balance(totalLiabilities)}</p></div>
        <div><p className="dashboard-metric-label">Cash</p>
          <div className="flex flex-wrap items-baseline gap-x-1.5"><span className="dashboard-metric-value">{balance(totalCash)}</span>
            <span className="text-[10px] text-muted-foreground">{showValues ? `${cashPct.toFixed(1)}% of portfolio` : '••••'}</span></div>
        </div>
        <div><p className="dashboard-metric-label">Portfolio P/L</p>
          <div className={cn('flex flex-wrap items-baseline gap-x-1.5', isPositivePl ? 'text-positive' : 'text-negative')}>
            <span className="dashboard-metric-value">{showValues && totalPl != null && isPositivePl ? '+' : ''}{balance(totalPl)}</span>
            <span className="text-[10px]">{showValues ? `${formatPercent(totalPlPct)} all time` : '••••'}</span>
          </div>
        </div>
      </CardFooter>
    </Card>
  )
}
