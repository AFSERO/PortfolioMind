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


interface Props {
  open: boolean
  title: string
  description: string
  onClose: () => void
  onConfirm: () => Promise<void>
}

export default function DeleteStatementItemDialog({
  open,
  title,
  description,
  onClose,
  onConfirm,
}: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const confirm = async () => {
    setIsSubmitting(true)
    try {
      await onConfirm()
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Delete failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(next) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={isSubmitting}
            onClick={() => void confirm()}
          >
            {isSubmitting ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
