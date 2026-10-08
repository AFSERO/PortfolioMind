import { useEffect, useState } from 'react'
import { ArrowLeft, Check, FileSearch, FileUp, Keyboard } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import UploadDropzone from '@/components/statements/UploadDropzone'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { liabilityService } from '@/services/liabilityService'
import type { Liability } from '@/types'
import { cn } from '@/utils/cn'

export default function StatementImportPage() {
  const { liabilityId } = useParams<{ liabilityId: string }>()
  const [liability, setLiability] = useState<Liability | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    if (!liabilityId) { setError('Liability not found'); setLoading(false); return }
    void liabilityService.get(liabilityId).then((data) => {
      if (!active) return
      setLiability(data)
      setError(data.liability_type === 'credit_card' ? null : 'PDF statements are available only for credit cards.')
    }).catch((caught) => {
      if (active) setError(caught instanceof Error ? caught.message : 'Liability could not be loaded')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [liabilityId])

  return (
    <AppShell>
      <div className="app-page max-w-5xl">
        <PageHeader
          eyebrow="Credit card statement"
          title={liability ? `Upload PDF · ${liability.name}` : 'Upload statement PDF'}
          description="Validate a statement file before the future analysis step. No financial records are created here."
          leading={<Button asChild variant="ghost" size="icon"><Link to={liabilityId ? `/liabilities/${liabilityId}/statements` : '/liabilities'} aria-label="Back to statements"><ArrowLeft /></Link></Button>}
          actions={liabilityId ? <Button asChild variant="outline"><Link to={`/liabilities/${liabilityId}/statements?manual=true`}><Keyboard />Enter manually</Link></Button> : null}
        />

        <StepIndicator />

        {loading ? <Skeleton className="h-80 w-full rounded-xl" /> : error || !liabilityId || !liability ? (
          <Alert variant="destructive"><FileSearch /><AlertTitle>Upload unavailable</AlertTitle><AlertDescription>{error ?? 'Liability not found'}</AlertDescription></Alert>
        ) : (
          <Card className="shadow-card">
            <CardHeader><CardTitle>Choose statement PDF</CardTitle><CardDescription>Preflight checks the file format, size and duplicate fingerprint only.</CardDescription></CardHeader>
            <CardContent><UploadDropzone liabilityId={liabilityId} /></CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  )
}

function StepIndicator() {
  const steps = [
    { label: 'Upload', icon: FileUp, active: true },
    { label: 'Review', icon: FileSearch, active: false },
    { label: 'Confirm', icon: Check, active: false },
  ]
  return (
    <ol aria-label="Statement import steps" className="grid grid-cols-3 gap-2">
      {steps.map((step, index) => (
        <li key={step.label} aria-current={step.active ? 'step' : undefined} className={cn('flex items-center gap-2 rounded-lg border px-3 py-2 text-sm', step.active ? 'border-primary/40 bg-primary/10 text-primary' : 'text-muted-foreground')}>
          <span className="financial-value flex size-6 items-center justify-center rounded-full bg-muted text-xs">{index + 1}</span>
          <step.icon className="hidden size-4 sm:block" aria-hidden="true" />
          <span>{step.label}</span>
        </li>
      ))}
    </ol>
  )
}
