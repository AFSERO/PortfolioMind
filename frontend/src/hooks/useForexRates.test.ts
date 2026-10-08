import { describe, expect, it } from 'vitest'

import { convertCurrency } from '@/hooks/useForexRates'


describe('convertCurrency', () => {
  it('keeps same-currency values one-to-one', () => {
    expect(convertCurrency(125, 'TRY', 'TRY', {})).toBe(125)
  })

  it('uses a valid direct rate', () => {
    expect(convertCurrency(100, 'USD', 'TRY', { 'USD/TRY': 42 })).toBe(4200)
  })

  it.each([
    [{}, 'missing'],
    [{ 'USD/TRY': 0 }, 'zero'],
    [{ 'USD/TRY': -1 }, 'negative'],
  ])('returns unavailable for a %s cross rate', (rates, _label) => {
    expect(convertCurrency(100, 'USD', 'TRY', rates)).toBeNull()
  })
})
