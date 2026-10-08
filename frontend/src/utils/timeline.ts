import type { TimelinePoint } from '@/types'
import { convertCurrency, type ForexRates } from '@/hooks/useForexRates'

export interface TransformedTimelinePoint {
  date: string
  value: number | null
}

export interface BuildTimelineOptions {
  referenceDate?: string | Date
}

export function formatUTCDate(d: Date): string {
  const year = d.getUTCFullYear()
  const month = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function parseUTCDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

export function addUTCDays(d: Date, days: number): Date {
  const res = new Date(d.getTime())
  res.setUTCDate(res.getUTCDate() + days)
  return res
}

export function getTodayISO(refDate?: string | Date): string {
  if (refDate) {
    if (typeof refDate === 'string') return refDate
    return formatUTCDate(refDate)
  }
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function convertSnapshotValue(
  pt: TimelinePoint,
  currency: string,
  rates: ForexRates = {},
): number | null {
  const tryValue = pt.net_worth_try ?? pt.total_value_try
  const usdValue = pt.net_worth_usd ?? pt.total_value_usd
  if (currency === 'USD') {
    return usdValue
  } else if (currency === 'TRY') {
    return tryValue
  } else {
    return convertCurrency(tryValue, 'TRY', currency, rates)
  }
}

/**
 * Builds a continuous daily calendar dataset for the dashboard timeline chart.
 * - Always spans the exact number of calendar days for the selected timeframe ending on today.
 * - Missing days are forward-filled with the latest known snapshot value.
 * - If a snapshot exists before the timeframe start, it seeds the forward fill.
 * - If no prior snapshot exists, values before the first actual snapshot remain null (no fake 0).
 * - For ALL (days === 1825), the range starts at the earliest actual snapshot date up to today.
 */
export function buildTimelinePoints(
  snapshots: TimelinePoint[],
  days: number,
  currency: string,
  rates: ForexRates = {},
  options?: BuildTimelineOptions,
): TransformedTimelinePoint[] {
  if (!snapshots || snapshots.length === 0) {
    return []
  }

  // Convert each snapshot to display currency and deduplicate by date (last wins)
  const converted = snapshots.map((pt) => ({
    date: pt.date,
    value: convertSnapshotValue(pt, currency, rates),
  }))

  converted.sort((a, b) => a.date.localeCompare(b.date))

  const snapshotMap = new Map<string, number | null>()
  for (const item of converted) {
    snapshotMap.set(item.date, item.value)
  }

  const todayStr = getTodayISO(options?.referenceDate)
  const latestSnapshotDate = converted[converted.length - 1].date
  // End date is today, or latest snapshot date if snapshot is in future relative to today
  const endDateStr = latestSnapshotDate > todayStr ? latestSnapshotDate : todayStr
  const endDate = parseUTCDate(endDateStr)

  let startDate: Date
  let startDateStr: string

  if (days === 1825) {
    // ALL: starts from earliest real snapshot date
    const earliestSnapshotDate = converted[0].date
    startDateStr = earliestSnapshotDate > endDateStr ? endDateStr : earliestSnapshotDate
    startDate = parseUTCDate(startDateStr)
  } else {
    // 1W (7), 1M (30), 3M (90), 6M (180), 1Y (365)
    // Exactly covers `days` calendar days ending on endDate [endDate - (days - 1), endDate]
    startDate = addUTCDays(endDate, -(days - 1))
    startDateStr = formatUTCDate(startDate)
  }

  // Determine initial forward-fill value before startDateStr
  // Look for the latest snapshot on or before startDateStr
  let currentValue: number | null = null
  for (let i = converted.length - 1; i >= 0; i--) {
    if (converted[i].date <= startDateStr) {
      currentValue = converted[i].value
      break
    }
  }

  const totalDays = Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1
  const result: TransformedTimelinePoint[] = []

  let curr = startDate
  for (let i = 0; i < totalDays; i++) {
    const dStr = formatUTCDate(curr)
    if (snapshotMap.has(dStr)) {
      currentValue = snapshotMap.get(dStr)!
    }
    result.push({
      date: dStr,
      value: currentValue,
    })
    curr = addUTCDays(curr, 1)
  }

  return result
}
