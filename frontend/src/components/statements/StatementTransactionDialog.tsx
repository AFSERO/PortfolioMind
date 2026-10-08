import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
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
  StatementTransactionPayload,
  StatementTransactionUpdatePayload,
} from '@/services/statementService'
import type { InstallmentPlan, StatementTransaction } from '@/types'


const schema = z
  .object({
    transaction_date: z.string().min(1, 'Required'),
    description: z.string().trim().min(1, 'Required'),
    transaction_type: z.enum([
      'purchase',
      'payment',
      'refund',
      'fee',
      'interest',
      'cash_advance',
      'installment',
      'other',
    ]),
    amount: z
      .string()
      .trim()
      .refine((value) => /^\d+(\.\d{1,6})?$/.test(value) && Number(value) > 0, 'Enter a positive amount'),
    currency: z.string().length(3),
    installment_plan_id: z.string(),
    installment_number: z.string(),
    installment_count: z.string(),
    notes: z.string(),
  })
  .superRefine((values, context) => {
    if (values.transaction_type !== 'installment') return
    const number = Number(values.installment_number)
    const count = Number(values.installment_count)
    if (!Number.isInteger(number) || number < 1) {
      context.addIssue({ code: 'custom', path: ['installment_number'], message: 'Required' })
    }
    if (!Number.isInteger(count) || count < 2 || count < number) {
      context.addIssue({ code: 'custom', path: ['installment_count'], message: 'Must be at least the installment number' })
    }
  })

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  currency: string
  plans: InstallmentPlan[]
  transaction?: StatementTransaction | null
  onClose: () => void
  onSave: (
    payload: StatementTransactionPayload | StatementTransactionUpdatePayload,
    transactionId?: string,
  ) => Promise<void>
}

function valuesFor(currency: string, transaction?: StatementTransaction | null): FormValues {
  if (!transaction) {
    return {
      transaction_date: '',
      description: '',
      transaction_type: 'purchase',
      amount: '',
      currency,
      installment_plan_id: '',
      installment_number: '',
      installment_count: '',
      notes: '',
    }
  }
  return {
    transaction_date: transaction.transaction_date,
    description: transaction.description,
    transaction_type: transaction.transaction_type,
    amount: String(transaction.amount),
    currency: transaction.currency,
    installment_plan_id: transaction.installment_plan_id ?? '',
    installment_number: transaction.installment_number?.toString() ?? '',
    installment_count: transaction.installment_count?.toString() ?? '',
    notes: transaction.notes ?? '',
  }
}

export default function StatementTransactionDialog({
  open,
  currency,
  plans,
  transaction,
  onClose,
  onSave,
}: Props) {
  const {
    register,
    control,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(currency, transaction),
  })
  const type = useWatch({ control, name: 'transaction_type' })

  useEffect(() => {
    if (open) reset(valuesFor(currency, transaction))
  }, [currency, open, reset, transaction])

  const submit = handleSubmit(async (values) => {
    const installment = values.transaction_type === 'installment'
    const payload: StatementTransactionPayload = {
      transaction_date: values.transaction_date,
      description: values.description,
      transaction_type: values.transaction_type,
      amount: values.amount,
      currency: values.currency,
      installment_plan_id: installment
        ? values.installment_plan_id || null
        : null,
      installment_number: installment ? Number(values.installment_number) : null,
      installment_count: installment ? Number(values.installment_count) : null,
      notes: values.notes.trim() || null,
    }
    try {
      await onSave(payload, transaction?.id)
      onClose()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : 'Failed to save transaction',
      )
    }
  })

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{transaction ? 'Edit Transaction' : 'Add Transaction'}</DialogTitle>
          <DialogDescription>
            Amounts are positive magnitudes; payment and refund types are subtracted.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <Field data-invalid={errors.transaction_date != null}>
              <FieldLabel htmlFor="transaction-date">Date</FieldLabel>
              <Input id="transaction-date" type="date" aria-invalid={errors.transaction_date != null} {...register('transaction_date')} />
              <FieldError>{errors.transaction_date?.message}</FieldError>
            </Field>
            <Field data-invalid={errors.transaction_type != null}>
              <FieldLabel>Type</FieldLabel>
              <Controller
                name="transaction_type"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Transaction Type" aria-invalid={errors.transaction_type != null}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {TRANSACTION_TYPES.map((item) => (
                          <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                )}
              />
              <FieldError>{errors.transaction_type?.message}</FieldError>
            </Field>
            <Field className="sm:col-span-2" data-invalid={errors.description != null}>
              <FieldLabel htmlFor="transaction-description">Description</FieldLabel>
              <Input id="transaction-description" aria-invalid={errors.description != null} {...register('description')} />
              <FieldError>{errors.description?.message}</FieldError>
            </Field>
            <Field data-invalid={errors.amount != null}>
              <FieldLabel htmlFor="transaction-amount">Amount</FieldLabel>
              <Input id="transaction-amount" type="number" min="0.000001" step="0.000001" aria-invalid={errors.amount != null} {...register('amount')} />
              <FieldError>{errors.amount?.message}</FieldError>
            </Field>
            <Field data-disabled>
              <FieldLabel htmlFor="transaction-currency">Currency</FieldLabel>
              <Input id="transaction-currency" disabled {...register('currency')} />
            </Field>
            {type === 'installment' ? (
              <>
                <Field>
                  <FieldLabel>Installment Plan</FieldLabel>
                  <Controller
                    name="installment_plan_id"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value || 'none'} onValueChange={(value) => field.onChange(value === 'none' ? '' : value)}>
                        <SelectTrigger aria-label="Installment Plan"><SelectValue placeholder="Optional plan" /></SelectTrigger>
                        <SelectContent><SelectGroup>
                          <SelectItem value="none">No linked plan</SelectItem>
                          {plans.map((plan) => <SelectItem key={plan.id} value={plan.id}>{plan.description}</SelectItem>)}
                        </SelectGroup></SelectContent>
                      </Select>
                    )}
                  />
                </Field>
                <Field data-invalid={errors.installment_number != null}>
                  <FieldLabel htmlFor="installment-number">Installment Number</FieldLabel>
                  <Input id="installment-number" type="number" min="1" aria-invalid={errors.installment_number != null} {...register('installment_number')} />
                  <FieldError>{errors.installment_number?.message}</FieldError>
                </Field>
                <Field data-invalid={errors.installment_count != null}>
                  <FieldLabel htmlFor="installment-count">Installment Count</FieldLabel>
                  <Input id="installment-count" type="number" min="2" aria-invalid={errors.installment_count != null} {...register('installment_count')} />
                  <FieldError>{errors.installment_count?.message}</FieldError>
                </Field>
              </>
            ) : null}
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="transaction-notes">Notes</FieldLabel>
              <Textarea id="transaction-notes" rows={2} {...register('notes')} />
            </Field>
          </FieldGroup>
          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : 'Save Transaction'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

const TRANSACTION_TYPES = [
  { value: 'purchase', label: 'Purchase' },
  { value: 'payment', label: 'Payment' },
  { value: 'refund', label: 'Refund' },
  { value: 'fee', label: 'Fee' },
  { value: 'interest', label: 'Interest' },
  { value: 'cash_advance', label: 'Cash Advance' },
  { value: 'installment', label: 'Installment' },
  { value: 'other', label: 'Other' },
] as const
