import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Plus,
  RefreshCw,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronRight,
  Pencil,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import AssetTypeBadge from '@/components/assets/AssetTypeBadge'
import AssetFormDialog from '@/components/assets/AssetFormDialog'
import DeleteConfirmDialog from '@/components/assets/DeleteConfirmDialog'
import { useAssets } from '@/hooks/useAssets'
import { useForexRates, convertCurrency, type ForexRates } from '@/hooks/useForexRates'
import { formatCurrency, formatPercent, plColorClass } from '@/utils/format'
import { ASSET_TYPE_META, typeLabel } from '@/utils/assetTypes'
import type { Asset, AssetType } from '@/types'
import type { AssetCreatePayload, AssetUpdatePayload } from '@/services/assetService'
import { cn } from '@/utils/cn'

// ── Filter tabs ───────────────────────────────────────────────────────────────

const ALL_FILTERS: Array<{ value: string; label: string }> = [
  { value: 'ALL', label: 'All' },
  ...Object.entries(ASSET_TYPE_META).map(([key, meta]) => ({
    value: key,
    label: meta.label,
  })),
]

// ── Sort ──────────────────────────────────────────────────────────────────────

type SortKey =
  | 'name'
  | 'asset_type'
  | 'total_quantity'
  | 'avg_cost'
  | 'current_price'
  | 'total_value'
  | 'pl'
  | 'pl_pct'
type SortDir = 'asc' | 'desc'

interface RowStats {
  /** Currency every monetary value in the row is rendered in (= avg_cost_currency or fallback). */
  displayCurrency: string
  /** Current price converted into displayCurrency (or null if backend has none). */
  currentPriceDisplay: number | null
  totalValue: number | null
  totalCost: number
  unrealizedPl: number | null
  totalPl: number | null
  totalPlPct: number | null
}

/**
 * Per-row computed stats. Backend already provides total_cost, avg_cost,
 * realized_pl, and (when available) current_price; we only do the FX
 * conversion needed to display current price + value in avg_cost_currency.
 */
function rowStats(a: Asset, rates: ForexRates): RowStats {
  const displayCurrency = a.avg_cost_currency ?? a.current_price_currency ?? 'TRY'
  const totalCost = a.total_cost ?? 0
  const realized = a.realized_pl ?? 0

  let currentPriceDisplay: number | null = null
  let totalValue: number | null = totalCost  // fallback when no current price
  let unrealizedPl: number | null = 0

  if (a.current_price != null) {
    currentPriceDisplay = convertCurrency(
      a.current_price,
      a.current_price_currency ?? displayCurrency,
      displayCurrency,
      rates,
    )
    if (currentPriceDisplay == null) {
      totalValue = null
      unrealizedPl = null
    } else {
      totalValue = currentPriceDisplay * a.total_quantity
      unrealizedPl = totalValue - totalCost
    }
  }

  const totalPl = unrealizedPl == null ? null : unrealizedPl + realized
  const totalPlPct = totalPl == null ? null : totalCost > 0 ? (totalPl / totalCost) * 100 : 0

  return {
    displayCurrency,
    currentPriceDisplay,
    totalValue,
    totalCost,
    unrealizedPl,
    totalPl,
    totalPlPct,
  }
}

// ── Skeleton row ─────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-800">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full bg-slate-800" />
        </td>
      ))}
    </tr>
  )
}

// ── Sort header ───────────────────────────────────────────────────────────────

