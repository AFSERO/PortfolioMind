import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'


interface Props {
  open: boolean
  liabilityName: string
  isDeleting: boolean
  onClose: () => void
  onConfirm: () => Promise<void>
}

export default function LiabilityDeleteDialog({
  open,
  liabilityName,
  isDeleting,
  onClose,
  onConfirm,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-sm border-slate-800 bg-slate-900 text-slate-100">
        <DialogHeader>
          <DialogTitle>Delete Liability</DialogTitle>
          <DialogDescription className="text-slate-400">
            Delete <span className="font-semibold text-slate-200">{liabilityName}</span>?
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
            aria-label="Delete liability"
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

