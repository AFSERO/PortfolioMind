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
import type { Asset, CashAccount, Transaction, TransactionType } from '@/types'
import type {
  TransactionCreatePayload,
  TransactionUpdatePayload,
} from '@/services/transactionService'
import { formatCurrency } from '@/utils/format'
import { cn } from '@/utils/cn'
import { cashService } from '@/services/cashService'

const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP'] as const

// ── Schema ───────────────────────────────────────────────────────────────────

const schema = z
  .object({
    transaction_type: z.enum(['BUY', 'SELL']),
    input_mode: z.enum(['quantity', 'amount']),
    quantity: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0').optional(),
    ),
    total_amount: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0').optional(),
    ),
    price_per_unit: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0'),
    ),
    transaction_currency: z.string().min(1),
    transaction_date: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.input_mode === 'quantity' && val.quantity == null) {
      ctx.addIssue({ code: 'custom', path: ['quantity'], message: 'Required' })
    }
    if (val.input_mode === 'amount' && val.total_amount == null) {
      ctx.addIssue({ code: 'custom', path: ['total_amount'], message: 'Required' })
    }
  })

type FormValues = z.infer<typeof schema>

// ── Props ────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean
  onClose: () => void
  asset: Asset
  transaction?: Transaction | null
  onCreate: (body: TransactionCreatePayload) => Promise<unknown>
  onUpdate: (txId: string, body: TransactionUpdatePayload) => Promise<unknown>
}

// ── Component ────────────────────────────────────────────────────────────────

