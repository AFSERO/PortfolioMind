import { useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, ArrowLeftRight, TrendingUp, TrendingDown, Banknote } from 'lucide-react'
import AppShell from '@/components/layout/AppShell'
import PageHeader from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import DepositDialog from '@/components/cash/DepositDialog'
import WithdrawDialog from '@/components/cash/WithdrawDialog'
import TransferDialog from '@/components/cash/TransferDialog'
import { useCashAccounts } from '@/hooks/useCashAccounts'
import { formatCurrency } from '@/utils/format'
import { cn } from '@/utils/cn'
import type { CashMovementType } from '@/types'

const DISPLAY_CURRENCIES = ['TRY', 'USD', 'EUR']

type DialogState =
  | { type: 'deposit'; currency: string }
  | { type: 'withdraw'; currency: string }
  | { type: 'transfer'; from: string }
  | null

function movementLabel(t: CashMovementType): string {
  const labels: Record<CashMovementType, string> = {
    DEPOSIT: 'Deposit',
    WITHDRAW: 'Withdrawal',
    TRANSFER_IN: 'Transfer In',
    TRANSFER_OUT: 'Transfer Out',
    BUY: 'Asset Purchase',
    SELL: 'Asset Sale',
    ADJUSTMENT: 'Adjustment',
  }
  return labels[t] ?? t
}

function movementSign(t: CashMovementType): '+' | '-' {
  return ['DEPOSIT', 'TRANSFER_IN', 'SELL'].includes(t) ? '+' : '-'
}

export default function CashPage() {
  const { accounts, movements, isLoading, error, deposit, withdraw, transfer } = useCashAccounts()
  const [dialog, setDialog] = useState<DialogState>(null)

  const accountByCurrency = (cur: string) => accounts.find((a) => a.currency === cur) ?? null

  const currencySymbol = (cur: string) => {
    const symbols: Record<string, string> = { TRY: '₺', USD: '$', EUR: '€', GBP: '£' }
    return symbols[cur] ?? cur
  }

  return (
    <AppShell>
      <div className="app-page max-w-4xl">
        <PageHeader
          title="Cash Accounts"
          description="Manage cash balances and movements."
          actions={<Button
            onClick={() => setDialog({ type: 'transfer', from: 'TRY' })}
            variant="outline"
          >
            <ArrowLeftRight className="h-4 w-4" />
            Transfer
          </Button>}
        />

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Account cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {isLoading
            ? [0, 1, 2].map((i) => (
                <div key={i} className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-3">
                  <Skeleton className="h-4 w-16 bg-slate-800" />
                  <Skeleton className="h-8 w-32 bg-slate-800" />
                  <div className="flex gap-2">
                    <Skeleton className="h-8 flex-1 bg-slate-800" />
                    <Skeleton className="h-8 flex-1 bg-slate-800" />
                  </div>
                </div>
              ))
            : DISPLAY_CURRENCIES.map((cur) => {
                const acct = accountByCurrency(cur)
                const balance = acct?.balance ?? 0
                const isPositive = balance >= 0

                return (
                  <div key={cur} className="rounded-xl border border-slate-800 bg-slate-900 p-5 flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300 font-bold text-sm">
                          {currencySymbol(cur)}
                        </span>
                        <span className="text-sm font-semibold text-slate-300">{cur}</span>
                      </div>
                      <Banknote className="h-4 w-4 text-slate-600" />
                    </div>

                    <div>
                      <p className={cn('text-2xl font-bold leading-none', isPositive ? 'text-slate-100' : 'text-loss')}>
                        {formatCurrency(balance, cur)}
                      </p>
                      {!acct && (
                        <p className="text-xs text-slate-600 mt-1">No account yet</p>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => setDialog({ type: 'deposit', currency: cur })}
                        className="flex-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-600/30 gap-1.5"
                        variant="outline"
                      >
                        <ArrowDownLeft className="h-3.5 w-3.5" />
                        Deposit
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => setDialog({ type: 'withdraw', currency: cur })}
                        className="flex-1 bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-600/20 gap-1.5"
                        variant="outline"
                        disabled={balance <= 0}
                      >
                        <ArrowUpRight className="h-3.5 w-3.5" />
                        Withdraw
                      </Button>
                    </div>
                  </div>
                )
              })}
        </div>

        {/* Cash Movement History */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-800">
            <h2 className="text-sm font-semibold text-slate-300">Movement History</h2>
          </div>

          {isLoading ? (
            <div className="p-5 space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-8 w-8 rounded-lg bg-slate-800" />
                    <div className="space-y-1">
                      <Skeleton className="h-3 w-24 bg-slate-800" />
                      <Skeleton className="h-3 w-16 bg-slate-800" />
                    </div>
                  </div>
                  <Skeleton className="h-4 w-20 bg-slate-800" />
                </div>
              ))}
            </div>
          ) : movements.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Banknote className="h-10 w-10 text-slate-700 mb-3" />
              <p className="text-sm text-slate-500">No movements yet</p>
              <p className="text-xs text-slate-600 mt-1">Deposits, withdrawals and transfers will appear here</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {movements.map((m) => {
                const sign = movementSign(m.movement_type)
                const isCredit = sign === '+'
                return (
                  <div key={m.id} className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/40 transition-colors">
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          'flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0',
                          isCredit ? 'bg-emerald-500/10' : 'bg-red-500/10',
                        )}
                      >
                        {isCredit
                          ? <TrendingUp className="h-4 w-4 text-emerald-400" />
                          : <TrendingDown className="h-4 w-4 text-red-400" />
                        }
                      </span>
                      <div>
                        <p className="text-sm font-medium text-slate-200">{movementLabel(m.movement_type)}</p>
                        <p className="text-xs text-slate-500">
                          {new Date(m.created_at).toLocaleDateString('tr-TR', {
                            year: 'numeric', month: 'short', day: 'numeric',
                          })}
                          {m.notes && <> · {m.notes}</>}
                        </p>
                      </div>
                    </div>
                    <span className={cn('text-sm font-semibold tabular-nums', isCredit ? 'text-profit' : 'text-loss')}>
                      {sign}{formatCurrency(m.amount, m.currency)}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <DepositDialog
        open={dialog?.type === 'deposit'}
        onClose={() => setDialog(null)}
        account={dialog?.type === 'deposit' ? accountByCurrency(dialog.currency) : null}
        currency={dialog?.type === 'deposit' ? dialog.currency : 'TRY'}
        onDeposit={deposit}
      />

      <WithdrawDialog
        open={dialog?.type === 'withdraw'}
        onClose={() => setDialog(null)}
        account={dialog?.type === 'withdraw' ? accountByCurrency(dialog.currency) : null}
        currency={dialog?.type === 'withdraw' ? dialog.currency : 'TRY'}
        onWithdraw={withdraw}
      />

      <TransferDialog
        open={dialog?.type === 'transfer'}
        onClose={() => setDialog(null)}
        accounts={accounts}
        defaultFromCurrency={dialog?.type === 'transfer' ? dialog.from : 'TRY'}
        onTransfer={transfer}
      />
    </AppShell>
  )
}
