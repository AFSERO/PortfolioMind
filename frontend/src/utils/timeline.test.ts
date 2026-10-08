import { describe, expect, it } from 'vitest'
import { buildTimelinePoints, formatUTCDate, parseUTCDate, addUTCDays } from './timeline'
import type { TimelinePoint } from '@/types'

function makeSnapshot(
  date: string,
  tryValue: number,
  usdValue = tryValue / 30,
  overrides: Partial<TimelinePoint> = {},
): TimelinePoint {
  return {
    date,
    total_value_try: tryValue,
    total_value_usd: usdValue,
    total_assets_try: tryValue,
    total_assets_usd: usdValue,
    total_liabilities_try: 0,
    total_liabilities_usd: 0,
    net_worth_try: tryValue,
    net_worth_usd: usdValue,
    value_semantics: 'net_worth',
    ...overrides,
  }
}

describe('timeline transformation utility', () => {
  const refDate = '2026-09-30'

  it('correctly formats, parses, and shifts UTC dates', () => {
    const d = parseUTCDate('2026-09-30')
    expect(formatUTCDate(d)).toBe('2026-09-30')
    const prev = addUTCDays(d, -6)
    expect(formatUTCDate(prev)).toBe('2026-09-24')
  })

  it('1W produces exactly 7 calendar points from Sep 24 to Sep 30', () => {
    const snapshots = [
      makeSnapshot('2026-09-29', 380000),
      makeSnapshot('2026-09-30', 382000),
    ]

    const points = buildTimelinePoints(snapshots, 7, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(7)
    expect(points[0].date).toBe('2026-09-24')
    expect(points[6].date).toBe('2026-09-30')
    expect(points.map((p) => p.date)).toEqual([
      '2026-09-24',
      '2026-09-25',
      '2026-09-26',
      '2026-09-27',
      '2026-09-28',
      '2026-09-29',
      '2026-09-30',
    ])
  })

  it('x-axis starts at range beginning even if the first snapshot is in the middle of range', () => {
    const snapshots = [makeSnapshot('2026-09-27', 382000)]

    const points = buildTimelinePoints(snapshots, 7, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(7)
    expect(points[0].date).toBe('2026-09-24')
    expect(points[0].value).toBeNull()
    expect(points[1].date).toBe('2026-09-25')
    expect(points[1].value).toBeNull()
    expect(points[2].date).toBe('2026-09-26')
    expect(points[2].value).toBeNull()
    expect(points[3].date).toBe('2026-09-27')
    expect(points[3].value).toBe(382000)
    expect(points[4].date).toBe('2026-09-28')
    expect(points[4].value).toBe(382000)
    expect(points[5].date).toBe('2026-09-29')
    expect(points[5].value).toBe(382000)
    expect(points[6].date).toBe('2026-09-30')
    expect(points[6].value).toBe(382000)
  })

  it('forward-fills missing internal days with the last known snapshot value', () => {
    const snapshots = [
      makeSnapshot('2026-09-24', 380000),
      makeSnapshot('2026-09-27', 382000),
    ]

    const points = buildTimelinePoints(snapshots, 7, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(7)
    expect(points[0]).toEqual({ date: '2026-09-24', value: 380000 })
    expect(points[1]).toEqual({ date: '2026-09-25', value: 380000 })
    expect(points[2]).toEqual({ date: '2026-09-26', value: 380000 })
    expect(points[3]).toEqual({ date: '2026-09-27', value: 382000 })
    expect(points[4]).toEqual({ date: '2026-09-28', value: 382000 })
    expect(points[5]).toEqual({ date: '2026-09-29', value: 382000 })
    expect(points[6]).toEqual({ date: '2026-09-30', value: 382000 })
  })

  it('uses last snapshot before range start as forward-fill seed value', () => {
    const snapshots = [
      makeSnapshot('2026-09-20', 375000),
      makeSnapshot('2026-09-27', 382000),
    ]

    const points = buildTimelinePoints(snapshots, 7, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(7)
    expect(points[0]).toEqual({ date: '2026-09-24', value: 375000 })
    expect(points[1]).toEqual({ date: '2026-09-25', value: 375000 })
    expect(points[2]).toEqual({ date: '2026-09-26', value: 375000 })
    expect(points[3]).toEqual({ date: '2026-09-27', value: 382000 })
    expect(points[4]).toEqual({ date: '2026-09-28', value: 382000 })
    expect(points[5]).toEqual({ date: '2026-09-29', value: 382000 })
    expect(points[6]).toEqual({ date: '2026-09-30', value: 382000 })
  })

  it('does NOT create fake 0 when no prior snapshot exists before the first data point', () => {
    const snapshots = [makeSnapshot('2026-09-28', 100000)]

    const points = buildTimelinePoints(snapshots, 7, 'TRY', {}, { referenceDate: refDate })

    const daysBefore = points.slice(0, 4)
    expect(daysBefore.map((p) => p.value)).toEqual([null, null, null, null])
    expect(daysBefore.some((p) => p.value === 0)).toBe(false)
  })

  it('1M timeframe starts at the correct calendar boundary (30 days total)', () => {
    const snapshots = [makeSnapshot('2026-09-30', 200000)]

    const points = buildTimelinePoints(snapshots, 30, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(30)
    expect(points[0].date).toBe('2026-09-01')
    expect(points[29].date).toBe('2026-09-30')
  })

  it('3M timeframe starts at the correct calendar boundary (90 days total)', () => {
    const snapshots = [makeSnapshot('2026-09-30', 200000)]

    const points = buildTimelinePoints(snapshots, 90, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(90)
    expect(points[0].date).toBe('2026-07-03')
    expect(points[89].date).toBe('2026-09-30')
  })

  it('6M timeframe starts at the correct calendar boundary (180 days total)', () => {
    const snapshots = [makeSnapshot('2026-09-30', 200000)]

    const points = buildTimelinePoints(snapshots, 180, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(180)
    expect(points[0].date).toBe('2026-04-04')
    expect(points[179].date).toBe('2026-09-30')
  })

  it('1Y timeframe starts at the correct calendar boundary (365 days total)', () => {
    const snapshots = [makeSnapshot('2026-09-30', 200000)]

    const points = buildTimelinePoints(snapshots, 365, 'TRY', {}, { referenceDate: refDate })

    expect(points).toHaveLength(365)
    expect(points[0].date).toBe('2025-10-01')
    expect(points[364].date).toBe('2026-09-30')
  })

  it('ALL starts at the earliest actual snapshot date and ends at today', () => {
    const snapshots = [
      makeSnapshot('2026-09-15', 350000),
      makeSnapshot('2026-09-27', 382000),
    ]

    const points = buildTimelinePoints(snapshots, 1825, 'TRY', {}, { referenceDate: refDate })

    // From 2026-09-15 to 2026-09-30 = 16 days
    expect(points).toHaveLength(16)
    expect(points[0].date).toBe('2026-09-15')
    expect(points[0].value).toBe(350000)
    expect(points[15].date).toBe('2026-09-30')
    expect(points[15].value).toBe(382000)
    // Internal forward fill
    expect(points[1].date).toBe('2026-09-16')
    expect(points[1].value).toBe(350000)
  })

  it('preserves accurate currency conversion across forward fill', () => {
    const snapshots = [
      makeSnapshot('2026-09-24', 40000, 1000),
      makeSnapshot('2026-09-27', 80000, 2000),
    ]

    const usdPoints = buildTimelinePoints(snapshots, 7, 'USD', {}, { referenceDate: refDate })
    expect(usdPoints[0]).toEqual({ date: '2026-09-24', value: 1000 })
    expect(usdPoints[1]).toEqual({ date: '2026-09-25', value: 1000 })
    expect(usdPoints[3]).toEqual({ date: '2026-09-27', value: 2000 })
    expect(usdPoints[6]).toEqual({ date: '2026-09-30', value: 2000 })

    const eurRates = { 'TRY/EUR': 0.025 }
    const eurPoints = buildTimelinePoints(snapshots, 7, 'EUR', eurRates, { referenceDate: refDate })
    expect(eurPoints[0].value).toBe(1000) // 40000 * 0.025
    expect(eurPoints[3].value).toBe(2000) // 80000 * 0.025
  })

  it('returns empty array when snapshots input is empty', () => {
    expect(buildTimelinePoints([], 7, 'TRY', {})).toEqual([])
  })
})
