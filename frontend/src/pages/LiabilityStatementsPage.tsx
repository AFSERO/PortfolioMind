import { useEffect, useState } from 'react'
import { ArrowLeft, FileText, FileUp, Keyboard, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import DeleteStatementItemDialog from '@/components/statements/DeleteStatementItemDialog'
import InstallmentOverview from '@/components/statements/InstallmentOverview'
import InstallmentPlanDialog from '@/components/statements/InstallmentPlanDialog'
import StatementFormDialog from '@/components/statements/StatementFormDialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useStatementWorkspace } from '@/hooks/useStatements'
import { statementService } from '@/services/statementService'
import type { InstallmentPlanPayload, InstallmentPlanUpdatePayload, StatementPayload, StatementUpdatePayload } from '@/services/statementService'
import type { InstallmentPlan, LiabilityStatement } from '@/types'
import { formatCurrency } from '@/utils/format'

export default function LiabilityStatementsPage() {
  const { liabilityId } = useParams<{ liabilityId: string }>()
  const [searchParams] = useSearchParams()
  const { liability, statements, plans, forecast, isLoading, error, refetch } = useStatementWorkspace(liabilityId)
  const [statementFormOpen, setStatementFormOpen] = useState(false)
  const [statementTarget, setStatementTarget] = useState<LiabilityStatement | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<LiabilityStatement | null>(null)
  const [planFormOpen, setPlanFormOpen] = useState(false)
  const [planTarget, setPlanTarget] = useState<InstallmentPlan | null>(null)

  useEffect(() => {
    if (searchParams.get('manual') === 'true') {
      setStatementTarget(null)
      setStatementFormOpen(true)
    }
  }, [searchParams])

  if (isLoading) return <AppShell><WorkspaceSkeleton /></AppShell>
  if (error || !liability || !liabilityId) {
    return <AppShell><div className="app-page"><Alert variant="destructive"><TriangleAlert /><AlertTitle>Statements unavailable</AlertTitle><AlertDescription>{error ?? 'Credit-card liability not found'}</AlertDescription></Alert></div></AppShell>
  }

  const saveStatement = async (payload: StatementPayload | StatementUpdatePayload, statementId?: string) => {
    if (statementId) await statementService.update(statementId, payload)
    else await statementService.create(liabilityId, payload as StatementPayload)
    toast.success(statementId ? 'Statement updated' : 'Statement added')
    await refetch()
  }
  const savePlan = async (payload: InstallmentPlanPayload | InstallmentPlanUpdatePayload, planId?: string) => {
    if (planId) await statementService.updatePlan(planId, payload)
    else await statementService.createPlan(liabilityId, payload as InstallmentPlanPayload)
    toast.success(planId ? 'Installment plan updated' : 'Installment plan added')
    await refetch()
  }
  const openManual = () => { setStatementTarget(null); setStatementFormOpen(true) }

  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          title={`${liability.name} Statements`}
          description="Upload statement PDFs, keep manual summaries and review installment plans."
          leading={<Button asChild variant="ghost" size="icon"><Link to="/liabilities" aria-label="Back to liabilities"><ArrowLeft /></Link></Button>}
          actions={<><Button asChild><Link to={`/liabilities/${liabilityId}/statements/import`}><FileUp />Upload PDF</Link></Button><Button variant="outline" onClick={openManual}><Keyboard />Enter manually</Button></>}
        />

        <Tabs defaultValue="statements">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TabsList><TabsTrigger value="statements">Statements</TabsTrigger><TabsTrigger value="installments">Installments</TabsTrigger></TabsList>
            <Button variant="ghost" size="sm" onClick={() => { setPlanTarget(null); setPlanFormOpen(true) }}><Plus />Add installment plan</Button>
          </div>
          <TabsContent value="statements" className="mt-4">
            {statements.length === 0 ? (
              <Empty className="data-surface">
                <EmptyHeader><EmptyMedia variant="icon"><FileText /></EmptyMedia><EmptyTitle>No statements yet</EmptyTitle><EmptyDescription>Upload a PDF for secure preflight or enter the statement summary manually.</EmptyDescription></EmptyHeader>
                <EmptyContent className="flex-row"><Button asChild><Link to={`/liabilities/${liabilityId}/statements/import`}><FileUp />Upload PDF</Link></Button><Button variant="outline" onClick={openManual}>Enter manually</Button></EmptyContent>
              </Empty>
            ) : (
              <div className="data-surface overflow-hidden">
                <Table className="block md:table">
                  <TableHeader className="hidden md:table-header-group"><TableRow><TableHead>Period</TableHead><TableHead>Due</TableHead><TableHead className="text-right">Balance</TableHead><TableHead>Status</TableHead><TableHead>Source</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                  <TableBody className="block md:table-row-group">
                    {statements.map((statement) => (
                      <TableRow key={statement.id} className="block border-b p-4 last:border-0 md:table-row md:p-0">
                        <TableCell className="block p-0 md:table-cell md:p-4"><p className="font-medium">{formatDate(statement.statement_period_start)} – {formatDate(statement.statement_period_end)}</p><p className="mt-1 text-xs text-muted-foreground">Statement {formatDate(statement.statement_date)}</p></TableCell>
                        <TableCell className="mt-3 flex justify-between p-0 text-sm md:mt-0 md:table-cell md:p-4"><span className="text-muted-foreground md:hidden">Due</span>{formatDate(statement.due_date)}</TableCell>
                        <TableCell className="mt-2 flex justify-between p-0 text-sm md:mt-0 md:table-cell md:p-4 md:text-right"><span className="text-muted-foreground md:hidden">Balance</span><div><p className="financial-value font-semibold">{formatCurrency(statement.statement_balance, statement.currency)}</p><p className="mt-1 text-xs text-muted-foreground">Min {formatCurrency(statement.minimum_payment, statement.currency)} · Future {formatCurrency(statement.remaining_installments_total, statement.currency)}</p></div></TableCell>
                        <TableCell className="mt-3 flex justify-between p-0 md:mt-0 md:table-cell md:p-4"><span className="text-sm text-muted-foreground md:hidden">Status</span><div className="flex flex-wrap gap-1"><Badge variant={statement.status === 'draft' ? 'outline' : 'secondary'}>{statement.status}</Badge><Badge variant={statement.is_reconciled ? 'secondary' : 'destructive'}>{statement.is_reconciled ? 'Reconciled' : 'Difference'}</Badge></div></TableCell>
                        <TableCell className="mt-2 flex justify-between p-0 text-sm md:mt-0 md:table-cell md:p-4"><span className="text-muted-foreground md:hidden">Source</span><span className="capitalize text-muted-foreground">{statement.source.replace('_', ' ')}</span></TableCell>
                        <TableCell className="mt-4 block p-0 md:mt-0 md:table-cell md:p-4"><div className="flex justify-end gap-1"><Button asChild variant="outline" size="sm"><Link to={`/liabilities/${liabilityId}/statements/${statement.id}`}>View</Link></Button>{statement.status === 'draft' ? <Button variant="ghost" size="sm" onClick={() => { setStatementTarget(statement); setStatementFormOpen(true) }}>Edit</Button> : null}<Button variant="ghost" size="icon" aria-label={`Delete statement ${statement.statement_date}`} onClick={() => setDeleteTarget(statement)}><Trash2 /></Button></div></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
          <TabsContent value="installments" className="mt-4">
            <InstallmentOverview plans={plans} forecast={forecast} onEdit={(plan) => { setPlanTarget(plan); setPlanFormOpen(true) }} onCancel={async (plan) => { try { await statementService.cancelPlan(plan.id); toast.success('Installment plan cancelled'); await refetch() } catch (caught) { toast.error(caught instanceof Error ? caught.message : 'Failed to cancel installment plan') } }} />
          </TabsContent>
        </Tabs>
      </div>
      <StatementFormDialog open={statementFormOpen} liability={liability} statement={statementTarget} onClose={() => { setStatementFormOpen(false); setStatementTarget(null) }} onSave={saveStatement as (payload: StatementPayload, statementId?: string) => Promise<void>} />
      <InstallmentPlanDialog open={planFormOpen} currency={liability.currency} plan={planTarget} onClose={() => { setPlanFormOpen(false); setPlanTarget(null) }} onSave={savePlan} />
      {deleteTarget ? <DeleteStatementItemDialog open title="Delete Statement" description="Deleting the statement will not reverse a balance previously applied to the liability." onClose={() => setDeleteTarget(null)} onConfirm={async () => { await statementService.delete(deleteTarget.id); toast.success('Statement deleted'); setDeleteTarget(null); await refetch() }} /> : null}
    </AppShell>
  )
}

function WorkspaceSkeleton() {
  return <div aria-label="Loading statements" className="app-page"><Skeleton className="h-10 w-64" /><Skeleton className="h-64 w-full" /></div>
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString()
}
