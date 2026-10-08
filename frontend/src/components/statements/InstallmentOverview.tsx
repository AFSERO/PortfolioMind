import { Pencil, XCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { InstallmentForecast, InstallmentPlan } from '@/types'
import { formatCurrency } from '@/utils/format'


interface Props {
  plans: InstallmentPlan[]
  forecast: InstallmentForecast | null
  onEdit?: (plan: InstallmentPlan) => void
  onCancel?: (plan: InstallmentPlan) => void
}

export default function InstallmentOverview({ plans, forecast, onEdit, onCancel }: Props) {
  return (
    <div className="flex flex-col gap-4">
      {forecast ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <ForecastCard title="Next Month" value={formatCurrency(forecast.next_month_total, forecast.currency)} />
          <ForecastCard title="Remaining Total" value={formatCurrency(forecast.remaining_total, forecast.currency)} />
          <ForecastCard title="Nearest Installment" value={forecast.nearest_installment_date ? formatDate(forecast.nearest_installment_date) : 'None'} />
          <ForecastCard title="Active Plans" value={String(forecast.active_plan_count)} />
        </div>
      ) : null}
      {forecast ? (
        <Card>
          <CardHeader>
            <CardTitle>Next Three Months</CardTitle>
            <CardDescription>Informational forecast; not included in current debt.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            {forecast.next_three_months.map((month) => (
              <div key={month.month} className="rounded-md border p-3">
                <p className="text-sm text-muted-foreground">{formatMonth(month.month)}</p>
                <p className="font-semibold">{formatCurrency(month.amount, forecast.currency)}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>Installment Plans</CardTitle>
          <CardDescription>Only monthly installments belong to individual statements.</CardDescription>
        </CardHeader>
        <CardContent>
          {plans.length === 0 ? (
            <p className="text-sm text-muted-foreground">No installment plans yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Purchase</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Monthly</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Remaining</TableHead>
                  <TableHead>Next</TableHead>
                  <TableHead>Completion</TableHead>
                  <TableHead>Status</TableHead>
                  {onEdit || onCancel ? <TableHead className="text-right">Actions</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {plans.map((plan) => (
                  <TableRow key={plan.id}>
                    <TableCell className="font-medium">{plan.description}</TableCell>
                    <TableCell>{formatCurrency(plan.original_amount, plan.currency)}</TableCell>
                    <TableCell>{formatCurrency(plan.monthly_installment_amount, plan.currency)}</TableCell>
                    <TableCell>{plan.completed_installment_count}/{plan.installment_count}</TableCell>
                    <TableCell>{plan.remaining_installment_count} · {formatCurrency(plan.remaining_amount, plan.currency)}</TableCell>
                    <TableCell>{plan.next_installment_date ? formatDate(plan.next_installment_date) : '—'}</TableCell>
                    <TableCell>{formatDate(plan.estimated_completion_date)}</TableCell>
                    <TableCell><Badge variant={plan.status === 'active' ? 'secondary' : 'outline'}>{plan.status}</Badge></TableCell>
                    {onEdit || onCancel ? (
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          {onEdit ? (
                            <Button size="icon" variant="ghost" aria-label={`Edit ${plan.description}`} onClick={() => onEdit(plan)}><Pencil /></Button>
                          ) : null}
                          {onCancel && plan.status === 'active' ? (
                            <Button size="icon" variant="ghost" aria-label={`Cancel ${plan.description}`} onClick={() => onCancel(plan)}><XCircle /></Button>
                          ) : null}
                        </div>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function ForecastCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle>{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString()
}

function formatMonth(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })
}
