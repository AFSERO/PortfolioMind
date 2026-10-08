import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Pencil,
  Trash2,
  RefreshCw,
  Plus,
  AlertTriangle,
  Sparkles,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import AppShell from '@/components/layout/AppShell'
import AssetTypeBadge from '@/components/assets/AssetTypeBadge'
import AssetFormDialog from '@/components/assets/AssetFormDialog'
import TransactionDialog from '@/components/assets/TransactionDialog'
import DeleteConfirmDialog from '@/components/assets/DeleteConfirmDialog'
import { useAssetDetail } from '@/hooks/useAssets'
import { useTransactions } from '@/hooks/useTransactions'
import { useForexRates, convertCurrency } from '@/hooks/useForexRates'
import {
  assetService,
  type AssetCreatePayload,
  type AssetUpdatePayload,
} from '@/services/assetService'
import { extractErrorMessage } from '@/services/api'
import { formatCurrency, formatPercent, plColorClass } from '@/utils/format'
import { typeColor } from '@/utils/assetTypes'
import TradingViewChart from '@/components/assets/TradingViewChart'
import VerdictCard from '@/components/assets/VerdictCard'
import TechnicalPlanZones from '@/components/assets/TechnicalPlanZones'
import IntelligenceTimeline from '@/components/assets/IntelligenceTimeline'
import ContextualAIActions from '@/components/assets/ContextualAIActions'
import { useInstrumentReviews, useTechnicalPlan } from '@/hooks/useIntelligence'
import type { PriceHistory, Transaction } from '@/types'
import { cn } from '@/utils/cn'

const TRADINGVIEW_TYPES = new Set(['STOCK', 'CRYPTO', 'FOREX', 'PRECIOUS_METALS'])

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string
  value: string
  sub?: string
  valueClass?: string
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={cn('text-lg font-semibold text-slate-100', valueClass)}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

