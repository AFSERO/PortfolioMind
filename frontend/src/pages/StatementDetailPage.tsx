import { useState } from 'react'
import { ArrowLeft, CheckCircle2, Pencil, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import ConfirmStatementDialog from '@/components/statements/ConfirmStatementDialog'
import DeleteStatementItemDialog from '@/components/statements/DeleteStatementItemDialog'
import InstallmentOverview from '@/components/statements/InstallmentOverview'
import StatementTransactionDialog from '@/components/statements/StatementTransactionDialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useStatementDetail } from '@/hooks/useStatements'
import { statementService } from '@/services/statementService'
import type { StatementTransactionPayload, StatementTransactionUpdatePayload } from '@/services/statementService'
import type { LiabilityStatement, StatementTransaction } from '@/types'
import { formatCurrency } from '@/utils/format'

export default function StatementDetailPage() {
  const { liabilityId, statementId } = useParams<{ liabilityId: string; statementId: string }>()
  const { statement, plans, forecast, isLoading, error, refetch } = useStatementDetail(liabilityId, statementId)
  const [transactionOpen, setTransactionOpen] = useState(false)
  const [transactionTarget, setTransactionTarget] = useState<StatementTransaction | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<StatementTransaction | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  if (isLoading) return <AppShell><div aria-label="Loading statement" className="app-page"><Skeleton className="h-10 w-64" /><Skeleton className="h-72 w-full" /></div></AppShell>
  if (error || !statement || !liabilityId || !statementId) return <AppShell><div className="app-page"><Alert variant="destructive"><TriangleAlert /><AlertTitle>Statement unavailable</AlertTitle><AlertDescription>{error ?? 'Statement not found'}</AlertDescription></Alert></div></AppShell>

  const saveTransaction = async (payload: StatementTransactionPayload | StatementTransactionUpdatePayload, transactionId?: string) => {
    if (transactionId) await statementService.updateTransaction(transactionId, payload)
    else await statementService.createTransaction(statementId, payload as StatementTransactionPayload)
    toast.success(transactionId ? 'Transaction updated' : 'Transaction added')
    await refetch()
  }
  const transactions = statement.transactions ?? []

  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          title="Statement Detail"
          eyebrow={`${formatDate(statement.statement_period_start)} – ${formatDate(statement.statement_period_end)}`}
          description={<span className="flex items-center gap-2"><Badge variant={statement.status === 'draft' ? 'outline' : 'secondary'}>{statement.status}</Badge><span>Source: {statement.source.replace('_', ' ')}</span></span>}
          leading={<Button asChild variant="ghost" size="icon"><Link to={`/liabilities/${liabilityId}/statements`} aria-label="Back to statements"><ArrowLeft /></Link></Button>}
          actions={statement.status === 'draft' ? <><Button variant="outline" onClick={() => { setTransactionTarget(null); setTransactionOpen(true) }}><Plus />Add Transaction</Button><Button onClick={() => setConfirmOpen(true)} disabled={!statement.is_reconciled}><CheckCircle2 />Confirm</Button></> : undefined}
        />

        {!statement.is_reconciled ? (
          <Alert variant="destructive"><TriangleAlert /><AlertTitle>Reconciliation required</AlertTitle><AlertDescription>The reported balance differs by {formatCurrency(statement.reconciliation_difference, statement.currency)}. Resolve the summary or transaction difference before confirmation.</AlertDescription></Alert>
        ) : (
          <Alert><CheckCircle2 className="text-positive" /><AlertTitle>Reconciled</AlertTitle><AlertDescription>Reported and calculated balances are within {formatCurrency(statement.reconciliation_tolerance, statement.currency)}.</AlertDescription></Alert>
        )}

        <StatementMetrics statement={statement} />

        <Tabs defaultValue="summary">
          <TabsList><TabsTrigger value="summary">Summary</TabsTrigger><TabsTrigger value="transactions">Transactions</TabsTrigger><TabsTrigger value="installments">Installments</TabsTrigger></TabsList>
          <TabsContent value="summary" className="mt-4">
            <Card className="shadow-card">
              <CardHeader><CardTitle>Statement Summary</CardTitle><CardDescription>Payments and refunds are stored positive and subtracted.</CardDescription></CardHeader>
              <CardContent className="grid gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
                <SummaryValue label="Previous Balance" amount={statement.previous_balance} currency={statement.currency} />
                <SummaryValue label="Purchases" amount={statement.purchases_total} currency={statement.currency} />
                <SummaryValue label="Payments" amount={statement.payments_total} currency={statement.currency} />
                <SummaryValue label="Refunds" amount={statement.refunds_total} currency={statement.currency} />
                <SummaryValue label="Fees" amount={statement.fees_total} currency={statement.currency} />
                <SummaryValue label="Interest" amount={statement.interest_total} currency={statement.currency} />
                <SummaryValue label="Summary Formula" amount={statement.summary_calculated_balance} currency={statement.currency} />
                <SummaryValue label="Summary Difference" amount={statement.summary_difference} currency={statement.currency} />
                <SummaryValue label="Transaction Difference" amount={statement.transaction_difference} currency={statement.currency} />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="transactions" className="mt-4">
            <Card className="shadow-card">
              <CardHeader><CardTitle>Statement Transactions</CardTitle><CardDescription>{transactions.length} line items</CardDescription></CardHeader>
              <CardContent>
                {transactions.length === 0 ? <p className="text-sm text-muted-foreground">No transactions. Reconciliation currently uses summary totals.</p> : (
                  <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Description</TableHead><TableHead>Type</TableHead><TableHead>Installment</TableHead><TableHead className="text-right">Amount</TableHead>{statement.status === 'draft' ? <TableHead className="text-right">Actions</TableHead> : null}</TableRow></TableHeader>
                    <TableBody>{transactions.map((transaction) => <TableRow key={transaction.id}><TableCell>{formatDate(transaction.transaction_date)}</TableCell><TableCell className="font-medium">{transaction.description}</TableCell><TableCell><Badge variant="outline">{transaction.transaction_type}</Badge></TableCell><TableCell>{transaction.installment_number ? `${transaction.installment_number}/${transaction.installment_count}` : '—'}</TableCell><TableCell className="financial-value text-right">{formatCurrency(transaction.amount, transaction.currency)}</TableCell>{statement.status === 'draft' ? <TableCell><div className="flex justify-end gap-1"><Button size="icon" variant="ghost" aria-label={`Edit ${transaction.description}`} onClick={() => { setTransactionTarget(transaction); setTransactionOpen(true) }}><Pencil /></Button><Button size="icon" variant="ghost" aria-label={`Delete ${transaction.description}`} onClick={() => setDeleteTarget(transaction)}><Trash2 /></Button></div></TableCell> : null}</TableRow>)}</TableBody>
                  </Table></div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="installments" className="mt-4"><InstallmentOverview plans={plans} forecast={forecast} /></TabsContent>
        </Tabs>
      </div>
      <StatementTransactionDialog open={transactionOpen} currency={statement.currency} plans={plans} transaction={transactionTarget} onClose={() => { setTransactionOpen(false); setTransactionTarget(null) }} onSave={saveTransaction} />
      <ConfirmStatementDialog open={confirmOpen} statement={statement} onClose={() => setConfirmOpen(false)} onConfirm={async (apply) => { await statementService.confirm(statement.id, apply); toast.success('Statement confirmed'); await refetch() }} />
      {deleteTarget ? <DeleteStatementItemDialog open title="Delete Transaction" description={`Delete ${deleteTarget.description}? Reconciliation will be recalculated.`} onClose={() => setDeleteTarget(null)} onConfirm={async () => { await statementService.deleteTransaction(deleteTarget.id); toast.success('Transaction deleted'); setDeleteTarget(null); await refetch() }} /> : null}
    </AppShell>
  )
}

function StatementMetrics({ statement }: { statement: LiabilityStatement }) {
  return <section aria-label="Statement totals" className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(20rem,0.9fr)]"><Card className="border-primary/20 shadow-card"><CardHeader><CardDescription>Reported Balance</CardDescription><CardTitle className="financial-value text-3xl">{formatCurrency(statement.reported_balance, statement.currency)}</CardTitle></CardHeader><CardContent><p className="text-sm text-muted-foreground">Due {formatDate(statement.due_date)} · Minimum {formatCurrency(statement.minimum_payment, statement.currency)}</p></CardContent></Card><Card className="shadow-card"><CardContent className="divide-y p-4"><MetricRow label="Calculated Balance" value={formatCurrency(statement.calculated_balance, statement.currency)} detail={`Source: ${statement.calculation_source}`} /><MetricRow label="Difference" value={formatCurrency(statement.reconciliation_difference, statement.currency)} detail={statement.is_reconciled ? 'Within tolerance' : 'Blocks confirmation'} /><MetricRow label="Future Installments" value={formatCurrency(statement.remaining_installments_total, statement.currency)} detail="Informational total" /></CardContent></Card></section>
}

function MetricRow({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"><div><p className="text-sm text-muted-foreground">{label}</p><p className="mt-0.5 text-xs text-muted-foreground">{detail}</p></div><p className="financial-value text-right font-semibold">{value}</p></div>
}

function SummaryValue({ label, amount, currency }: { label: string; amount: number | null; currency: string }) {
  return <div><p className="text-sm text-muted-foreground">{label}</p><p className="financial-value mt-1 font-medium">{amount == null ? 'Not available' : formatCurrency(amount, currency)}</p></div>
}

function formatDate(value: string) { return new Date(`${value}T00:00:00`).toLocaleDateString() }
