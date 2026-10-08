import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import type { AllocationData, DashboardSummary } from '@/types'

interface Props {
  allocation: AllocationData | null
  summary: DashboardSummary | null
}

export default function PortfolioRiskCard({ allocation, summary }: Props) {
  return (
    <Card className="dashboard-card h-full">
      <CardHeader className="flex flex-row items-center justify-between gap-2 p-5 pb-3">
        <CardTitle className="dashboard-card-title">Portfolio Context</CardTitle>
        <Link to="/allocation" className="inline-flex items-center gap-1 text-xs text-info hover:text-foreground">
          View details <ArrowUpRight className="size-3" />
        </Link>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-5 pb-5">
        <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Holdings</span><span className="financial-value font-semibold">{summary?.asset_count ?? 'Unavailable'}</span></div>
        <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Asset categories</span><span className="financial-value font-semibold">{allocation?.by_type.length ?? 'Unavailable'}</span></div>
        <p className="text-xs leading-relaxed text-muted-foreground">Beta, Sharpe ratio and maximum drawdown are not available.</p>
      </CardContent>
    </Card>
  )
}
