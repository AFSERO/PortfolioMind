import { useEffect, useMemo } from 'react'
import { useForm, Controller } from 'react-hook-form'
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
import type { CashAccount } from '@/types'
import type { TransferPayload } from '@/services/cashService'
import { useForexRates } from '@/hooks/useForexRates'
import { formatCurrency } from '@/utils/format'

const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP'] as const

const schema = z
  .object({
    from_currency: z.string().min(3),
    to_currency: z.string().min(3),
    from_amount: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0'),
    ),
    rate: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be > 0'),
    ),
    notes: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.from_currency === val.to_currency) {
      ctx.addIssue({ code: 'custom', path: ['to_currency'], message: 'Must differ from source' })
    }
  })

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onClose: () => void
  accounts: CashAccount[]
  defaultFromCurrency?: string
  onTransfer: (payload: TransferPayload) => Promise<void>
}

export default function TransferDialog({ open, onClose, accounts, defaultFromCurrency = 'TRY', onTransfer }: Props) {
  const { rates } = useForexRates()

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema as any) as any,
    defaultValues: {
      from_currency: defaultFromCurrency,
      to_currency: defaultFromCurrency === 'TRY' ? 'USD' : 'TRY',
      from_amount: undefined,
      rate: undefined,
      notes: '',
    },
  })

  const fromCurrency = watch('from_currency')
  const toCurrency = watch('to_currency')
  const fromAmount = watch('from_amount') as number | undefined
  const rate = watch('rate') as number | undefined

  // Prefill rate from forex rates
  useEffect(() => {
    if (!fromCurrency || !toCurrency || fromCurrency === toCurrency) return
    const direct = rates[`${fromCurrency}/${toCurrency}`]
    if (direct) { setValue('rate', parseFloat(direct.toFixed(6))); return }
    const inverse = rates[`${toCurrency}/${fromCurrency}`]
    if (inverse && inverse > 0) { setValue('rate', parseFloat((1 / inverse).toFixed(6))); return }
    const fromToTry = rates[`${fromCurrency}/TRY`]
    const toToTry = rates[`${toCurrency}/TRY`]
    if (fromToTry && toToTry && toToTry > 0) {
      setValue('rate', parseFloat((fromToTry / toToTry).toFixed(6)))
    }
  }, [fromCurrency, toCurrency, rates, setValue])

  useEffect(() => {
    if (open) {
      reset({
        from_currency: defaultFromCurrency,
        to_currency: defaultFromCurrency === 'TRY' ? 'USD' : 'TRY',
        from_amount: undefined,
        rate: undefined,
        notes: '',
      })
    }
  }, [open, defaultFromCurrency, reset])

  const toAmount = useMemo(() => {
    const a = Number(fromAmount)
    const r = Number(rate)
    if (!a || !r || !isFinite(a) || !isFinite(r) || a <= 0 || r <= 0) return null
    return a * r
  }, [fromAmount, rate])

  const fromAccount = accounts.find((a) => a.currency === fromCurrency)

  const onSubmit = async (values: FormValues) => {
    try {
      await onTransfer({
        from_currency: values.from_currency,
        to_currency: values.to_currency,
        from_amount: values.from_amount!,
        rate: values.rate!,
        notes: values.notes || undefined,
      })
      toast.success(`Transferred ${formatCurrency(values.from_amount!, values.from_currency)} → ${values.to_currency}`)
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Transfer failed')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md bg-slate-900 border-slate-800 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-100">Transfer Between Currencies</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-1">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-slate-300 text-xs">From</Label>
              <Controller
                name="from_currency"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c} className="focus:bg-slate-700">{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {fromAccount && (
                <p className="text-[11px] text-slate-500">
                  Balance: {formatCurrency(fromAccount.balance, fromCurrency)}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label className="text-slate-300 text-xs">To</Label>
              <Controller
                name="to_currency"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger className="bg-slate-800 border-slate-700 text-slate-100">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-700 text-slate-100">
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c} className="focus:bg-slate-700">{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.to_currency && (
                <p className="text-xs text-red-400">{errors.to_currency.message as string}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-slate-300 text-xs">Amount ({fromCurrency})</Label>
              <Input
                {...register('from_amount')}
                type="number"
                step="any"
                placeholder="0.00"
                className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
              />
              {errors.from_amount && (
                <p className="text-xs text-red-400">{errors.from_amount.message as string}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label className="text-slate-300 text-xs">
                Rate
                <span className="ml-1 text-slate-500 font-normal">({fromCurrency}/{toCurrency})</span>
              </Label>
              <Input
                {...register('rate')}
                type="number"
                step="any"
                placeholder="1.00"
                className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
              />
              {errors.rate && (
                <p className="text-xs text-red-400">{errors.rate.message as string}</p>
              )}
            </div>
          </div>

          {toAmount != null && (
            <p className="text-xs text-slate-400 bg-slate-800/60 rounded-md px-3 py-2">
              You will receive ≈ <span className="font-semibold text-emerald-400">{formatCurrency(toAmount, toCurrency)}</span>
            </p>
          )}

          <div className="space-y-1.5">
            <Label className="text-slate-300">Notes <span className="text-slate-500 font-normal">(optional)</span></Label>
            <Textarea
              {...register('notes')}
              rows={2}
              placeholder="e.g. Currency exchange at bank…"
              className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500 resize-none"
            />
          </div>

          <DialogFooter className="pt-1">
            <Button type="button" variant="outline" onClick={onClose} className="border-slate-700 text-slate-300 hover:bg-slate-800">
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              {isSubmitting ? 'Transferring…' : 'Transfer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
