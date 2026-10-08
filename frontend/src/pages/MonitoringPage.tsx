import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import MonitoringTable from '@/components/monitoring/MonitoringTable'
import { useAssets } from '@/hooks/useAssets'

export default function MonitoringPage() {
  const { assets, isLoading, refetch } = useAssets()

  return (
    <AppShell>
      <div className="app-page space-y-6">
        <PageHeader
          title="Portfolio Monitoring"
          description="Continuous thesis evaluation, valuation bands, and review cadences across all monitored holdings."
        />

        <MonitoringTable assets={assets} isLoading={isLoading} onRefresh={refetch} />
      </div>
    </AppShell>
  )
}
