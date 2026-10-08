import { useRef, useState } from 'react'
import { CheckCircle2, Copy, FileText, LoaderCircle, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { STATEMENT_PDF_MAX_BYTES, statementService, type StatementPdfPreflight } from '@/services/statementService'
import { cn } from '@/utils/cn'

type UploadState =
  | { status: 'idle' }
  | { status: 'validating'; file: File }
  | { status: 'ready'; file: File; result: StatementPdfPreflight }
  | { status: 'duplicate'; file: File; result: StatementPdfPreflight }
  | { status: 'error'; file?: File; message: string }

interface UploadDropzoneProps {
  liabilityId: string
  maxBytes?: number
}

export default function UploadDropzone({ liabilityId, maxBytes = STATEMENT_PDF_MAX_BYTES }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const requestVersion = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [state, setState] = useState<UploadState>({ status: 'idle' })
  const selectedFile = state.status === 'idle' ? undefined : state.file

  const chooseFile = () => inputRef.current?.click()

  const validate = async (file: File) => {
    const currentVersion = ++requestVersion.current
    const isPdfName = file.name.toLowerCase().endsWith('.pdf')
    const isPdfMime = file.type.toLowerCase() === 'application/pdf'
    if (!isPdfName || !isPdfMime) {
      setState({ status: 'error', file, message: 'Only PDF files are accepted. Check both the extension and file type.' })
      return
    }
    if (file.size > maxBytes) {
      setState({ status: 'error', file, message: `This file exceeds the ${formatBytes(maxBytes)} limit.` })
      return
    }

    setState({ status: 'validating', file })
    try {
      const result = await statementService.preflightPdf(liabilityId, file)
      if (currentVersion !== requestVersion.current) return
      setState({ status: result.is_duplicate ? 'duplicate' : 'ready', file, result })
    } catch (error) {
      if (currentVersion !== requestVersion.current) return
      setState({ status: 'error', file, message: error instanceof Error ? error.message : 'The PDF could not be checked. Try again.' })
    }
  }

  const remove = () => {
    requestVersion.current += 1
    setState({ status: 'idle' })
    if (inputRef.current) inputRef.current.value = ''
  }

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void validate(file)
  }

  return (
    <div className="flex flex-col gap-4">
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        accept=".pdf,application/pdf"
        onChange={(event) => { const file = event.target.files?.[0]; if (file) void validate(file) }}
        aria-label="Choose credit-card statement PDF"
      />
      <div
        role="button"
        tabIndex={0}
        aria-label={selectedFile ? 'Replace selected PDF' : 'Upload a PDF statement'}
        onClick={chooseFile}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            chooseFile()
          }
        }}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false) }}
        onDrop={onDrop}
        className={cn(
          'flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed bg-muted/20 p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5',
          dragging && 'border-primary bg-primary/10',
          state.status === 'ready' && 'border-positive/60 bg-positive/5',
          state.status === 'duplicate' && 'border-warning/60 bg-warning/5',
          state.status === 'error' && 'border-negative/60 bg-negative/5',
        )}
      >
        <DropzoneContent state={state} maxBytes={maxBytes} />
      </div>

      <div aria-live="polite" aria-atomic="true">
        {state.status === 'error' ? (
          <Alert variant="destructive"><FileText /><AlertTitle>PDF not accepted</AlertTitle><AlertDescription>{state.message}</AlertDescription></Alert>
        ) : null}
        {state.status === 'duplicate' ? (
          <Alert><Copy /><AlertTitle>This PDF was already used</AlertTitle><AlertDescription>
            No new record was created. {state.result.matched_statement_id ? <Link className="font-medium text-primary underline underline-offset-4" to={`/liabilities/${liabilityId}/statements/${state.result.matched_statement_id}`}>Open the matching statement</Link> : null}
          </AlertDescription></Alert>
        ) : null}
        {state.status === 'ready' ? (
          <Alert><CheckCircle2 className="text-positive" /><AlertTitle>PDF preflight complete</AlertTitle><AlertDescription>The file is a valid PDF and has not been used for another statement. Analysis is not available in this release.</AlertDescription></Alert>
        ) : null}
      </div>

      {selectedFile ? (
        <Card>
          <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{selectedFile.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">{formatBytes(selectedFile.size)} · PDF</p>
              {'result' in state ? <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">SHA-256 {state.result.sha256}</p> : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={(event) => { event.stopPropagation(); chooseFile() }}><RefreshCw />Replace</Button>
              <Button variant="ghost" onClick={(event) => { event.stopPropagation(); remove() }}><Trash2 />Remove</Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">The file is checked in memory and is not stored. Maximum {formatBytes(maxBytes)}.</p>
        <Button disabled>Analyze statement</Button>
      </div>
      <p className="text-xs text-muted-foreground">Statement analysis and transaction extraction will be added in a later product package.</p>
    </div>
  )
}

function DropzoneContent({ state, maxBytes }: { state: UploadState; maxBytes: number }) {
  if (state.status === 'validating') return <><LoaderCircle className="mb-4 size-10 animate-spin text-primary" /><p className="font-medium">Checking PDF…</p><p className="mt-1 text-sm text-muted-foreground">Verifying type, size, signature and duplicate hash.</p></>
  if (state.status === 'ready') return <><CheckCircle2 className="mb-4 size-10 text-positive" /><p className="font-medium">PDF ready</p><p className="mt-1 text-sm text-muted-foreground">Click or press Enter to replace it.</p></>
  if (state.status === 'duplicate') return <><Copy className="mb-4 size-10 text-warning" /><p className="font-medium">Duplicate PDF found</p><p className="mt-1 text-sm text-muted-foreground">The existing statement is linked below.</p></>
  if (state.status === 'error') return <><FileText className="mb-4 size-10 text-negative" /><p className="font-medium">Choose another PDF</p><p className="mt-1 text-sm text-muted-foreground">Click, press Enter, or drop a replacement file.</p></>
  return <><UploadCloud className="mb-4 size-10 text-primary" /><p className="font-medium">Drop a credit-card statement PDF here</p><p className="mt-1 text-sm text-muted-foreground">or click to choose a file · PDF only · up to {formatBytes(maxBytes)}</p></>
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`
  return `${(bytes / (1024 * 1024)).toFixed(bytes % (1024 * 1024) === 0 ? 0 : 1)} MiB`
}
