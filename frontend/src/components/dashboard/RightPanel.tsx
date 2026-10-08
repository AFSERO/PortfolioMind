import { Clock3, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { type ForexRates } from '@/hooks/useForexRates'
import { api } from '@/services/api'
import type { AllocationData, DashboardSummary } from '@/types'
import { typeLabel } from '@/utils/assetTypes'

interface Props {
  summary: DashboardSummary | null
  allocation: AllocationData | null
  isLoading: boolean
  onRefresh: () => void
  currency?: string
  rates?: ForexRates
}

function freshness(summary: DashboardSummary | null) {
  const metadata = summary?.exchange_rates
  if (!metadata) return { label: 'No freshness metadata', detail: 'Dashboard values use the latest available data.' }
  const timestamps = metadata.rates
    .map((rate) => rate.fetched_at)
    .filter((value): value is string => Boolean(value))
    .map((value) => new Date(value))
    .filter((value) => !Number.isNaN(value.getTime()))
  const latest = timestamps.sort((a, b) => b.getTime() - a.getTime())[0]
  return {
    label: metadata.status === 'stale' ? 'Some exchange rates are stale' : 'Exchange rates complete',
    detail: latest ? `Latest rate ${latest.toLocaleString()}` : 'No provider timestamp returned.',
  }
}

export default function RightPanel({ summary, allocation, isLoading, onRefresh }: Props) {
  const [snapshotting, setSnapshotting] = useState(false)
  const dataFreshness = freshness(summary)

  const handleSnapshot = async () => {
    setSnapshotting(true)
    try {
      await api.post('/dashboard/snapshot', {})
      toast.success('Snapshot recorded')
      onRefresh()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create snapshot')
    } finally {
      setSnapshotting(false)
    }
  }

  return (
    <Card className="h-full shadow-card">
      <CardHeader>
        <CardTitle className="text-base">Portfolio context</CardTitle>
        <CardDescription>Allocation coverage and data freshness</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {isLoading ? <Skeleton className="h-28 w-full" /> : (
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">By category</p>
            {allocation?.by_type.length ? (
              <div className="flex flex-col gap-3">
                {[...allocation.by_type].sort((a, b) => b.value - a.value).slice(0, 5).map((item) => (
                  <div key={item.asset_type} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-muted-foreground">{typeLabel(item.asset_type)}</span>
                    <span className="financial-value font-medium">{item.percentage.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-muted-foreground">No assets added yet.</p>}
          </div>
        )}
        <div className="border-t pt-5">
          <div className="flex items-start gap-3">
            <Clock3 className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium">{dataFreshness.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{dataFreshness.detail}</p>
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={handleSnapshot} disabled={snapshotting} className="w-full">
          <RefreshCw className={snapshotting ? 'animate-spin' : undefined} aria-hidden="true" />
          {snapshotting ? 'Recording…' : "Record today's snapshot"}
        </Button>
      </CardContent>
    </Card>
  )
}
