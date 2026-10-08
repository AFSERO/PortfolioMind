import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PortfolioImportCard } from './PortfolioImportCard'
import type { PortfolioImportBatch, ActionProposal } from '@/types/copilot'

describe('PortfolioImportCard', () => {
  const sampleBatch: PortfolioImportBatch = {
    id: 'batch-1',
    user_id: 'user-1',
    source_type: 'NATURAL_LANGUAGE',
    status: 'READY_FOR_CONFIRMATION',
    idempotency_key: 'key-1',
    created_at: new Date().toISOString(),
    items: [
      {
        id: 'item-1',
        batch_id: 'batch-1',
        raw_input: '50 adet THYAO aldım',
        asset_type: 'STOCK',
        symbol: 'THYAO.IS',
        name: 'Turk Hava Yollari',
        quantity: 50,
        average_cost: 300,
        currency: 'TRY',
        intended_action: 'CREATE_OPENING_POSITION',
        warnings: [],
        missing_fields: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ],
    ready_count: 1,
    needs_review_count: 0,
    ambiguous_count: 0,
    warnings: [],
    errors: [],
  }

  const sampleProposal: ActionProposal = {
    id: 'prop-1',
    user_id: 'user-1',
    conversation_id: 'conv-1',
    action_type: 'PORTFOLIO_IMPORT',
    permission_level: 'LEVEL_3_STRONG_CONFIRMATION',
    status: 'READY_FOR_CONFIRMATION',
    parameters: { import_batch_id: 'batch-1' },
    human_readable_summary: 'Portföy içe aktarımı: 1 varlık',
    warnings: [],
    idempotency_key: 'idem-1',
    created_at: new Date().toISOString(),
  }

  it('renders batch items, symbol, quantity and confirmation button', () => {
    const handleConfirm = vi.fn()
    render(
      <PortfolioImportCard
        batch={sampleBatch}
        proposal={sampleProposal}
        onConfirm={handleConfirm}
      />
    )

    expect(screen.getByText(/THYAO\.IS/i)).toBeInTheDocument()
    expect(screen.getByText(/Yeni Açılış Pozisyonu/i)).toBeInTheDocument()
    const confirmButton = screen.getByRole('button', { name: /Onayla ve Portföye Aktar/i })
    expect(confirmButton).toBeEnabled()

    fireEvent.click(confirmButton)
    expect(handleConfirm).toHaveBeenCalledWith('prop-1')
  })

  it('disables confirmation and shows resolution controls when item needs review', () => {
    const batchWithIssue: PortfolioImportBatch = {
      ...sampleBatch,
      status: 'DRAFT',
      ready_count: 0,
      needs_review_count: 1,
      items: [
        {
          ...sampleBatch.items[0],
          existing_quantity: 20,
          intended_action: 'AMBIGUOUS',
          warnings: ['Mevcut 20 adet pozisyon var. İlave mi güncelleme mi?'],
        },
      ],
    }

    render(
      <PortfolioImportCard
        batch={batchWithIssue}
        proposal={sampleProposal}
      />
    )

    expect(screen.getByText(/Karar Gerekli/i)).toBeInTheDocument()
    expect(
      screen.getByText(/Mevcut \(20\) pozisyon ile nasıl birleştirilsin\?/i)
    ).toBeInTheDocument()

    // Confirm button should be disabled because needs review
    const confirmButton = screen.getByRole('button', { name: /Onayla ve Portföye Aktar/i })
    expect(confirmButton).toBeDisabled()
  })
})