function SortTh({
  label,
  sortKey,
  current,
  dir,
  onSort,
  className,
}: {
  label: string
  sortKey: SortKey
  current: SortKey
  dir: SortDir
  onSort: (k: SortKey) => void
  className?: string
}) {
  const isActive = current === sortKey
  return (
    <th
      className={cn(
        'px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider cursor-pointer select-none whitespace-nowrap hover:text-slate-300 transition-colors',
        className,
      )}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {isActive ? (
          dir === 'asc' ? (
            <ArrowUp className="h-3 w-3 text-emerald-400" />
          ) : (
            <ArrowDown className="h-3 w-3 text-emerald-400" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </span>
    </th>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssetsPage() {
  const navigate = useNavigate()
  const { assets, isLoading, createAsset, updateAsset, deleteAsset, refreshPrices } = useAssets()
  const { rates } = useForexRates()

  const [filter, setFilter] = useState<string>('ALL')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const [formOpen, setFormOpen] = useState(false)
  const [editAsset, setEditAsset] = useState<Asset | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // Precompute stats once per row so sorts and renders share the same numbers
  const rowsWithStats = useMemo(
    () => assets.map((a) => ({ asset: a, stats: rowStats(a, rates) })),
    [assets, rates],
  )

  const displayed = useMemo(() => {
    let list =
      filter === 'ALL' ? rowsWithStats : rowsWithStats.filter((r) => r.asset.asset_type === filter)

    list = [...list].sort((a, b) => {
      let va: number | string
      let vb: number | string
      switch (sortKey) {
        case 'name':           va = a.asset.name.toLowerCase(); vb = b.asset.name.toLowerCase(); break
        case 'asset_type':     va = a.asset.asset_type;          vb = b.asset.asset_type;         break
        case 'total_quantity': va = a.asset.total_quantity;      vb = b.asset.total_quantity;     break
        case 'avg_cost':       va = a.asset.avg_cost ?? 0;       vb = b.asset.avg_cost ?? 0;      break
        case 'current_price':  va = a.stats.currentPriceDisplay ?? 0; vb = b.stats.currentPriceDisplay ?? 0; break
        case 'total_value':    va = a.stats.totalValue ?? 0;     vb = b.stats.totalValue ?? 0;    break
        case 'pl':             va = a.stats.totalPl ?? 0;        vb = b.stats.totalPl ?? 0;       break
        case 'pl_pct':         va = a.stats.totalPlPct ?? 0;     vb = b.stats.totalPlPct ?? 0;    break
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })

    return list
  }, [rowsWithStats, filter, sortKey, sortDir])

  // ── Handlers ────────────────────────────────────────────────────────────────
  const handleSave = async (
    payload: AssetCreatePayload | AssetUpdatePayload,
    id?: string,
  ) => {
    if (id) {
      await updateAsset(id, payload as AssetUpdatePayload)
    } else {
      await createAsset(payload as AssetCreatePayload)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await deleteAsset(deleteTarget.id)
      toast.success(`${deleteTarget.name} deleted`)
      setDeleteTarget(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await refreshPrices()
    } finally {
      setIsRefreshing(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          title="Assets"
          description={`${assets.length} position${assets.length !== 1 ? 's' : ''} in your portfolio.`}
          actions={<>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin')} />
              Refresh Prices
            </Button>
            <Button
              size="sm"
              onClick={() => { setEditAsset(null); setFormOpen(true) }}
            >
              <Plus className="h-4 w-4" />
              Add Asset
            </Button>
          </>}
        />

        {/* Filter tabs */}
        <div className="flex shrink-0 items-center gap-1 overflow-x-auto border-b pb-3">
          {ALL_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors',
                filter === f.value
                  ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent',
              )}
            >
              {f.label}
              {f.value !== 'ALL' && (
                <span className="ml-1.5 text-slate-500">
                  {assets.filter((a) => a.asset_type === (f.value as AssetType)).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto px-8 py-4 [&::-webkit-scrollbar]:hidden [scrollbar-width:none] [-ms-overflow-style:none]">
          {isLoading ? (
            <table className="w-full text-sm">
              <tbody>
                {[1, 2, 3, 4, 5].map((i) => <SkeletonRow key={i} />)}
              </tbody>
            </table>
          ) : displayed.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
              <p className="text-slate-400 text-sm">
                {filter === 'ALL'
                  ? 'No assets yet. Add your first asset to get started.'
                  : `No ${typeLabel(filter)} assets.`}
              </p>
              {filter === 'ALL' && (
                <Button
                  size="sm"
                  onClick={() => { setEditAsset(null); setFormOpen(true) }}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                >
                  <Plus className="h-4 w-4" />
                  Add Asset
                </Button>
              )}
            </div>
          ) : (
            <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <SortTh label="Name" sortKey="name" current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Type" sortKey="asset_type" current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Quantity" sortKey="total_quantity" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortTh label="Avg Cost" sortKey="avg_cost" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortTh label="Current Price" sortKey="current_price" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortTh label="Total Value" sortKey="total_value" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortTh label="Total P/L" sortKey="pl" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <SortTh label="P/L %" sortKey="pl_pct" current={sortKey} dir={sortDir} onSort={handleSort} className="text-right" />
                    <th className="px-4 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayed.map(({ asset, stats }) => (
                    <tr
                      key={asset.id}
                      className="border-b border-slate-800/60 hover:bg-slate-800/40 transition-colors cursor-pointer group"
                      onClick={() => navigate(`/assets/${asset.id}`)}
                    >
                      {/* Name */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div>
                            <div className="flex items-center gap-1.5">
                              <p className="font-medium text-slate-100 group-hover:text-emerald-400 transition-colors">
                                {asset.name}
                              </p>
                              {asset.has_mixed_currencies && (
                                <span
                                  onClick={(e) => e.stopPropagation()}
                                  className="text-amber-400"
                                  title={`Transactions in multiple currencies — values shown in ${stats.displayCurrency}.`}
                                >
                                  <AlertTriangle className="h-3.5 w-3.5" />
                                </span>
                              )}
                            </div>
                            {asset.symbol && (
                              <p className="text-xs text-slate-500">{asset.symbol}</p>
                            )}
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <AssetTypeBadge type={asset.asset_type} size="sm" />
                      </td>

                      {/* Quantity */}
                      <td className="px-4 py-3 text-right text-slate-300">
                        {asset.total_quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                      </td>

                      {/* Avg cost */}
                      <td className="px-4 py-3 text-right text-slate-300">
                        {asset.avg_cost != null
                          ? formatCurrency(asset.avg_cost, stats.displayCurrency)
                          : <span className="text-slate-600">—</span>}
                      </td>

                      {/* Current price (converted) */}
                      <td className="px-4 py-3 text-right text-slate-200">
                        {stats.currentPriceDisplay != null
                          ? formatCurrency(stats.currentPriceDisplay, stats.displayCurrency)
                          : <span className="text-slate-600">—</span>}
                      </td>

                      {/* Total value */}
                      <td className="px-4 py-3 text-right text-slate-200">
                        {stats.totalValue == null
                          ? <span className="text-slate-600">Unavailable</span>
                          : formatCurrency(stats.totalValue, stats.displayCurrency)}
                      </td>

                      {/* Total P/L */}
                      <td className={cn('px-4 py-3 text-right font-medium', stats.totalPl == null ? 'text-slate-600' : plColorClass(stats.totalPl))}>
                        {stats.totalPl == null
                          ? <span>Unavailable</span>
                          : asset.current_price != null || asset.realized_pl !== 0
                          ? formatCurrency(stats.totalPl, stats.displayCurrency)
                          : <span className="text-slate-600">—</span>}
                      </td>

                      {/* P/L % */}
                      <td className={cn('px-4 py-3 text-right font-medium', stats.totalPlPct == null ? 'text-slate-600' : plColorClass(stats.totalPlPct))}>
                        {stats.totalPlPct == null
                          ? <span>Unavailable</span>
                          : asset.current_price != null || asset.realized_pl !== 0
                          ? formatPercent(stats.totalPlPct)
                          : <span className="text-slate-600">—</span>}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="inline-flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => { setEditAsset(asset); setFormOpen(true) }}
                            className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-700 transition-colors"
                            title="Edit"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteTarget(asset)}
                            className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                          <ChevronRight className="h-3.5 w-3.5 text-slate-600 ml-1" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <AssetFormDialog
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditAsset(null) }}
        asset={editAsset}
        onSave={handleSave}
      />

      {deleteTarget && (
        <DeleteConfirmDialog
          open={!!deleteTarget}
          assetName={deleteTarget.name}
          onClose={() => setDeleteTarget(null)}
          onConfirm={handleDelete}
          isDeleting={isDeleting}
        />
      )}
    </AppShell>
  )
}
