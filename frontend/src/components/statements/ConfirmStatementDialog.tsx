import { useState } from 'react'
import { toast } from 'sonner'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import type { LiabilityStatement } from '@/types'
import { formatCurrency } from '@/utils/format'


interface Props {
  open: boolean
  statement: LiabilityStatement
  onClose: () => void
  onConfirm: (applyToLiability: boolean) => Promise<void>
}

export default function ConfirmStatementDialog({
  open,
  statement,
  onClose,
  onConfirm,
}: Props) {
  const [applyToLiability, setApplyToLiability] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const confirm = async () => {
    setIsSubmitting(true)
    try {
      await onConfirm(applyToLiability)
      setApplyToLiability(false)
      onClose()
    } catch (caught) {
      toast.error(
        caught instanceof Error ? caught.message : 'Failed to confirm statement',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(next) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Confirm Statement</AlertDialogTitle>
          <AlertDialogDescription>
            Confirm the reported balance of{' '}
            {formatCurrency(statement.statement_balance, statement.currency)}.
            Confirmed financial fields become read-only.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Field orientation="horizontal">
          <Checkbox
            id="apply-to-liability"
            checked={applyToLiability}
            onCheckedChange={(checked) => setApplyToLiability(checked === true)}
          />
          <div>
            <FieldLabel htmlFor="apply-to-liability">
              Apply this statement balance to the liability
            </FieldLabel>
            <FieldDescription>
              Sets the current balance to this value; it does not add a delta.
            </FieldDescription>
          </div>
        </Field>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={isSubmitting} onClick={() => void confirm()}>
            {isSubmitting ? 'Confirming…' : 'Confirm Statement'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
