import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ActionProposalCard } from './ActionProposalCard'
import type { ActionProposal } from '@/types/copilot'

describe('ActionProposalCard', () => {
  const baseTransactionProposal: ActionProposal = {
    id: 'prop-buy-1',
    user_id: 'user-1',
    conversation_id: 'conv-1',
    action_type: 'TRANSACTION_RECORD',
    permission_level: 'LEVEL_2_CONFIRMATION',
    status: 'PENDING',
    parameters: {
      symbol: 'THYAO.IS',
      transaction_type: 'BUY',
      quantity: 50,
      price: 310.5,
      currency: 'TRY',
      transaction_date: '2026-10-01',
    },
    expected_impact: {
      action: 'BUY',
      symbol: 'THYAO.IS',
      previous_quantity: 0,
      new_quantity: 50,
      total_amount: 15525,
      cash_delta: -15525,
      currency: 'TRY',
    },
    human_readable_summary: '50 adet THYAO.IS için 310.50 TRY fiyattan portföy ALIŞ kaydı oluşturulacak.',
    warnings: [],
    idempotency_key: 'idem-1',
    created_at: new Date().toISOString(),
  }

  it('renders BUY transaction proposal with impact details, disclaimer and confirmation buttons', () => {
    const handleConfirm = vi.fn()
    const handleCancel = vi.fn()

    render(
      <ActionProposalCard
        proposal={baseTransactionProposal}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    )

    // Action metadata label & status
    expect(screen.getByText('PORTFÖY ALIŞ KAYDI')).toBeDefined()
    expect(screen.getByText('Onay Bekliyor')).toBeDefined()
    expect(screen.getByText(baseTransactionProposal.human_readable_summary)).toBeDefined()

    // Position & cash details
    expect(screen.getByText('0 → 50')).toBeDefined()
    expect(screen.getAllByText(/15.525,00 TRY|15,525.00 TRY/).length).toBe(2)
    expect(screen.getByText('2026-10-01')).toBeDefined()

    // Product boundary disclaimer
    expect(
      screen.getByText(
        'Bu işlem bir borsa/aracı kurum emri değildir; yalnızca PortfolioMind içi portföy kayıtlarınızı günceller.'
      )
    ).toBeDefined()

    // Action buttons
    const confirmBtn = screen.getByRole('button', { name: /Onayla ve Uygula/i })
    const cancelBtn = screen.getByRole('button', { name: /İptal Et/i })
    expect(confirmBtn).toBeDefined()
    expect(cancelBtn).toBeDefined()

    fireEvent.click(confirmBtn)
    expect(handleConfirm).toHaveBeenCalledWith('prop-buy-1')

    fireEvent.click(cancelBtn)
    expect(handleCancel).toHaveBeenCalledWith('prop-buy-1')
  })

  it('renders SELL transaction proposal with positive cash delta', () => {
    const sellProposal: ActionProposal = {
      ...baseTransactionProposal,
      id: 'prop-sell-1',
      parameters: {
        symbol: 'THYAO.IS',
        transaction_type: 'SELL',
        quantity: 20,
        price: 320,
        currency: 'TRY',
      },
      expected_impact: {
        action: 'SELL',
        symbol: 'THYAO.IS',
        previous_quantity: 50,
        new_quantity: 30,
        total_amount: 6400,
        cash_delta: 6400,
        currency: 'TRY',
      },
      human_readable_summary: '20 adet THYAO.IS için 320.00 TRY fiyattan portföy SATIŞ kaydı oluşturulacak.',
    }

    render(
      <ActionProposalCard
        proposal={sellProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('PORTFÖY SATIŞ KAYDI')).toBeDefined()
    expect(screen.getByText('50 → 30')).toBeDefined()
    expect(screen.getByText(/\+.*6.400|\+.*6,400/)).toBeDefined()
  })

  it('renders WATCHLIST_CHANGE proposal', () => {
    const watchlistProposal: ActionProposal = {
      id: 'prop-watch-1',
      user_id: 'user-1',
      action_type: 'WATCHLIST_CHANGE',
      permission_level: 'LEVEL_2_CONFIRMATION',
      status: 'PENDING',
      parameters: {
        symbol: 'THF',
        action: 'ADD',
      },
      expected_impact: {
        action: 'ADD',
        symbol: 'THF',
      },
      human_readable_summary: 'THF izleme listesine eklenecek.',
      warnings: [],
      idempotency_key: 'idem-watch-1',
      created_at: new Date().toISOString(),
    }

    render(
      <ActionProposalCard
        proposal={watchlistProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('İZLEME LİSTESİ EYLEMİ')).toBeDefined()
    expect(screen.getByText('Ekle (THF)')).toBeDefined()
  })

  it('renders DECISION_NOTE proposal', () => {
    const noteProposal: ActionProposal = {
      id: 'prop-note-1',
      user_id: 'user-1',
      action_type: 'DECISION_NOTE',
      permission_level: 'LEVEL_2_CONFIRMATION',
      status: 'PENDING',
      parameters: {
        symbol: 'THYAO.IS',
        note_type: 'THESIS_NOTE',
        title: 'Havacılık Sektörü Büyüme Tezi',
      },
      expected_impact: {
        action: 'LOG_NOTE',
        symbol: 'THYAO.IS',
        title: 'Havacılık Sektörü Büyüme Tezi',
      },
      human_readable_summary: 'THYAO.IS için karar günlüğüne "Havacılık Sektörü Büyüme Tezi" notu kaydedilecek.',
      warnings: [],
      idempotency_key: 'idem-note-1',
      created_at: new Date().toISOString(),
    }

    render(
      <ActionProposalCard
        proposal={noteProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('KARAR GÜNLÜĞÜ NOTU')).toBeDefined()
    expect(screen.getByText('Havacılık Sektörü Büyüme Tezi')).toBeDefined()
  })

  it('renders warnings if present in proposal', () => {
    const warningProposal: ActionProposal = {
      ...baseTransactionProposal,
      warnings: ['Kayıt fiyatı piyasa fiyatından %5 farklı.', 'Yüksek portföy yoğunlaşması.'],
    }

    render(
      <ActionProposalCard
        proposal={warningProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('Kayıt fiyatı piyasa fiyatından %5 farklı.')).toBeDefined()
    expect(screen.getByText('Yüksek portföy yoğunlaşması.')).toBeDefined()
  })

  it('renders terminal state: EXECUTED', () => {
    const executedProposal: ActionProposal = {
      ...baseTransactionProposal,
      status: 'EXECUTED',
    }

    render(
      <ActionProposalCard
        proposal={executedProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('Uygulandı')).toBeDefined()
    expect(screen.getByText('İşlem başarıyla doğrulandı ve portföy kayıtlarınıza uygulandı.')).toBeDefined()
    expect(screen.queryByRole('button', { name: /Onayla ve Uygula/i })).toBeNull()
  })

  it('renders terminal state: CANCELLED', () => {
    const cancelledProposal: ActionProposal = {
      ...baseTransactionProposal,
      status: 'CANCELLED',
    }

    render(
      <ActionProposalCard
        proposal={cancelledProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('İptal Edildi')).toBeDefined()
    expect(screen.getByText('İşlem önerisi iptal edildi. Herhangi bir değişiklik yapılmadı.')).toBeDefined()
    expect(screen.queryByRole('button', { name: /Onayla ve Uygula/i })).toBeNull()
  })

  it('renders terminal state: STALE', () => {
    const staleProposal: ActionProposal = {
      ...baseTransactionProposal,
      status: 'STALE',
    }

    render(
      <ActionProposalCard
        proposal={staleProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    )

    expect(screen.getByText('Geçersiz (STALE)')).toBeDefined()
    expect(screen.getByText('Portföy bakiyesi değiştiği için öneri bayatladı (STALE) ve iptal edildi.')).toBeDefined()
    expect(screen.queryByRole('button', { name: /Onayla ve Uygula/i })).toBeNull()
  })

  it('disables buttons when loading', () => {
    render(
      <ActionProposalCard
        proposal={baseTransactionProposal}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        loading={true}
      />
    )

    const confirmBtn = screen.getByRole('button', { name: /Onayla ve Uygula/i })
    const cancelBtn = screen.getByRole('button', { name: /İptal Et/i })

    expect(confirmBtn).toHaveProperty('disabled', true)
    expect(cancelBtn).toHaveProperty('disabled', true)
  })
})
