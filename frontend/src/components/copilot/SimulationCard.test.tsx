import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SimulationCard } from './SimulationCard'
import type { SimulationResultData } from '@/types/copilot'

describe('SimulationCard', () => {
  const baseSellSimulation: SimulationResultData = {
    status: 'success',
    simulation_type: 'SELL',
    instrument: {
      symbol: 'THF',
      name: 'Tacirler Portfoy Hisse Senedi Fonu',
      asset_type: 'FUND',
      currency: 'TRY',
      is_owned: true,
    },
    assumptions: {
      price: 15.2,
      price_currency: 'TRY',
      price_source: 'CURRENT_REFERENCE_PRICE',
      fee: 0.0,
      affects_cash: true,
    },
    validation: {
      is_valid: true,
    },
    before: {
      total_value_base: 100000,
      total_invested_assets_base: 80000,
      base_currency: 'TRY',
      target_position: {
        quantity: 1000,
        position_value: 15200,
        position_value_base: 15200,
        weight_pct: 15.2,
      },
      cash: {
        balance: 20000,
        currency: 'TRY',
        total_cash_base: 20000,
        cash_weight_pct: 20.0,
        cash_account_exists: true,
      },
    },
    transaction: {
      transaction_type: 'SELL',
      quantity: 500,
      gross_value: 7600,
      gross_value_base: 7600,
      fee: 0,
      net_cash_delta: 7600,
      net_cash_delta_base: 7600,
      currency: 'TRY',
      is_affordable: true,
      cash_shortfall: 0,
    },
    after: {
      total_value_base: 100000,
      total_invested_assets_base: 72400,
      base_currency: 'TRY',
      target_position: {
        quantity: 500,
        position_value: 7600,
        position_value_base: 7600,
        weight_pct: 7.6,
      },
      cash: {
        balance: 27600,
        currency: 'TRY',
        total_cash_base: 27600,
        cash_weight_pct: 27.6,
        cash_account_exists: true,
      },
    },
    allocation_before: {
      by_type: [
        { asset_type: 'FUND', value: 80000, percentage: 80.0 },
        { asset_type: 'CASH', value: 20000, percentage: 20.0 },
      ],
      by_asset: [],
    },
    allocation_after: {
      by_type: [
        { asset_type: 'FUND', value: 72400, percentage: 72.4 },
        { asset_type: 'CASH', value: 27600, percentage: 27.6 },
      ],
      by_asset: [],
    },
    warnings: [],
  }

  it('renders SELL simulation with hypothetical badges, weight delta, cash delta, and no confirm buttons', () => {
    render(<SimulationCard simulation={baseSellSimulation} />)

    // Header badges
    expect(screen.getByText('Portföy Senaryo Simülasyonu')).toBeDefined()
    expect(screen.getByText('HİPOTETİK')).toBeDefined()
    expect(screen.getByText('Mutasyon Yok')).toBeDefined()
    expect(screen.getByText('SATIŞ SENARYOSU')).toBeDefined()
    expect(screen.getByText('THF')).toBeDefined()

    // Weight and cash changes
    expect(screen.getByText('Varlık Ağırlığı')).toBeDefined()
    expect(screen.getByText('Nakit Oranı')).toBeDefined()
    expect(screen.getByText('Toplam Portföy')).toBeDefined()

    // Pure information note
    expect(
      screen.getByText('Bu senaryo veritabanında saklanmaz ve portföyünüze kaydedilmez.')
    ).toBeDefined()

    // Strictly NO buttons (no confirm, no cancel, no execute)
    expect(screen.queryByRole('button', { name: /onayla/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /iptal/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /uygula/i })).toBeNull()
  })

  it('renders cash shortfall warning when BUY scenario is not affordable', () => {
    const unaffordableBuy: SimulationResultData = {
      ...baseSellSimulation,
      simulation_type: 'BUY',
      transaction: {
        transaction_type: 'BUY',
        quantity: 100,
        gross_value: 50000,
        gross_value_base: 50000,
        fee: 0,
        net_cash_delta: -50000,
        net_cash_delta_base: -50000,
        currency: 'TRY',
        is_affordable: false,
        cash_shortfall: 30000,
      },
    }

    render(<SimulationCard simulation={unaffordableBuy} />)
    expect(screen.getByText('ALIŞ SENARYOSU')).toBeDefined()
    expect(screen.getByText(/Nakit Bakiyesi Yetersiz/)).toBeDefined()
    expect(screen.getByText('Ek Fonlama Gerekir')).toBeDefined()
  })

  it('renders scenario warning banner when validation fails', () => {
    const invalidSim: SimulationResultData = {
      ...baseSellSimulation,
      validation: {
        is_valid: false,
        reason: 'INSUFFICIENT_HOLDING',
        message: 'Portföyünüzde yeterli miktarda THF bulunmamaktadır.',
      },
    }

    render(<SimulationCard simulation={invalidSim} />)
    expect(screen.getByText('Senaryo Uyarısı:')).toBeDefined()
    expect(
      screen.getByText('Portföyünüzde yeterli miktarda THF bulunmamaktadır.')
    ).toBeDefined()
  })
})
