import { useEffect } from 'react'
import {
  Controller,
  type SubmitHandler,
  type UseFormRegisterReturn,
  useForm,
} from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type {
  LiabilityCreatePayload,
  LiabilityUpdatePayload,
} from '@/services/liabilityService'
import type { Liability, LiabilityType } from '@/types'


const LIABILITY_TYPES: Array<{ value: LiabilityType; label: string }> = [
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'personal_loan', label: 'Personal Loan' },
  { value: 'mortgage', label: 'Mortgage' },
  { value: 'student_loan', label: 'Student Loan' },
  { value: 'other', label: 'Other' },
]

const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP'] as const
const DECIMAL_PATTERN = /^\d{1,12}(?:\.\d{1,6})?$/

const decimalString = z
  .string()
  .trim()
  .min(1, 'Amount is required')
  .regex(DECIMAL_PATTERN, 'Use a non-negative value with at most 6 decimals')

const optionalDecimalString = z.union([z.literal(''), decimalString])

const formSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(255),
  liability_type: z.enum([
    'credit_card',
    'personal_loan',
    'mortgage',
    'student_loan',
    'other',
  ]),
  currency: z.enum(CURRENCIES),
  current_balance: decimalString,
  original_balance: optionalDecimalString,
  interest_rate: optionalDecimalString,
  minimum_payment: optionalDecimalString,
  due_date: z.string(),
  notes: z.string().max(5000),
  is_active: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

interface Props {
  open: boolean
  onClose: () => void
  liability?: Liability | null
  onSave: (
    payload: LiabilityCreatePayload | LiabilityUpdatePayload,
    liabilityId?: string,
  ) => Promise<void>
}

const emptyValues: FormValues = {
  name: '',
  liability_type: 'credit_card',
  currency: 'TRY',
  current_balance: '',
  original_balance: '',
  interest_rate: '',
  minimum_payment: '',
  due_date: '',
  notes: '',
  is_active: true,
}

function valuesFor(liability?: Liability | null): FormValues {
  if (!liability) return emptyValues
  return {
    name: liability.name,
    liability_type: liability.liability_type,
    currency: liability.currency as FormValues['currency'],
    current_balance: String(liability.current_balance),
    original_balance:
      liability.original_balance == null ? '' : String(liability.original_balance),
    interest_rate:
      liability.interest_rate == null ? '' : String(liability.interest_rate),
    minimum_payment:
      liability.minimum_payment == null ? '' : String(liability.minimum_payment),
    due_date: liability.due_date ?? '',
    notes: liability.notes ?? '',
    is_active: liability.is_active,
  }
}

function nullable(value: string): string | null {
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : null
}

export default function LiabilityFormDialog({
  open,
  onClose,
  liability,
  onSave,
}: Props) {
  const isEdit = liability != null
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: valuesFor(liability),
  })

  useEffect(() => {
    if (open) reset(valuesFor(liability))
  }, [liability, open, reset])

  const onSubmit: SubmitHandler<FormValues> = async (values) => {
    const payload: LiabilityCreatePayload = {
      name: values.name,
      liability_type: values.liability_type,
      currency: values.currency,
      current_balance: values.current_balance,
      original_balance: nullable(values.original_balance),
      interest_rate: nullable(values.interest_rate),
      minimum_payment: nullable(values.minimum_payment),
      due_date: nullable(values.due_date),
      notes: nullable(values.notes),
      is_active: values.is_active,
    }
    try {
      await onSave(payload, liability?.id)
      toast.success(isEdit ? 'Liability updated' : 'Liability added')
      onClose()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : 'Failed to save liability',
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto border-slate-800 bg-slate-900 text-slate-100">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Liability' : 'Add Liability'}</DialogTitle>
          <DialogDescription className="text-slate-400">
            Balances are maintained manually and included in your net worth.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 py-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="liability-name" className="text-slate-300">
                Liability Name
              </Label>
              <Input
                id="liability-name"
                {...register('name')}
                aria-invalid={errors.name != null}
                placeholder="e.g. Main credit card"
                className="border-slate-700 bg-slate-800 text-slate-100"
              />
              {errors.name && (
                <p className="text-xs text-loss">{errors.name.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-slate-300">Liability Type</Label>
              <Controller
                name="liability_type"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Liability Type" className="border-slate-700 bg-slate-800 text-slate-100">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="border-slate-700 bg-slate-800 text-slate-100">
                      <SelectGroup>
                        {LIABILITY_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label className="text-slate-300">Currency</Label>
              <Controller
                name="currency"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Currency" className="border-slate-700 bg-slate-800 text-slate-100">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="border-slate-700 bg-slate-800 text-slate-100">
                      <SelectGroup>
                        {CURRENCIES.map((currency) => (
                          <SelectItem key={currency} value={currency}>
                            {currency}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>

            <DecimalField
              id="current-balance"
              label="Current Balance"
              error={errors.current_balance?.message}
              inputProps={register('current_balance')}
              required
            />
            <DecimalField
              id="original-balance"
              label="Original Balance"
              error={errors.original_balance?.message}
              inputProps={register('original_balance')}
            />
            <DecimalField
              id="interest-rate"
              label="Interest Rate (%)"
              error={errors.interest_rate?.message}
              inputProps={register('interest_rate')}
            />
            <DecimalField
              id="minimum-payment"
              label="Minimum Payment"
              error={errors.minimum_payment?.message}
              inputProps={register('minimum_payment')}
            />

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="due-date" className="text-slate-300">
                Due Date <span className="font-normal text-slate-500">(optional)</span>
              </Label>
              <Input
                id="due-date"
                type="date"
                {...register('due_date')}
                className="border-slate-700 bg-slate-800 text-slate-100"
              />
            </div>

            <label className="flex items-center gap-3 self-end rounded-md border border-slate-800 px-3 py-2.5 text-sm text-slate-300">
              <input
                type="checkbox"
                {...register('is_active')}
                className="size-4 rounded border-slate-600 accent-emerald-500"
              />
              Active liability
            </label>

            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="liability-notes" className="text-slate-300">
                Notes <span className="font-normal text-slate-500">(optional)</span>
              </Label>
              <Textarea
                id="liability-notes"
                {...register('notes')}
                rows={3}
                placeholder="Add a note about this liability"
                className="resize-none border-slate-700 bg-slate-800 text-slate-100"
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Liability'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function DecimalField({
  id,
  label,
  error,
  inputProps,
  required = false,
}: {
  id: string
  label: string
  error?: string
  inputProps: UseFormRegisterReturn
  required?: boolean
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-slate-300">
        {label}{' '}
        {!required && <span className="font-normal text-slate-500">(optional)</span>}
      </Label>
      <Input
        id={id}
        type="number"
        min="0"
        step="0.000001"
        placeholder="0.00"
        aria-invalid={error != null}
        {...inputProps}
        className="border-slate-700 bg-slate-800 text-slate-100"
      />
      {error && <p className="text-xs text-loss">{error}</p>}
    </div>
  )
}
