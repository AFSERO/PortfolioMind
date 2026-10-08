import { useEffect, useMemo, useState, useCallback } from 'react'
import { useForm, Controller, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2, AlertCircle } from 'lucide-react'
import type { Asset, AssetType, CashAccount } from '@/types'
import type {
  AssetCreatePayload,
  AssetUpdatePayload,
  InitialTransactionPayload,
} from '@/services/assetService'
import { ASSET_TYPE_META } from '@/utils/assetTypes'
import { formatCurrency } from '@/utils/format'
import { cn } from '@/utils/cn'
import SymbolCombobox from './SymbolCombobox'
import { cashService } from '@/services/cashService'
import { assetResolverService, type ResolvedAsset } from '@/services/assetResolverService'

// ── Asset type categorisation ────────────────────────────────────────────────

const SYMBOL_TYPES: AssetType[] = ['STOCK', 'FOREX', 'CRYPTO', 'PRECIOUS_METALS', 'FUND']
const MANUAL_PRICE_TYPES: AssetType[] = ['REAL_ESTATE', 'CUSTOM']
const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP'] as const

// ── Precious metals configuration ────────────────────────────────────────────

type MetalType = 'GOLD' | 'SILVER' | 'PLATINUM' | 'PALLADIUM'

const METAL_TYPES: Array<{ value: MetalType; label: string }> = [
  { value: 'GOLD',      label: 'Altın / Gold' },
  { value: 'SILVER',    label: 'Gümüş / Silver' },
  { value: 'PLATINUM',  label: 'Platin / Platinum' },
  { value: 'PALLADIUM', label: 'Paladyum / Palladium' },
]

const METAL_SUBTYPES: Record<MetalType, Array<{ value: string; label: string }>> = {
  GOLD: [
    { value: 'GR',   label: 'Gram (24 karat, saf / pure)' },
    { value: 'QTR',  label: 'Çeyrek Altın (Quarter, 22 karat)' },
    { value: 'HALF', label: 'Yarım Altın (Half, 22 karat)' },
    { value: 'FULL', label: 'Tam Altın (Full, 22 karat)' },
    { value: 'XAU',  label: 'Ons (Troy Ounce)' },
  ],
  SILVER: [
    { value: 'SILVER_GR', label: 'Gram' },
    { value: 'XAG',       label: 'Ons (Troy Ounce)' },
  ],
  PLATINUM:  [{ value: 'XPT', label: 'Ons (Troy Ounce)' }],
  PALLADIUM: [{ value: 'XPD', label: 'Ons (Troy Ounce)' }],
}

const DEFAULT_SUBTYPE: Record<MetalType, string> = {
  GOLD:      'GR',
  SILVER:    'SILVER_GR',
  PLATINUM:  'XPT',
  PALLADIUM: 'XPD',
}

function metalTypeFromSymbol(symbol: string | null | undefined): MetalType {
  if (!symbol) return 'GOLD'
  if (['GR', 'QTR', 'HALF', 'FULL', 'XAU'].includes(symbol)) return 'GOLD'
  if (['XAG', 'SILVER_GR'].includes(symbol)) return 'SILVER'
  if (symbol === 'XPT') return 'PLATINUM'
  if (symbol === 'XPD') return 'PALLADIUM'
  return 'GOLD'
}

// ── Schemas ──────────────────────────────────────────────────────────────────

const numberFromInput = z.preprocess(
  (v) => (v === '' || v == null ? undefined : Number(v)),
  z.number().positive('Must be > 0'),
)

const optionalNumberFromInput = z.preprocess(
  (v) => (v === '' || v == null ? null : Number(v)),
  z.number().nonnegative().nullable().optional(),
)

const baseAssetFields = {
  asset_type: z.enum([
    'STOCK', 'FOREX', 'PRECIOUS_METALS', 'CRYPTO', 'FUND', 'REAL_ESTATE', 'CUSTOM',
  ]),
  symbol: z.string().optional(),
  name: z.string().min(1, 'Name is required'),
  notes: z.string().optional(),
  current_price: optionalNumberFromInput,
  current_price_currency: z.string().optional().nullable(),
}

