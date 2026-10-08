import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
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
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { StatementPayload } from '@/services/statementService'
import type { Liability, LiabilityStatement } from '@/types'


const money = z
  .string()
  .trim()
  .min(1, 'Required')
  .refine((value) => /^\d+(\.\d{1,6})?$/.test(value), 'Use a non-negative amount')

const schema = z
  .object({
    statement_period_start: z.string().min(1, 'Required'),
    statement_period_end: z.string().min(1, 'Required'),
    statement_date: z.string().min(1, 'Required'),
    due_date: z.string().min(1, 'Required'),
    currency: z.string().length(3),
    previous_balance: money,
    payments_total: money,
    purchases_total: money,
    fees_total: money,
    interest_total: money,
    refunds_total: money,
    statement_balance: money,
    minimum_payment: money,
    remaining_installments_total: money,
    notes: z.string(),
  })
  .superRefine((values, context) => {
    if (values.statement_period_start > values.statement_period_end) {
      context.addIssue({
        code: 'custom',
        path: ['statement_period_end'],
        message: 'Period end must be after period start',
      })
    }
    if (values.due_date < values.statement_date) {
      context.addIssue({
        code: 'custom',
        path: ['due_date'],
        message: 'Due date must be after statement date',
      })
    }
    if (Number(values.minimum_payment) > Number(values.statement_balance)) {
      context.addIssue({
        code: 'custom',
        path: ['minimum_payment'],
        message: 'Minimum payment cannot exceed statement balance',
      })
    }
  })

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  liability: Liability
  statement?: LiabilityStatement | null
  onClose: () => void
  onSave: (payload: StatementPayload, statementId?: string) => Promise<void>
}

const emptyValues = (currency: string): FormValues => ({
  statement_period_start: '',
  statement_period_end: '',
  statement_date: '',
  due_date: '',
  currency,
  previous_balance: '0',
  payments_total: '0',
  purchases_total: '0',
  fees_total: '0',
  interest_total: '0',
  refunds_total: '0',
  statement_balance: '0',
  minimum_payment: '0',
  remaining_installments_total: '0',
  notes: '',
})

function valuesFor(
  liability: Liability,
  statement?: LiabilityStatement | null,
): FormValues {
  if (!statement) return emptyValues(liability.currency)
  return {
    statement_period_start: statement.statement_period_start,
    statement_period_end: statement.statement_period_end,
    statement_date: statement.statement_date,
    due_date: statement.due_date,
    currency: statement.currency,
    previous_balance: String(statement.previous_balance),
    payments_total: String(statement.payments_total),
    purchases_total: String(statement.purchases_total),
    fees_total: String(statement.fees_total),
    interest_total: String(statement.interest_total),
    refunds_total: String(statement.refunds_total),
    statement_balance: String(statement.statement_balance),
    minimum_payment: String(statement.minimum_payment),
    remaining_installments_total: String(statement.remaining_installments_total),
    notes: statement.notes ?? '',
  }
}

export default function StatementFormDialog({
  open,
  liability,
  statement,
  onClose,
  onSave,
}: Props) {
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(liability, statement),
  })

  useEffect(() => {
    if (open) reset(valuesFor(liability, statement))
  }, [liability, open, reset, statement])

  const submit = handleSubmit(async (values) => {
    try {
      await onSave(
        {
          ...values,
          notes: values.notes.trim() || null,
          source: 'manual',
        },
        statement?.id,
      )
      onClose()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : 'Failed to save statement',
      )
    }
  })

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{statement ? 'Edit Statement' : 'Add Statement'}</DialogTitle>
          <DialogDescription>
            Enter the bank-reported summary. Saving a draft does not change the
            liability balance.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <div className="flex flex-col gap-6">
          <FieldSet>
            <FieldLegend>Statement dates</FieldLegend>
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="statement-period-start"
              label="Period Start"
              type="date"
              input={register('statement_period_start')}
              error={errors.statement_period_start?.message}
            />
            <FormField
              id="statement-period-end"
              label="Period End"
              type="date"
              input={register('statement_period_end')}
              error={errors.statement_period_end?.message}
            />
            <FormField
              id="statement-date"
              label="Statement Date"
              type="date"
              input={register('statement_date')}
              error={errors.statement_date?.message}
            />
            <FormField
              id="statement-due-date"
              label="Due Date"
              type="date"
              input={register('due_date')}
              error={errors.due_date?.message}
            />
            <FormField
              id="statement-currency"
              label="Currency"
              input={register('currency')}
              error={errors.currency?.message}
              disabled
            />
            </FieldGroup>
          </FieldSet>
          <FieldSet>
            <FieldLegend>Balance activity</FieldLegend>
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="statement-previous-balance"
              label="Previous Balance"
              input={register('previous_balance')}
              error={errors.previous_balance?.message}
              money
            />
            <FormField
              id="statement-purchases"
              label="Purchases"
              input={register('purchases_total')}
              error={errors.purchases_total?.message}
              money
            />
            <FormField
              id="statement-payments"
              label="Payments"
              input={register('payments_total')}
              error={errors.payments_total?.message}
              money
            />
            <FormField
              id="statement-refunds"
              label="Refunds"
              input={register('refunds_total')}
              error={errors.refunds_total?.message}
              money
            />
            <FormField
              id="statement-interest"
              label="Interest"
              input={register('interest_total')}
              error={errors.interest_total?.message}
              money
            />
            <FormField
              id="statement-fees"
              label="Fees"
              input={register('fees_total')}
              error={errors.fees_total?.message}
              money
            />
            </FieldGroup>
          </FieldSet>
          <FieldSet>
            <FieldLegend>Payment details</FieldLegend>
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="statement-balance"
              label="Reported Statement Balance"
              input={register('statement_balance')}
              error={errors.statement_balance?.message}
              money
            />
            <FormField
              id="statement-minimum"
              label="Minimum Payment"
              input={register('minimum_payment')}
              error={errors.minimum_payment?.message}
              money
            />
            <FormField
              id="statement-remaining-installments"
              label="Remaining Installments (informational)"
              input={register('remaining_installments_total')}
              error={errors.remaining_installments_total?.message}
              money
            />
            <Field className="sm:col-span-2" data-invalid={errors.notes != null}>
              <FieldLabel htmlFor="statement-notes">Notes</FieldLabel>
              <Textarea id="statement-notes" rows={3} {...register('notes')} />
              <FieldError>{errors.notes?.message}</FieldError>
            </Field>
            </FieldGroup>
          </FieldSet>
          </div>
          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : statement ? 'Save Changes' : 'Add Statement'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function FormField({
  id,
  label,
  input,
  error,
  type = 'text',
  money = false,
  disabled = false,
}: {
  id: string
  label: string
  input: UseFormRegisterReturn
  error?: string
  type?: string
  money?: boolean
  disabled?: boolean
}) {
  return (
    <Field data-invalid={error != null} data-disabled={disabled || undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type={money ? 'number' : type}
        min={money ? '0' : undefined}
        step={money ? '0.000001' : undefined}
        disabled={disabled}
        aria-invalid={error != null}
        {...input}
      />
      <FieldError>{error}</FieldError>
    </Field>
  )
}
