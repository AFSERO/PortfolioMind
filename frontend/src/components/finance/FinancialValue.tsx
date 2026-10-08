import { formatCurrency } from '@/utils/format'
import { cn } from '@/utils/cn'

interface FinancialValueProps {
  amount: number | null | undefined
  currency: string
  sentiment?: 'neutral' | 'positive' | 'negative' | 'auto'
  className?: string
}

export default function FinancialValue({
  amount,
  currency,
  sentiment = 'neutral',
  className,
}: FinancialValueProps) {
  const resolved = sentiment === 'auto'
    ? (amount ?? 0) < 0 ? 'negative' : 'positive'
    : sentiment
  return (
    <span
      className={cn(
        'financial-value font-semibold',
        resolved === 'positive' && 'text-positive',
        resolved === 'negative' && 'text-negative',
        amount == null && 'text-muted-foreground',
        className,
      )}
    >
      {amount == null ? 'Unavailable' : formatCurrency(amount, currency)}
    </span>
  )
}
