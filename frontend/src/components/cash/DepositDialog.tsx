import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
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
import type { CashAccount } from '@/types'
import type { DepositPayload } from '@/services/cashService'
import { formatCurrency } from '@/utils/format'

const schema = z.object({
  amount: z.preprocess(
    (v) => (v === '' || v == null ? undefined : Number(v)),
    z.number().positive('Must be > 0'),
  ),
  notes: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onClose: () => void
  account: CashAccount | null
  currency: string
  onDeposit: (payload: DepositPayload) => Promise<void>
}

export default function DepositDialog({ open, onClose, account, currency, onDeposit }: Props) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema as any) as any })

  useEffect(() => {
    if (open) reset({ amount: undefined, notes: '' })
  }, [open, reset])

  const onSubmit = async (values: FormValues) => {
    try {
      await onDeposit({ currency, amount: values.amount!, notes: values.notes || undefined })
      toast.success(`Deposited ${formatCurrency(values.amount!, currency)} to ${currency} account`)
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Deposit failed')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm bg-slate-900 border-slate-800 text-slate-100">
        <DialogHeader>
          <DialogTitle className="text-slate-100">Deposit — {currency}</DialogTitle>
        </DialogHeader>
        {account && (
          <p className="text-xs text-slate-500">
            Current balance: <span className="text-slate-300 font-medium">{formatCurrency(account.balance, currency)}</span>
          </p>
        )}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label className="text-slate-300">Amount</Label>
            <Input
              {...register('amount')}
              type="number"
              step="any"
              placeholder="0.00"
              className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
            />
            {errors.amount && <p className="text-xs text-red-400">{errors.amount.message as string}</p>}
          </div>
          <div className="space-y-1.5">
            <Label className="text-slate-300">Notes <span className="text-slate-500 font-normal">(optional)</span></Label>
            <Textarea
              {...register('notes')}
              rows={2}
              placeholder="e.g. Salary, transfer from bank…"
              className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500 resize-none"
            />
          </div>
          <DialogFooter className="pt-1">
            <Button type="button" variant="outline" onClick={onClose} className="border-slate-700 text-slate-300 hover:bg-slate-800">
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              {isSubmitting ? 'Depositing…' : 'Deposit'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
