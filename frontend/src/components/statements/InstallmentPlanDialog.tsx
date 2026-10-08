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
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import type {
  InstallmentPlanPayload,
  InstallmentPlanUpdatePayload,
} from '@/services/statementService'
import type { InstallmentPlan } from '@/types'


const decimal = z
  .string()
  .trim()
  .refine((value) => /^\d+(\.\d{1,6})?$/.test(value) && Number(value) > 0, 'Enter a positive amount')

const schema = z
  .object({
    description: z.string().trim().min(1, 'Required'),
    merchant_name: z.string(),
    purchase_date: z.string().min(1, 'Required'),
    currency: z.string().length(3),
    original_amount: decimal,
    installment_count: z.string().refine((value) => Number.isInteger(Number(value)) && Number(value) >= 2, 'Minimum 2'),
    monthly_installment_amount: decimal,
    first_installment_date: z.string().min(1, 'Required'),
    completed_installment_count: z.string().refine((value) => Number.isInteger(Number(value)) && Number(value) >= 0, 'Cannot be negative'),
    external_reference: z.string(),
  })
  .superRefine((values, context) => {
    const count = Number(values.installment_count)
    const completed = Number(values.completed_installment_count)
    if (completed > count) {
      context.addIssue({ code: 'custom', path: ['completed_installment_count'], message: 'Cannot exceed installment count' })
    }
    const difference = Math.abs(Number(values.original_amount) - Number(values.monthly_installment_amount) * count)
    if (difference > 0.01 * count + Number.EPSILON) {
      context.addIssue({ code: 'custom', path: ['monthly_installment_amount'], message: 'Schedule exceeds rounding tolerance' })
    }
  })

type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  currency: string
  plan?: InstallmentPlan | null
  onClose: () => void
  onSave: (
    payload: InstallmentPlanPayload | InstallmentPlanUpdatePayload,
    planId?: string,
  ) => Promise<void>
}

function valuesFor(currency: string, plan?: InstallmentPlan | null): FormValues {
  if (!plan) {
    return {
      description: '',
      merchant_name: '',
      purchase_date: '',
      currency,
      original_amount: '',
      installment_count: '2',
      monthly_installment_amount: '',
      first_installment_date: '',
      completed_installment_count: '0',
      external_reference: '',
    }
  }
  return {
    description: plan.description,
    merchant_name: plan.merchant_name ?? '',
    purchase_date: plan.purchase_date,
    currency: plan.currency,
    original_amount: String(plan.original_amount),
    installment_count: String(plan.installment_count),
    monthly_installment_amount: String(plan.monthly_installment_amount),
    first_installment_date: plan.first_installment_date,
    completed_installment_count: String(plan.completed_installment_count),
    external_reference: plan.external_reference ?? '',
  }
}

export default function InstallmentPlanDialog({
  open,
  currency,
  plan,
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
    defaultValues: valuesFor(currency, plan),
  })

  useEffect(() => {
    if (open) reset(valuesFor(currency, plan))
  }, [currency, open, plan, reset])

  const submit = handleSubmit(async (values) => {
    const completed = Number(values.completed_installment_count)
    const count = Number(values.installment_count)
    const payload: InstallmentPlanPayload = {
      description: values.description,
      merchant_name: values.merchant_name.trim() || null,
      purchase_date: values.purchase_date,
      currency: values.currency,
      original_amount: values.original_amount,
      installment_count: count,
      monthly_installment_amount: values.monthly_installment_amount,
      first_installment_date: values.first_installment_date,
      completed_installment_count: completed,
      status: completed === count ? 'completed' : plan?.status ?? 'active',
      external_reference: values.external_reference.trim() || null,
    }
    try {
      await onSave(payload, plan?.id)
      onClose()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : 'Failed to save installment plan',
      )
    }
  })

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{plan ? 'Edit Installment Plan' : 'Add Installment Plan'}</DialogTitle>
          <DialogDescription>
            The plan is informational and is not added again to the current statement or net worth.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            <PlanField id="plan-description" label="Description" input={register('description')} error={errors.description?.message} wide />
            <PlanField id="plan-merchant" label="Merchant" input={register('merchant_name')} error={errors.merchant_name?.message} />
            <PlanField id="plan-purchase-date" label="Purchase Date" input={register('purchase_date')} error={errors.purchase_date?.message} type="date" />
            <PlanField id="plan-currency" label="Currency" input={register('currency')} error={errors.currency?.message} disabled />
            <PlanField id="plan-original" label="Original Amount" input={register('original_amount')} error={errors.original_amount?.message} money />
            <PlanField id="plan-count" label="Installment Count" input={register('installment_count')} error={errors.installment_count?.message} type="number" min="2" />
            <PlanField id="plan-monthly" label="Monthly Installment" input={register('monthly_installment_amount')} error={errors.monthly_installment_amount?.message} money />
            <PlanField id="plan-first-date" label="First Installment Date" input={register('first_installment_date')} error={errors.first_installment_date?.message} type="date" />
            <PlanField id="plan-completed" label="Completed Installments" input={register('completed_installment_count')} error={errors.completed_installment_count?.message} type="number" min="0" />
            <PlanField id="plan-reference" label="External Reference" input={register('external_reference')} error={errors.external_reference?.message} />
          </FieldGroup>
          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : 'Save Plan'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PlanField({
  id,
  label,
  input,
  error,
  type = 'text',
  min,
  money = false,
  disabled = false,
  wide = false,
}: {
  id: string
  label: string
  input: UseFormRegisterReturn
  error?: string
  type?: string
  min?: string
  money?: boolean
  disabled?: boolean
  wide?: boolean
}) {
  return (
    <Field className={wide ? 'sm:col-span-2' : undefined} data-invalid={error != null} data-disabled={disabled || undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input id={id} type={money ? 'number' : type} min={money ? '0.000001' : min} step={money ? '0.000001' : undefined} disabled={disabled} aria-invalid={error != null} {...input} />
      <FieldError>{error}</FieldError>
    </Field>
  )
}
