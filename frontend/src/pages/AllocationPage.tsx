import { useMemo } from 'react'
import { Scale, PieChart, ShieldAlert, Info } from 'lucide-react'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import AllocationChart from '@/components/dashboard/AllocationChart'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Skeleton } from '@/components/ui/skeleton'
import { useDashboardAllocation } from '@/hooks/useDashboard'
import { useForexRates, convertCurrency } from '@/hooks/useForexRates'
import { useDashboardStore, type DashboardCurrency } from '@/store/dashboardStore'
import { formatCurrency } from '@/utils/format'
import { typeLabel, typeColor } from '@/utils/assetTypes'

const CURRENCIES: DashboardCurrency[] = ['TRY', 'USD', 'EUR']

// Default benchmark allocation model targets for diversified portfolio
const DEFAULT_TARGETS: Record<string, number> = {
  STOCK: 40,
  FUND: 20,
  PRECIOUS_METALS: 15,
  CRYPTO: 10,
  FOREX: 10,
  REAL_ESTATE: 5,
  CUSTOM: 0,
}

export default function AllocationPage() {
  const allocation = useDashboardAllocation()
  const { currency, setCurrency } = useDashboardStore()
  const { rates } = useForexRates()

  const categories = allocation.data?.by_type ?? []
  const baseCurrency = allocation.data?.base_currency ?? 'TRY'

  const totalValue = useMemo(() => {
    return categories.reduce((sum, item) => sum + item.value, 0)
  }, [categories])

  const convertedTotal = useMemo(() => {
    return convertCurrency(totalValue, baseCurrency, currency, rates) ?? totalValue
  }, [totalValue, baseCurrency, currency, rates])

  // Table rows with current vs target drift
  const rows = useMemo(() => {
    return categories.map((item) => {
      const currentPct = item.percentage
      const targetPct = DEFAULT_TARGETS[item.asset_type] ?? 10
      const drift = currentPct - targetPct
      const convertedVal = convertCurrency(item.value, baseCurrency, currency, rates) ?? item.value

      let driftStatus: 'OVERWEIGHT' | 'UNDERWEIGHT' | 'BALANCED' = 'BALANCED'
      if (drift > 5) driftStatus = 'OVERWEIGHT'
      else if (drift < -5) driftStatus = 'UNDERWEIGHT'

      return {
        ...item,
        currentPct,
        targetPct,
        drift,
        driftStatus,
        convertedVal,
      }
    })
  }, [categories, baseCurrency, currency, rates])

  const maxCategory = useMemo(() => {
    if (rows.length === 0) return null
    return [...rows].sort((a, b) => b.currentPct - a.currentPct)[0]
  }, [rows])

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Portfolio Allocation"
          description="Analyze asset distribution, target allocations, and strategic rebalancing drift."
          actions={
            <ToggleGroup
              type="single"
              value={currency}
              onValueChange={(val) => val && setCurrency(val as DashboardCurrency)}
              className="border border-border/60 bg-background/50 rounded-lg p-0.5"
            >
              {CURRENCIES.map((c) => (
                <ToggleGroupItem
                  key={c}
                  value={c}
                  className="px-2.5 py-1 text-xs font-mono font-medium data-[state=on]:bg-muted data-[state=on]:text-foreground"
                >
                  {c}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          }
        />

        {/* Top visual grid: Chart & Concentration Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <AllocationChart
              data={allocation.data}
              isLoading={allocation.isLoading}
              currency={currency}
              rates={rates}
            />
          </div>

          <div className="flex flex-col gap-4">
            <Card className="border-border/60 bg-card/40 flex-1">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <span className="flex size-7 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400">
                    <Scale className="size-4" />
                  </span>
                  <CardTitle className="text-sm font-semibold">Allocation Health</CardTitle>
                </div>
                <CardDescription className="text-xs text-muted-foreground">
                  Concentration and portfolio diversification profile.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                <div>
                  <p className="text-[11px] text-muted-foreground uppercase font-medium">Total Portfolio Value</p>
                  <p className="text-lg font-bold font-mono text-foreground mt-0.5">
                    {allocation.isLoading ? (
                      <Skeleton className="h-6 w-32" />
                    ) : (
                      formatCurrency(convertedTotal, currency)
                    )}
                  </p>
                </div>

                {maxCategory && (
                  <div className="pt-3 border-t border-border/40 space-y-1">
                    <p className="text-[11px] text-muted-foreground uppercase font-medium">Largest Asset Class</p>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-foreground">
                        {typeLabel(maxCategory.asset_type)}
                      </span>
                      <span className="font-mono font-bold text-teal-300">
                        {maxCategory.currentPct.toFixed(1)}%
                      </span>
                    </div>
                    {maxCategory.currentPct > 45 && (
                      <div className="flex items-start gap-1.5 text-[11px] text-amber-400 bg-amber-500/10 p-2 rounded-md border border-amber-500/20 mt-2">
                        <ShieldAlert className="size-3.5 shrink-0 mt-0.5" />
                        <span>High concentration in single asset class. Consider diversifying future contributions.</span>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-border/60 bg-card/40">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Info className="size-4 text-teal-400" />
                  <CardTitle className="text-xs font-semibold">Rebalancing Philosophy</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="text-[11px] text-muted-foreground leading-relaxed">
                PortfolioMind recommends drift-based rebalancing: allocate new savings to underweight categories rather than selling winners prematurely to minimize friction and taxes.
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Detailed Breakdown & Drift Table */}
        <div className="rounded-xl border border-border/60 bg-card/40 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Target Drift Analysis</h3>
              <p className="text-xs text-muted-foreground">
                Comparing current asset weights against standard strategic asset allocation benchmarks.
              </p>
            </div>
            <span className="text-xs text-muted-foreground font-mono">
              {rows.length} asset classes
            </span>
          </div>

          {allocation.isLoading ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg bg-card/60 border border-border/60" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="py-12 text-center">
              <PieChart className="size-8 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">No asset allocation data found.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/60 text-[11px] text-muted-foreground uppercase font-semibold text-left">
                    <th className="pb-3 pl-2">Asset Class</th>
                    <th className="pb-3 text-right">Current Value</th>
                    <th className="pb-3 text-right">Current %</th>
                    <th className="pb-3 text-right">Target %</th>
                    <th className="pb-3 text-right">Drift</th>
                    <th className="pb-3 text-right pr-2">Alignment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {rows.map((row) => {
                    const color = typeColor(row.asset_type)
                    return (
                      <tr key={row.asset_type} className="hover:bg-muted/20 transition-colors">
                        <td className="py-3 pl-2">
                          <div className="flex items-center gap-2">
                            <span
                              className="size-2.5 rounded-full shrink-0"
                              style={{ backgroundColor: color }}
                            />
                            <span className="font-semibold text-foreground">
                              {typeLabel(row.asset_type)}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 text-right font-mono text-foreground">
                          {formatCurrency(row.convertedVal, currency)}
                        </td>
                        <td className="py-3 text-right font-mono font-semibold text-foreground">
                          {row.currentPct.toFixed(1)}%
                        </td>
                        <td className="py-3 text-right font-mono text-muted-foreground">
                          {row.targetPct.toFixed(1)}%
                        </td>
                        <td className="py-3 text-right font-mono">
                          <span
                            className={
                              row.drift > 5
                                ? 'text-amber-400 font-semibold'
                                : row.drift < -5
                                ? 'text-blue-400 font-semibold'
                                : 'text-muted-foreground'
                            }
                          >
                            {row.drift > 0 ? `+${row.drift.toFixed(1)}%` : `${row.drift.toFixed(1)}%`}
                          </span>
                        </td>
                        <td className="py-3 text-right pr-2">
                          {row.driftStatus === 'OVERWEIGHT' && (
                            <Badge variant="outline" className="border-amber-500/30 text-amber-300 bg-amber-500/10 text-[10px]">
                              Overweight
                            </Badge>
                          )}
                          {row.driftStatus === 'UNDERWEIGHT' && (
                            <Badge variant="outline" className="border-blue-500/30 text-blue-300 bg-blue-500/10 text-[10px]">
                              Underweight
                            </Badge>
                          )}
                          {row.driftStatus === 'BALANCED' && (
                            <Badge variant="outline" className="border-teal-500/30 text-teal-300 bg-teal-500/10 text-[10px]">
                              Aligned
                            </Badge>
                          )}
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
    </AppShell>
  )
}