const createSchema = z
  .object({
    ...baseAssetFields,
    input_mode: z.enum(['quantity', 'amount']),
    quantity: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0').optional(),
    ),
    total_amount: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0').optional(),
    ),
    price_per_unit: numberFromInput,
    transaction_currency: z.string().min(1),
    transaction_date: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.input_mode === 'quantity' && val.quantity == null) {
      ctx.addIssue({ code: 'custom', path: ['quantity'], message: 'Required' })
    }
    if (val.input_mode === 'amount' && val.total_amount == null) {
      ctx.addIssue({ code: 'custom', path: ['total_amount'], message: 'Required' })
    }
  })

const editSchema = z.object({ ...baseAssetFields })

type CreateValues = z.infer<typeof createSchema>
type EditValues   = z.infer<typeof editSchema>
type FormValues   = CreateValues & Partial<EditValues>

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean
  onClose: () => void
  asset?: Asset | null
  onSave: (
    payload: AssetCreatePayload | AssetUpdatePayload,
    assetId?: string,
  ) => Promise<void>
}

// ── Component ────────────────────────────────────────────────────────────────

export default function AssetFormDialog({ open, onClose, asset, onSave }: Props) {
  const isEdit = !!asset

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver((isEdit ? editSchema : createSchema) as any) as any,
    defaultValues: {
      asset_type: 'STOCK',
      input_mode: 'quantity',
      transaction_currency: 'TRY',
      transaction_date: new Date().toISOString().split('T')[0],
      current_price_currency: 'TRY',
    },
  })

  const assetType = watch('asset_type') as AssetType
  const symbol = watch('symbol')
  const inputMode = watch('input_mode') as 'quantity' | 'amount'
  const quantity = watch('quantity') as number | undefined
  const totalAmount = watch('total_amount') as number | undefined
  const pricePerUnit = watch('price_per_unit') as number | undefined
  const txCurrency = (watch('transaction_currency') as string) || 'TRY'

  const needsSymbol = SYMBOL_TYPES.includes(assetType)
  const isManualPrice = MANUAL_PRICE_TYPES.includes(assetType)
  const isPreciousMetals = assetType === 'PRECIOUS_METALS'

  const [metalType, setMetalType] = useState<MetalType>('GOLD')
  const [affectsCash, setAffectsCash] = useState(true)
  const [cashAccounts, setCashAccounts] = useState<CashAccount[]>([])
  const [resolvedAsset, setResolvedAsset] = useState<ResolvedAsset | null>(null)
  const [assetResolving, setAssetResolving] = useState(false)
  const [assetError, setAssetError] = useState<string | null>(null)

  const fetchCashAccounts = useCallback(async () => {
    try {
      const accounts = await cashService.getAccounts()
      setCashAccounts(accounts)
    } catch {
      setCashAccounts([])
    }
  }, [])

  useEffect(() => {
    if (!isEdit && isPreciousMetals) {
      const validSymbols = Object.values(METAL_SUBTYPES).flatMap((s) => s.map((x) => x.value))
      if (!symbol || !validSymbols.includes(symbol)) {
        setValue('symbol', DEFAULT_SUBTYPE[metalType])
      }
    }
  }, [isEdit, isPreciousMetals, symbol, metalType, setValue])

  // Automatically resolve asset metadata and latest market price for market-priced assets
  useEffect(() => {
    if (isEdit || !needsSymbol || !symbol || symbol.trim().length < 2) {
      setResolvedAsset(null)
      setAssetError(null)
      setAssetResolving(false)
      return
    }

    let cancelled = false
    const timeoutId = setTimeout(async () => {
      setAssetResolving(true)
      setAssetError(null)
      try {
        const resolved = await assetResolverService.resolve(assetType, symbol.trim())
        if (!cancelled) {
          setResolvedAsset(resolved)
          setValue('name', resolved.name, { shouldValidate: true })
          setValue('price_per_unit', resolved.latest_price, { shouldValidate: true })
          setValue('transaction_currency', resolved.currency)
          setValue('current_price', resolved.latest_price)
          setValue('current_price_currency', resolved.currency)
        }
      } catch (err) {
        if (!cancelled) {
          setResolvedAsset(null)
          setAssetError(
            err instanceof Error
              ? err.message
              : 'Could not resolve asset price. Please enter manually.'
          )
        }
      } finally {
        if (!cancelled) {
          setAssetResolving(false)
        }
      }
    }, 350)

    return () => {
      cancelled = true
      clearTimeout(timeoutId)
    }
  }, [assetType, symbol, isEdit, needsSymbol, setValue])

  const handleMetalTypeChange = (mt: MetalType) => {
    setMetalType(mt)
    setValue('symbol', DEFAULT_SUBTYPE[mt])
  }

  // Fetch cash accounts when dialog opens (create mode only)
  useEffect(() => {
    if (open && !isEdit) {
      setAffectsCash(true)
      fetchCashAccounts()
    }
  }, [open, isEdit, fetchCashAccounts])

  // Reset form on open / asset change
  useEffect(() => {
    if (!open) return

    setResolvedAsset(null)
    setAssetError(null)
    setAssetResolving(false)

    if (asset) {
      const inferredMetal =
        asset.asset_type === 'PRECIOUS_METALS' ? metalTypeFromSymbol(asset.symbol) : 'GOLD'
      setMetalType(inferredMetal)
      reset({
        asset_type: asset.asset_type,
        symbol: asset.symbol ?? '',
        name: asset.name,
        notes: asset.notes ?? '',
        current_price: asset.current_price ?? null,
        current_price_currency: asset.current_price_currency ?? 'TRY',
        // Create-only fields are unused in edit mode but kept for type compat
        input_mode: 'quantity',
        transaction_currency: 'TRY',
        transaction_date: new Date().toISOString().split('T')[0],
      })
    } else {
      setMetalType('GOLD')
      reset({
        asset_type: 'STOCK',
        symbol: '',
        name: '',
        notes: '',
        current_price: null,
        current_price_currency: 'TRY',
        input_mode: 'quantity',
        quantity: undefined,
        total_amount: undefined,
        price_per_unit: undefined,
        transaction_currency: 'TRY',
        transaction_date: new Date().toISOString().split('T')[0],
      })
    }
  }, [open, asset, reset])

  // Live computed value beneath the dual-input toggle
  const computedPreview = useMemo(() => {
    if (isEdit) return null
    const ppu = Number(pricePerUnit)
    if (!ppu || !isFinite(ppu) || ppu <= 0) return null

    if (inputMode === 'quantity') {
      const q = Number(quantity)
      if (!q || !isFinite(q) || q <= 0) return null
      return `≈ ${formatCurrency(q * ppu, txCurrency)} total`
    }
    const t = Number(totalAmount)
    if (!t || !isFinite(t) || t <= 0) return null
    const q = t / ppu
    return `≈ ${q.toLocaleString(undefined, { maximumFractionDigits: 6 })} units`
  }, [isEdit, inputMode, quantity, totalAmount, pricePerUnit, txCurrency])

  // ── Submit ─────────────────────────────────────────────────────────────────
  const onSubmit: SubmitHandler<FormValues> = async (values) => {
    try {
      if (isEdit && asset) {
        const update: AssetUpdatePayload = {
          name: values.name,
          symbol: values.symbol || undefined,
          notes: values.notes || undefined,
          current_price: isManualPrice ? values.current_price ?? null : undefined,
          current_price_currency: isManualPrice
            ? values.current_price_currency ?? undefined
            : undefined,
        }
        await onSave(update, asset.id)
      } else {
        const initial_transaction: InitialTransactionPayload = {
          transaction_type: 'BUY',
          price_per_unit: Number(values.price_per_unit),
          transaction_currency: values.transaction_currency!,
          affects_cash: affectsCash,
          ...(values.transaction_date ? { transaction_date: values.transaction_date } : {}),
          ...(values.input_mode === 'quantity'
            ? { quantity: Number(values.quantity) }
            : { total_amount: Number(values.total_amount) }),
        }
        const create: AssetCreatePayload = {
          asset_type: values.asset_type,
          symbol: values.symbol || undefined,
          name: values.name,
          notes: values.notes || undefined,
          is_manual_price: isManualPrice,
          current_price: isManualPrice ? values.current_price ?? undefined : undefined,
          current_price_currency: isManualPrice
            ? values.current_price_currency ?? undefined
            : undefined,
          initial_transaction,
        }
        await onSave(create)
      }
      toast.success(isEdit ? 'Asset updated' : 'Asset added')
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save asset')
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  const acquisitionLabel = isManualPrice ? 'Acquisition' : 'Initial Transaction (BUY)'

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto bg-slate-900 border-slate-800 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-100">
            {isEdit ? 'Edit Asset' : 'Add Asset'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Asset Type — locked in edit mode */}
          <div className="space-y-1.5">
            <Label className="text-slate-300">Asset Type</Label>
            <Controller
              name="asset_type"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange} disabled={isEdit}>
                  <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100 disabled:opacity-60">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                    {Object.entries(ASSET_TYPE_META).map(([key, meta]) => (
                      <SelectItem key={key} value={key} className="focus:bg-slate-700">
                        {meta.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {isEdit && (
              <p className="text-xs text-slate-500">Type cannot be changed after creation.</p>
            )}
          </div>

          {/* Symbol combobox (STOCK / FOREX / CRYPTO / FUND) */}
          {needsSymbol && !isPreciousMetals && (
            <div className="space-y-1.5">
              <Label className="text-slate-300">
                {assetType === 'FUND' ? 'Fund Code' : 'Symbol'}
                <span className="ml-1 text-slate-500 font-normal text-xs">
                  {assetType === 'FOREX'  ? '(e.g. USD/TRY)' :
                   assetType === 'STOCK'  ? '(e.g. AAPL, NVDA, THYAO)' :
                   assetType === 'CRYPTO' ? '(e.g. BTC, ETH, SOL)' :
                   assetType === 'FUND'   ? '(e.g. KCV, THF, MAC)' : ''}
                </span>
              </Label>
              <Controller
                name="symbol"
                control={control}
                render={({ field }) => (
                  <SymbolCombobox
                    type={
                      assetType === 'CRYPTO' ? 'crypto' :
                      assetType === 'FOREX'  ? 'forex'  :
                      assetType === 'FUND'   ? 'fund'   :
                      'stock'
                    }
                    value={field.value ?? ''}
                    onChange={field.onChange}
                    onNameSelect={(name) => setValue('name', name)}
                    onAssetSelect={(entry) => {
                      if (entry.currency) {
                        setValue('transaction_currency', entry.currency)
                        setValue('current_price_currency', entry.currency)
                      }
                    }}
                    placeholder={
                      assetType === 'FOREX'  ? 'Search pair… (e.g. USD/TRY)' :
                      assetType === 'STOCK'  ? 'Search ticker or name… (e.g. THYAO, NVDA, Apple)' :
                      assetType === 'CRYPTO' ? 'Search coin or name… (e.g. BTC, Bitcoin, ETH)' :
                      assetType === 'FUND'   ? 'Search fund code or name… (e.g. KCV, THF)' : ''
                    }
                  />
                )}
              />
              <div className="pt-0.5">
                {assetResolving && (
                  <p className="text-xs text-slate-400 flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 text-emerald-400 animate-spin" />
                    Resolving market price & details…
                  </p>
                )}
                {resolvedAsset && !assetResolving && (
                  <div className="rounded-md border border-emerald-800/40 bg-emerald-950/30 px-2.5 py-1.5 text-xs text-emerald-300 flex items-center justify-between">
                    <div className="flex items-center gap-1.5 truncate mr-2">
                      <span className="truncate font-medium">{resolvedAsset.name}</span>
                      {resolvedAsset.market && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-900/60 text-emerald-300 border border-emerald-700/50 font-sans">
                          {resolvedAsset.market}
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-emerald-200 shrink-0 font-medium">
                      {resolvedAsset.currency === 'TRY' ? '₺' : resolvedAsset.currency === 'USD' ? '$' : `${resolvedAsset.currency} `}
                      {resolvedAsset.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                      {resolvedAsset.price_date && (
                        <span className="ml-1 text-[11px] text-emerald-400 font-normal">
                          ({resolvedAsset.price_date})
                        </span>
                      )}
                    </span>
                  </div>
                )}
                {assetError && !assetResolving && (
                  <p className="text-xs text-amber-400 flex items-center gap-1.5">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    {assetError}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Precious metals selectors */}
          {isPreciousMetals && (
            <>
              <div className="space-y-1.5">
                <Label className="text-slate-300">Metal Type</Label>
                <Select
                  value={metalType}
                  onValueChange={(v) => handleMetalTypeChange(v as MetalType)}
                  disabled={isEdit}
                >
                  <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100 disabled:opacity-60">
                    <SelectValue placeholder="Select metal" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                    {METAL_TYPES.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value} className="focus:bg-slate-700">
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-slate-300">
                  Sub-type
                  <span className="ml-1 text-slate-500 font-normal text-xs">
                    (determines unit price fetched)
                  </span>
                </Label>
                <Controller
                  name="symbol"
                  control={control}
                  render={({ field }) => (
                    <Select
                      value={field.value ?? DEFAULT_SUBTYPE[metalType]}
                      onValueChange={field.onChange}
                      disabled={isEdit}
                    >
                      <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100 disabled:opacity-60">
                        <SelectValue placeholder="Select sub-type" />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                        {METAL_SUBTYPES[metalType].map((opt) => (
                          <SelectItem key={opt.value} value={opt.value} className="focus:bg-slate-700">
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <div className="pt-0.5">
                  {assetResolving && (
                    <p className="text-xs text-slate-400 flex items-center gap-1.5">
                      <Loader2 className="h-3.5 w-3.5 text-emerald-400 animate-spin" />
                      Resolving market price…
                    </p>
                  )}
                  {resolvedAsset && !assetResolving && (
                    <div className="rounded-md border border-emerald-800/40 bg-emerald-950/30 px-2.5 py-1.5 text-xs text-emerald-300 flex items-center justify-between">
                      <span className="truncate mr-2 font-medium">{resolvedAsset.name}</span>
                      <span className="font-mono text-emerald-200 shrink-0 font-medium">
                        ${resolvedAsset.latest_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                        {resolvedAsset.price_date && (
                          <span className="ml-1 text-[11px] text-emerald-400 font-normal">
                            ({resolvedAsset.price_date})
                          </span>
                        )}
                      </span>
                    </div>
                  )}
                  {assetError && !assetResolving && (
                    <p className="text-xs text-amber-400 flex items-center gap-1.5">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      {assetError}
                    </p>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Name */}
          <div className="space-y-1.5">
            <Label className="text-slate-300">Name</Label>
            <Input
              {...register('name')}
              placeholder="e.g. Apple Inc."
              className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
            />
            {errors.name && (
              <p className="text-xs text-red-400">{errors.name.message as string}</p>
            )}
          </div>

          {/* ── Initial Transaction (Add mode only) ───────────────────────── */}
          {!isEdit && (
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-slate-300 text-sm">{acquisitionLabel}</Label>
                {/* Input mode toggle */}
                <Controller
                  name="input_mode"
                  control={control}
                  render={({ field }) => (
                    <div className="inline-flex rounded-md border border-slate-700 bg-slate-800 p-0.5 text-xs">
                      <button
                        type="button"
                        onClick={() => field.onChange('quantity')}
                        className={cn(
                          'px-2 py-1 rounded',
                          field.value === 'quantity'
                            ? 'bg-emerald-600/30 text-emerald-300'
                            : 'text-slate-400 hover:text-slate-200',
                        )}
                      >
                        Quantity
                      </button>
                      <button
                        type="button"
                        onClick={() => field.onChange('amount')}
                        className={cn(
                          'px-2 py-1 rounded',
                          field.value === 'amount'
                            ? 'bg-emerald-600/30 text-emerald-300'
                            : 'text-slate-400 hover:text-slate-200',
                        )}
                      >
                        Total Amount
                      </button>
                    </div>
                  )}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {inputMode === 'quantity' ? (
                  <div className="space-y-1.5">
                    <Label className="text-slate-300 text-xs">Quantity</Label>
                    <Input
                      {...register('quantity')}
                      type="number"
                      step="any"
                      placeholder="1"
                      className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
                    />
                    {errors.quantity && (
                      <p className="text-xs text-red-400">{errors.quantity.message as string}</p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label className="text-slate-300 text-xs">Total Amount</Label>
                    <Input
                      {...register('total_amount')}
                      type="number"
                      step="any"
                      placeholder="0.00"
                      className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
                    />
                    {errors.total_amount && (
                      <p className="text-xs text-red-400">{errors.total_amount.message as string}</p>
                    )}
                  </div>
                )}

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs">Price per Unit</Label>
                  <Input
                    {...register('price_per_unit')}
                    type="number"
                    step="any"
                    placeholder="0.00"
                    className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
                  />
                  {errors.price_per_unit && (
                    <p className="text-xs text-red-400">{errors.price_per_unit.message as string}</p>
                  )}
                </div>
              </div>

              {computedPreview && (
                <p className="text-xs text-slate-500">{computedPreview}</p>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs">Currency</Label>
                  <Controller
                    name="transaction_currency"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                          {CURRENCIES.map((c) => (
                            <SelectItem key={c} value={c} className="focus:bg-slate-700">
                              {c}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-300 text-xs">Date <span className="text-slate-500 font-normal">(optional)</span></Label>
                  <Input
                    {...register('transaction_date')}
                    type="date"
                    className="bg-slate-800 border-slate-700 text-slate-100 [color-scheme:dark]"
                  />
                  <p className="text-[11px] text-slate-500">Leave empty if unsure — today's date will be used.</p>
                </div>
              </div>
            </div>
          )}

          {/* Affects cash account — create mode only */}
          {!isEdit && (() => {
            const cur = txCurrency
            const cashAcct = cashAccounts.find((a) => a.currency === cur)
            return (
              <label className="flex items-start gap-3 cursor-pointer select-none rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={affectsCash}
                  onChange={(e) => setAffectsCash(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 accent-emerald-500 cursor-pointer"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 font-medium">Deduct from cash account</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {cur} balance:{' '}
                    <span className={cn('font-medium', cashAcct ? (cashAcct.balance >= 0 ? 'text-slate-300' : 'text-loss') : 'text-slate-600')}>
                      {cashAcct ? formatCurrency(cashAcct.balance, cur) : 'No account'}
                    </span>
                  </p>
                </div>
              </label>
            )
          })()}

          {/* Manual current price (FUND / REAL_ESTATE / CUSTOM) — both modes */}
          {isManualPrice && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-slate-300">Current Value</Label>
                <Input
                  {...register('current_price')}
                  type="number"
                  step="any"
                  placeholder="0.00"
                  className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-slate-300">Value Currency</Label>
                <Controller
                  name="current_price_currency"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value ?? 'TRY'} onValueChange={field.onChange}>
                      <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                        {CURRENCIES.map((c) => (
                          <SelectItem key={c} value={c} className="focus:bg-slate-700">
                            {c}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-slate-300">
              Notes <span className="text-slate-500 font-normal">(optional)</span>
            </Label>
            <Textarea
              {...register('notes')}
              placeholder="Any notes about this asset..."
              rows={2}
              className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500 resize-none"
            />
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isSubmitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Asset'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