export default function TransactionDialog({
  open,
  onClose,
  asset,
  transaction,
  onCreate,
  onUpdate,
}: Props) {
  const isEdit = !!transaction
  const [affectsCash, setAffectsCash] = useState(true)
  const [cashAccounts, setCashAccounts] = useState<CashAccount[]>([])

  const fetchCashAccounts = useCallback(async () => {
    try { setCashAccounts(await cashService.getAccounts()) } catch { setCashAccounts([]) }
  }, [])

  useEffect(() => {
    if (open) {
      setAffectsCash(transaction?.affects_cash ?? true)
      fetchCashAccounts()
    }
  }, [open, transaction, fetchCashAccounts])

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(schema as any) as any,
    defaultValues: {
      transaction_type: 'BUY',
      input_mode: 'quantity',
      transaction_currency: asset.avg_cost_currency ?? 'TRY',
      transaction_date: new Date().toISOString().split('T')[0],
    },
  })

  const txType = watch('transaction_type') as TransactionType
  const inputMode = watch('input_mode') as 'quantity' | 'amount'
  const quantity = watch('quantity') as number | undefined
  const totalAmount = watch('total_amount') as number | undefined
  const pricePerUnit = watch('price_per_unit') as number | undefined
  const txCurrency = (watch('transaction_currency') as string) || 'TRY'

  // Reset on open / transaction change
  useEffect(() => {
    if (!open) return
    if (transaction) {
      reset({
        transaction_type: transaction.transaction_type,
        input_mode: 'quantity',
        quantity: transaction.quantity,
        total_amount: undefined,
        price_per_unit: transaction.price_per_unit,
        transaction_currency: transaction.transaction_currency,
        transaction_date: transaction.transaction_date,
        notes: transaction.notes ?? '',
      })
    } else {
      reset({
        transaction_type: 'BUY',
        input_mode: 'quantity',
        quantity: undefined,
        total_amount: undefined,
        price_per_unit: undefined,
        transaction_currency: asset.avg_cost_currency ?? 'TRY',
        transaction_date: new Date().toISOString().split('T')[0],
        notes: '',
      })
    }
  }, [open, transaction, asset.avg_cost_currency, reset])

  // Effective qty preview (used for SELL guard + computed line)
  const effectiveQty = useMemo(() => {
    const ppu = Number(pricePerUnit)
    if (inputMode === 'quantity') {
      const q = Number(quantity)
      return q > 0 && isFinite(q) ? q : null
    }
    if (!ppu || !isFinite(ppu) || ppu <= 0) return null
    const t = Number(totalAmount)
    if (!t || !isFinite(t) || t <= 0) return null
    return t / ppu
  }, [inputMode, quantity, totalAmount, pricePerUnit])

  const computedPreview = useMemo(() => {
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
  }, [inputMode, quantity, totalAmount, pricePerUnit, txCurrency])

  // Client-side SELL guard. For an edit, exclude the current transaction's contribution.
  const sellExceedsHoldings = useMemo(() => {
    if (txType !== 'SELL' || effectiveQty == null) return false
    const heldExcludingThis =
      isEdit && transaction && transaction.transaction_type === 'SELL'
        ? asset.total_quantity + transaction.quantity
        : isEdit && transaction && transaction.transaction_type === 'BUY'
          ? asset.total_quantity - transaction.quantity
          : asset.total_quantity
    return effectiveQty > heldExcludingThis + 1e-9
  }, [txType, effectiveQty, isEdit, transaction, asset.total_quantity])

  const onSubmit: SubmitHandler<FormValues> = async (values) => {
    if (sellExceedsHoldings) {
      toast.error('SELL quantity exceeds current holdings')
      return
    }
    try {
      const payload: TransactionCreatePayload = {
        transaction_type: values.transaction_type,
        price_per_unit: Number(values.price_per_unit),
        transaction_currency: values.transaction_currency,
        affects_cash: transaction?.affects_cash ?? affectsCash,
        ...(values.transaction_date ? { transaction_date: values.transaction_date } : {}),
        notes: values.notes || undefined,
        ...(values.input_mode === 'quantity'
          ? { quantity: Number(values.quantity) }
          : { total_amount: Number(values.total_amount) }),
      }
      if (isEdit && transaction) {
        await onUpdate(transaction.id, payload)
        toast.success('Transaction updated')
      } else {
        await onCreate(payload)
        toast.success('Transaction added')
      }
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save transaction')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto bg-slate-900 border-slate-800 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-100">
            {isEdit ? 'Edit Transaction' : 'Add Transaction'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-2">
          {/* Type toggle */}
          <div className="space-y-1.5">
            <Label className="text-slate-300">Type</Label>
            <Controller
              name="transaction_type"
              control={control}
              render={({ field }) => (
                <div className="inline-flex w-full rounded-md border border-slate-700 bg-slate-800 p-0.5">
                  {(['BUY', 'SELL'] as const).map((t) => (
                    <button
                      type="button"
                      key={t}
                      onClick={() => field.onChange(t)}
                      className={cn(
                        'flex-1 px-3 py-1.5 rounded text-sm font-medium transition-colors',
                        field.value === t
                          ? t === 'BUY'
                            ? 'bg-emerald-600/30 text-emerald-300'
                            : 'bg-red-600/30 text-red-300'
                          : 'text-slate-400 hover:text-slate-200',
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
            />
          </div>

          {/* Input mode toggle */}
          <div className="flex items-center justify-between">
            <Label className="text-slate-300 text-sm">Input by</Label>
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

          {sellExceedsHoldings && (
            <p className="text-xs text-red-400">
              SELL quantity exceeds current holdings ({asset.total_quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })})
            </p>
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

          {/* Affects cash account — create mode only */}
          {!isEdit && (() => {
            const cashAcct = cashAccounts.find((a) => a.currency === txCurrency)
            return (
              <label className="flex items-start gap-3 cursor-pointer select-none rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={affectsCash}
                  onChange={(e) => setAffectsCash(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 accent-emerald-500 cursor-pointer"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 font-medium">
                    {txType === 'BUY' ? 'Deduct from cash account' : 'Credit to cash account'}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {txCurrency} balance:{' '}
                    <span className={cn('font-medium', cashAcct ? (cashAcct.balance >= 0 ? 'text-slate-300' : 'text-loss') : 'text-slate-600')}>
                      {cashAcct ? formatCurrency(cashAcct.balance, txCurrency) : 'No account'}
                    </span>
                  </p>
                </div>
              </label>
            )
          })()}

          {/* Notes */}
          <div className="space-y-1.5">
            <Label className="text-slate-300">
              Notes <span className="text-slate-500 font-normal">(optional)</span>
            </Label>
            <Textarea
              {...register('notes')}
              placeholder="Anything worth remembering about this transaction…"
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
              disabled={isSubmitting || sellExceedsHoldings}
              className={cn(
                'text-white',
                txType === 'SELL'
                  ? 'bg-red-600 hover:bg-red-700'
                  : 'bg-emerald-600 hover:bg-emerald-700',
              )}
            >
              {isSubmitting ? 'Saving…' : isEdit ? 'Save Changes' : `Add ${txType}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
