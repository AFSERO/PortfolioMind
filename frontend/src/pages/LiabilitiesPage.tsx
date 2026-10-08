import { useMemo, useState } from 'react'
import { AlertTriangle, Ellipsis, FileUp, Pencil, Plus, ReceiptText, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import FinancialValue from '@/components/finance/FinancialValue'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import LiabilityDeleteDialog from '@/components/liabilities/LiabilityDeleteDialog'
import LiabilityFormDialog from '@/components/liabilities/LiabilityFormDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { convertCurrency, useForexRates } from '@/hooks/useForexRates'
import { useLiabilities } from '@/hooks/useLiabilities'
import type { LiabilityCreatePayload, LiabilityUpdatePayload } from '@/services/liabilityService'
import { useAuthStore } from '@/store'
import type { Liability, LiabilityType } from '@/types'
import { formatCurrency } from '@/utils/format'

const TYPE_LABELS: Record<LiabilityType, string> = {
  credit_card: 'Credit Card',
  personal_loan: 'Personal Loan',
  mortgage: 'Mortgage',
  student_loan: 'Student Loan',
  other: 'Other',
}

export default function LiabilitiesPage() {
  const { liabilities, isLoading, error, refetch, createLiability, updateLiability, deleteLiability } = useLiabilities()
  const { rates } = useForexRates()
  const { user } = useAuthStore()
  const baseCurrency = user?.base_currency ?? 'TRY'
  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Liability | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Liability | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const rows = useMemo(() => liabilities.map((liability) => ({
    liability,
    baseValue: convertCurrency(liability.current_balance, liability.currency, baseCurrency, rates),
  })), [baseCurrency, liabilities, rates])

  const summary = useMemo(() => {
    const active = rows.filter(({ liability }) => liability.is_active)
    const cards = active.filter(({ liability }) => liability.liability_type === 'credit_card')
    const safeSum = (items: typeof rows) => items.every(({ baseValue }) => baseValue != null)
      ? items.reduce((total, { baseValue }) => total + (baseValue ?? 0), 0)
      : null
    return { total: safeSum(active), cards: safeSum(cards), activeCount: active.length }
  }, [rows])

  const openCreate = () => { setEditTarget(null); setFormOpen(true) }
  const openEdit = (liability: Liability) => { setEditTarget(liability); setFormOpen(true) }

  const handleSave = async (payload: LiabilityCreatePayload | LiabilityUpdatePayload, liabilityId?: string) => {
    if (liabilityId) await updateLiability(liabilityId, payload as LiabilityUpdatePayload)
    else await createLiability(payload as LiabilityCreatePayload)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await deleteLiability(deleteTarget.id)
      toast.success(`${deleteTarget.name} deleted`)
      setDeleteTarget(null)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Failed to delete liability')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <AppShell>
      <div className="app-page">
        <PageHeader
          title="Liabilities"
          description="Track debt balances and manage credit-card statements without mixing currencies."
          actions={<Button onClick={openCreate}><Plus aria-hidden="true" />Add Liability</Button>}
        />

        {!isLoading && !error && rows.length > 0 ? (
          <section aria-label="Liability summary" className="grid gap-3 sm:grid-cols-3">
            <SummaryMetric label="Total debt" amount={summary.total} currency={baseCurrency} detail="Active liabilities" negative />
            <SummaryMetric label="Credit cards" amount={summary.cards} currency={baseCurrency} detail="Active card balances" negative />
            <Card className="shadow-card"><CardContent className="p-4"><p className="text-sm text-muted-foreground">Active records</p><p className="financial-value mt-2 text-2xl font-semibold">{summary.activeCount}</p><p className="mt-1 text-xs text-muted-foreground">Inactive records excluded</p></CardContent></Card>
          </section>
        ) : null}

        {error ? (
          <Card role="alert">
            <CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle />Liabilities unavailable</CardTitle><CardDescription>{error}</CardDescription></CardHeader>
            <CardContent><Button variant="outline" onClick={() => void refetch()}>Try Again</Button></CardContent>
          </Card>
        ) : isLoading ? <LoadingTable /> : rows.length === 0 ? (
          <Card className="shadow-card">
            <CardHeader><CardTitle>No liabilities yet</CardTitle><CardDescription>Add a credit card, loan, mortgage, or other debt to calculate your real net worth.</CardDescription></CardHeader>
            <CardContent><Button onClick={openCreate}><Plus />Add your first liability</Button></CardContent>
          </Card>
        ) : (
          <div className="data-surface overflow-hidden">
            <Table className="block md:table">
              <TableHeader className="hidden md:table-header-group">
                <TableRow><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead className="text-right">Current Debt</TableHead><TableHead className="text-right">In {baseCurrency}</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Actions</TableHead></TableRow>
              </TableHeader>
              <TableBody className="block md:table-row-group">
                {rows.map(({ liability, baseValue }) => (
                  <TableRow key={liability.id} className="block border-b p-4 last:border-0 md:table-row md:p-0">
                    <TableCell className="block p-0 md:table-cell md:p-4">
                      <p className="font-medium">{liability.name}</p>
                      {liability.due_date ? <p className="mt-1 text-xs text-muted-foreground">Due {new Date(`${liability.due_date}T00:00:00`).toLocaleDateString()}</p> : null}
                    </TableCell>
                    <TableCell className="mt-3 flex justify-between p-0 text-sm text-muted-foreground md:mt-0 md:table-cell md:p-4"><span className="md:hidden">Type</span>{TYPE_LABELS[liability.liability_type]}</TableCell>
                    <TableCell className="mt-2 flex justify-between p-0 text-sm md:mt-0 md:table-cell md:p-4 md:text-right"><span className="text-muted-foreground md:hidden">Current debt</span><span className="financial-value font-medium">{formatCurrency(liability.current_balance, liability.currency)}</span></TableCell>
                    <TableCell className="mt-2 flex justify-between p-0 text-sm md:mt-0 md:table-cell md:p-4 md:text-right"><span className="text-muted-foreground md:hidden">In {baseCurrency}</span><FinancialValue amount={baseValue} currency={baseCurrency} className="text-sm text-foreground" /></TableCell>
                    <TableCell className="mt-3 flex justify-between p-0 md:mt-0 md:table-cell md:p-4"><span className="text-sm text-muted-foreground md:hidden">Status</span><Badge variant={liability.is_active ? 'secondary' : 'outline'}>{liability.is_active ? 'Active' : 'Inactive'}</Badge></TableCell>
                    <TableCell className="mt-4 block p-0 md:mt-0 md:table-cell md:p-4">
                      <div className="flex items-center justify-end gap-2">
                        {liability.liability_type === 'credit_card' ? (
                          <Button asChild size="sm"><Link to={`/liabilities/${liability.id}/statements/import`}><FileUp />Upload PDF</Link></Button>
                        ) : null}
                        <LiabilityActions liability={liability} onEdit={() => openEdit(liability)} onDelete={() => setDeleteTarget(liability)} />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      <LiabilityFormDialog open={formOpen} liability={editTarget} onClose={() => { setFormOpen(false); setEditTarget(null) }} onSave={handleSave} />
      <LiabilityDeleteDialog open={deleteTarget != null} liabilityName={deleteTarget?.name ?? ''} isDeleting={isDeleting} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete} />
    </AppShell>
  )
}

function SummaryMetric({ label, amount, currency, detail, negative = false }: { label: string; amount: number | null; currency: string; detail: string; negative?: boolean }) {
  return <Card className="shadow-card"><CardContent className="p-4"><p className="text-sm text-muted-foreground">{label}</p><FinancialValue amount={amount} currency={currency} sentiment={negative ? 'negative' : 'neutral'} className="mt-2 block text-2xl" /><p className="mt-1 text-xs text-muted-foreground">{amount == null ? 'Exchange rate unavailable' : detail}</p></CardContent></Card>
}

function LiabilityActions({ liability, onEdit, onDelete }: { liability: Liability; onEdit: () => void; onDelete: () => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild><Button variant="outline" size="icon" aria-label={`Actions for ${liability.name}`}><Ellipsis /></Button></DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {liability.liability_type === 'credit_card' ? (
          <DropdownMenuItem asChild><Link to={`/liabilities/${liability.id}/statements`}><ReceiptText />View statements</Link></DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onSelect={onEdit}><Pencil />Edit</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={onDelete} aria-label={`Delete ${liability.name}`}><Trash2 />Delete</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function LoadingTable() {
  return <div aria-label="Loading liabilities" className="data-surface flex flex-col gap-3 p-4">{[0, 1, 2, 3].map((row) => <Skeleton key={row} className="h-14 w-full" />)}</div>
}