function ChartTooltip({
  active,
  payload,
  currency,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  currency: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/95 px-3 py-2 shadow-xl text-xs">
      <p className="text-slate-300">{formatCurrency(payload[0].value, currency)}</p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { asset, isLoading, error, refetch } = useAssetDetail(id!)
  const { rates } = useForexRates()
  const {
    transactions,
    isLoading: txLoading,
    create: createTx,
    update: updateTx,
    remove: removeTx,
  } = useTransactions(id)

  const instrumentId = asset?.instrument_id ?? asset?.instrument?.id
  const { reviews, isLoading: reviewsLoading } = useInstrumentReviews(instrumentId)
  const { plan: technicalPlan } = useTechnicalPlan(instrumentId)

  const [priceHistory, setPriceHistory] = useState<PriceHistory[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)

  const [editAssetOpen, setEditAssetOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [txDialogOpen, setTxDialogOpen] = useState(false)
  const [editTx, setEditTx] = useState<Transaction | null>(null)
  const [deleteTx, setDeleteTx] = useState<Transaction | null>(null)
  const [researching, setResearching] = useState(false)

  const handleDeepResearch = async () => {
    if (!id || !asset || researching) return
    setResearching(true)
    toast.info(`Deep Research başlatılıyor: ${asset.symbol || asset.name}...`)
    try {
      const res = await assetService.runDeepResearch(id)
      const summary = res?.summary
      const newRec = summary?.recommendation || 'Tamamlandı'
      toast.success(`Deep Research tamamlandı (${asset.symbol || asset.name}): ${newRec}`)
      await refetch()
    } catch (err: unknown) {
      toast.error(extractErrorMessage(err, 'Deep Research başarısız oldu'))
    } finally {
      setResearching(false)
    }
  }

  useEffect(() => {
    if (!id) return
    setHistoryLoading(true)
    assetService.getPriceHistory(id, 90)
      .then((data) => setPriceHistory(data))
      .catch(() => setPriceHistory([]))
      .finally(() => setHistoryLoading(false))
  }, [id])

  const handleSaveAsset = async (
    payload: AssetCreatePayload | AssetUpdatePayload,
    assetId?: string,
  ) => {
    if (!assetId) return
    await assetService.update(assetId, payload as AssetUpdatePayload)
    await refetch()
  }

  const handleDeleteAsset = async () => {
    if (!asset) return
    setIsDeleting(true)
    try {
      await assetService.delete(asset.id)
      toast.success(`${asset.name} deleted`)
      navigate('/assets')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
      setIsDeleting(false)
    }
  }

  const wrappedCreateTx = async (body: Parameters<typeof createTx>[0]) => {
    const result = await createTx(body)
    await refetch()
    return result
  }

  const wrappedUpdateTx = async (
    txId: string,
    body: Parameters<typeof updateTx>[1],
  ) => {
    const result = await updateTx(txId, body)
    await refetch()
    return result
  }

  const handleDeleteTx = async () => {
    if (!deleteTx) return
    try {
      await removeTx(deleteTx.id)
      await refetch()
      toast.success('Transaction deleted')
      setDeleteTx(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    }
  }

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <AppShell>
        <div className="px-8 py-6 space-y-4">
          <Skeleton className="h-8 w-48 bg-slate-800" />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-24 bg-slate-800 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 bg-slate-800 rounded-xl" />
        </div>
      </AppShell>
    )
  }

  if (error || !asset) {
    return (
      <AppShell>
        <div className="px-8 py-6">
          <button
            onClick={() => navigate('/assets')}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Assets
          </button>
          <p className="text-slate-400">{error ?? 'Asset not found'}</p>
        </div>
      </AppShell>
    )
  }

  // ── Computed values ─────────────────────────────────────────────────────────
  const displayCurrency =
    asset.avg_cost_currency ?? asset.current_price_currency ?? 'TRY'
  const rawCurrentPrice = asset.current_price
  const rawCurrentCurrency = asset.current_price_currency ?? displayCurrency
  const currentPriceConverted =
    rawCurrentPrice != null
      ? convertCurrency(rawCurrentPrice, rawCurrentCurrency, displayCurrency, rates)
      : null
  const valuationUnavailable = rawCurrentPrice != null && currentPriceConverted == null

  const totalCost = asset.total_cost
  const totalValue =
    valuationUnavailable
      ? null
      : currentPriceConverted != null
      ? currentPriceConverted * asset.total_quantity
      : totalCost
  const unrealizedPl = valuationUnavailable || totalCost == null
    ? null
    : currentPriceConverted != null && totalValue != null
      ? totalValue - totalCost
      : 0
  const realizedPl = asset.realized_pl
  const totalPl = unrealizedPl == null || realizedPl == null ? null : unrealizedPl + realizedPl
  const totalPlPct = totalPl == null || totalCost == null ? null : totalCost > 0 ? (totalPl / totalCost) * 100 : 0
  const color = typeColor(asset.asset_type)

  const chartData = priceHistory.map((h) => ({
    date: new Date(h.recorded_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' }),
    price: h.price,
  }))

  return (
    <AppShell>
      <div className="px-8 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/assets')}
              className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Assets
            </button>
            <div className="h-4 w-px bg-slate-700" />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-semibold text-slate-100">{asset.name}</h1>
                {asset.symbol && (
                  <span className="text-sm text-slate-500 font-mono">{asset.symbol}</span>
                )}
                <AssetTypeBadge type={asset.asset_type} size="sm" />
                {asset.instrument?.exchange && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-mono">
                    {asset.instrument.exchange}
                  </span>
                )}
              </div>
              {asset.is_manual_price && (
                <p className="text-xs text-slate-500 mt-0.5">Manual price</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleDeepResearch}
              disabled={researching}
              className="bg-teal-600 hover:bg-teal-700 text-white gap-1.5"
            >
              {researching ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Researching...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Deep Research</span>
                </>
              )}
            </Button>
            <Button
              size="sm"
              onClick={() => { setEditTx(null); setTxDialogOpen(true) }}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
            >
              <Plus className="h-4 w-4" />
              Add Transaction
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditAssetOpen(true)}
              className="border-slate-700 text-slate-300 hover:bg-slate-800 gap-1.5"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteOpen(true)}
              className="border-red-900/50 text-red-400 hover:bg-red-900/20 gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </Button>
          </div>
        </div>

        {/* Mixed-currency banner */}
        {asset.has_mixed_currencies && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-700/40 bg-amber-900/10 px-4 py-2.5 text-sm">
            <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-amber-200">Mixed transaction currencies detected.</p>
              <p className="text-amber-200/70 text-xs">
                Cost basis is computed in the first BUY's currency ({displayCurrency}); other amounts
                are not FX-converted. Treat aggregated P/L as approximate.
              </p>
            </div>
          </div>
        )}

        {/* Investment Intelligence: The Verdict */}
        <VerdictCard
          state={asset.instrument?.intelligence_state}
          assetId={asset.id}
          assetType={asset.asset_type}
          assetName={asset.symbol || asset.name}
          onRefresh={refetch}
        />

        {/* Investment Intelligence: Technical Strategy Zones */}
        <TechnicalPlanZones
          plan={technicalPlan}
          currentPrice={currentPriceConverted}
          currency={displayCurrency}
        />

        {/* Stats cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            label="Current Value"
            value={totalValue == null ? 'Unavailable' : formatCurrency(totalValue, displayCurrency)}
            sub={`${asset.total_quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })} units`}
          />
          <StatCard
            label="Total Cost"
            value={formatCurrency(totalCost, displayCurrency)}
            sub={
              asset.avg_cost != null
                ? `avg ${formatCurrency(asset.avg_cost, displayCurrency)}`
                : undefined
            }
          />
          <StatCard
            label="Unrealized P/L"
            value={
              unrealizedPl != null
                ? formatCurrency(unrealizedPl, displayCurrency)
                : valuationUnavailable ? 'Unavailable' : '—'
            }
            sub={totalPlPct != null ? formatPercent(totalPlPct) : undefined}
            valueClass={
              unrealizedPl != null ? plColorClass(unrealizedPl) : undefined
            }
          />
          <StatCard
            label="Realized P/L"
            value={formatCurrency(realizedPl, displayCurrency)}
            sub={realizedPl !== 0 ? 'from SELL transactions' : undefined}
            valueClass={plColorClass(realizedPl)}
          />
          <StatCard
            label="Current Price"
            value={
              currentPriceConverted != null
                ? formatCurrency(currentPriceConverted, displayCurrency)
                : '—'
            }
            sub={
              rawCurrentPrice != null && rawCurrentCurrency !== displayCurrency
                ? `(${formatCurrency(rawCurrentPrice, rawCurrentCurrency)} original)`
                : undefined
            }
          />
        </div>

        {/* Price chart */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
            Price Chart
          </h3>

          {TRADINGVIEW_TYPES.has(asset.asset_type) && asset.symbol ? (
            <TradingViewChart symbol={asset.symbol} assetType={asset.asset_type} />
          ) : (
            <>
              <div className="flex items-center justify-between mb-4 -mt-4">
                <span className="text-xs text-slate-600">Recorded price history</span>
                {historyLoading && (
                  <RefreshCw className="h-3.5 w-3.5 text-slate-600 animate-spin" />
                )}
              </div>

              {historyLoading ? (
                <Skeleton className="h-48 w-full bg-slate-800 rounded-lg" />
              ) : chartData.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 gap-2 text-center">
                  <p className="text-slate-500 text-sm">No price history yet</p>
                  <p className="text-slate-600 text-xs">
                    History is recorded each time prices are refreshed
                  </p>
                </div>
              ) : (
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        axisLine={false}
                        tickLine={false}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => v.toLocaleString()}
                        width={60}
                      />
                      <Tooltip
                        content={<ChartTooltip currency={displayCurrency} />}
                        cursor={{ stroke: '#334155', strokeWidth: 1 }}
                      />
                      <Area
                        type="monotone"
                        dataKey="price"
                        stroke={color}
                        strokeWidth={2}
                        fill="url(#priceGradient)"
                        dot={false}
                        activeDot={{ r: 4, fill: color, stroke: '#0f172a', strokeWidth: 2 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>

        {/* Intelligence Timeline & Contextual Actions */}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <IntelligenceTimeline reviews={reviews} isLoading={reviewsLoading} />
          </div>
          <div>
            <ContextualAIActions asset={asset} />
          </div>
        </div>

        {/* Transaction History */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
              Transaction History
            </h3>
            <Button
              size="sm"
              onClick={() => { setEditTx(null); setTxDialogOpen(true) }}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 h-7 px-2.5 text-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
          </div>

          {txLoading ? (
            <Skeleton className="h-24 w-full bg-slate-800 rounded-lg" />
          ) : transactions.length === 0 ? (
            <p className="text-slate-500 text-sm py-4 text-center">No transactions yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Type</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Quantity</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Price</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Total</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Notes</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={tx.id} className="border-b border-slate-800/60 hover:bg-slate-800/40 group">
                      <td className="px-3 py-2 text-slate-300">{tx.transaction_date}</td>
                      <td className="px-3 py-2">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-xs font-medium',
                          tx.transaction_type === 'BUY'
                            ? 'bg-emerald-600/20 text-emerald-400'
                            : 'bg-red-600/20 text-red-400',
                        )}>
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-300">
                        {tx.quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-300">
                        {formatCurrency(tx.price_per_unit, tx.transaction_currency)}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-200">
                        {formatCurrency(tx.total_amount, tx.transaction_currency)}
                      </td>
                      <td className="px-3 py-2 text-slate-400 text-xs max-w-[12rem] truncate">
                        {tx.notes || '—'}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="inline-flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => { setEditTx(tx); setTxDialogOpen(true) }}
                            className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-700"
                            title="Edit"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteTx(tx)}
                            className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-red-900/20"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Asset details */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-4">
            Details
          </h3>
          <dl className="grid grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-4 text-sm">
            <div>
              <dt className="text-slate-500 mb-0.5">Type</dt>
              <dd><AssetTypeBadge type={asset.asset_type} size="sm" /></dd>
            </div>
            {asset.symbol && (
              <div>
                <dt className="text-slate-500 mb-0.5">Symbol</dt>
                <dd className="text-slate-200 font-mono">{asset.symbol}</dd>
              </div>
            )}
            <div>
              <dt className="text-slate-500 mb-0.5">Total Quantity</dt>
              <dd className="text-slate-200">
                {asset.total_quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500 mb-0.5">Avg Cost</dt>
              <dd className="text-slate-200">
                {asset.avg_cost != null
                  ? formatCurrency(asset.avg_cost, displayCurrency)
                  : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500 mb-0.5">Realized P/L</dt>
              <dd className={cn('text-slate-200', plColorClass(realizedPl))}>
                {formatCurrency(realizedPl, displayCurrency)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500 mb-0.5">Mixed Currencies</dt>
              <dd className="text-slate-200">{asset.has_mixed_currencies ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt className="text-slate-500 mb-0.5">Price Source</dt>
              <dd className="text-slate-200">
                {asset.is_manual_price ? 'Manual' : 'Automatic'}
              </dd>
            </div>
            {asset.notes && (
              <div className="col-span-2 md:col-span-3">
                <dt className="text-slate-500 mb-0.5">Notes</dt>
                <dd className="text-slate-200">{asset.notes}</dd>
              </div>
            )}
            <div>
              <dt className="text-slate-500 mb-0.5">Added</dt>
              <dd className="text-slate-200">
                {new Date(asset.created_at).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500 mb-0.5">Last Updated</dt>
              <dd className="text-slate-200">
                {new Date(asset.updated_at).toLocaleDateString()}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Dialogs */}
      <AssetFormDialog
        open={editAssetOpen}
        onClose={() => setEditAssetOpen(false)}
        asset={asset}
        onSave={handleSaveAsset}
      />

      <TransactionDialog
        open={txDialogOpen}
        onClose={() => { setTxDialogOpen(false); setEditTx(null) }}
        asset={asset}
        transaction={editTx}
        onCreate={wrappedCreateTx}
        onUpdate={wrappedUpdateTx}
      />

      <DeleteConfirmDialog
        open={deleteOpen}
        assetName={asset.name}
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDeleteAsset}
        isDeleting={isDeleting}
      />

      {deleteTx && (
        <DeleteConfirmDialog
          open={!!deleteTx}
          assetName={`${deleteTx.transaction_type} ${deleteTx.quantity} on ${deleteTx.transaction_date}`}
          onClose={() => setDeleteTx(null)}
          onConfirm={handleDeleteTx}
          isDeleting={false}
        />
      )}
    </AppShell>
  )
}

