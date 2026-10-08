/**
 * Formats a monetary value with proper locale-specific separators.
 * TRY uses tr-TR locale (e.g. 1.234,56 ₺).
 */
export function formatCurrency(
  value: number | null,
  currency: string,
  locale = 'tr-TR',
): string {
  if (value == null) return 'Bilinmiyor'
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Returns a CSS class name for profit/loss coloring.
 * Uses the --profit / --loss CSS variables defined in index.css.
 */
export function plColorClass(value: number | null): string {
  if (value == null) return 'text-muted-foreground'
  return value >= 0 ? 'text-profit' : 'text-loss'
}

/** Formats a percentage, e.g. 12.34 → "+12.34%" */
export function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

