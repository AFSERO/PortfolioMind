import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import CopilotPage from './CopilotPage'
import { copilotService } from '@/services/copilotService'
import type { CopilotConversation } from '@/types/copilot'

vi.mock('@/services/copilotService', () => ({
  copilotService: {
    listConversations: vi.fn(),
    getConversation: vi.fn(),
    createConversation: vi.fn(),
    sendMessage: vi.fn(),
    sendV2Message: vi.fn(),
    deleteConversation: vi.fn(),
    confirmProposal: vi.fn(),
    cancelProposal: vi.fn(),
  },
}))

const mockConversations: CopilotConversation[] = [
  {
    id: 'conv-1',
    user_id: 'user-1',
    title: 'Portfolio Risks Discussion',
    created_at: '2026-09-24T20:00:00Z',
    updated_at: '2026-09-24T20:05:00Z',
  },
]

const mockInitialConversation: CopilotConversation = {
  id: 'conv-1',
  user_id: 'user-1',
  title: 'Portfolio Risks Discussion',
  created_at: '2026-09-24T20:00:00Z',
  updated_at: '2026-09-24T20:05:00Z',
  messages: [
    {
      id: 'msg-1',
      conversation_id: 'conv-1',
      role: 'user',
      raw_content: 'Where are my biggest portfolio risks?',
      created_at: '2026-09-24T20:01:00Z',
    },
    {
      id: 'msg-2',
      conversation_id: 'conv-1',
      role: 'assistant',
      raw_content: 'Your primary concentration risk is in US Tech Growth equities.',
      intent: 'PORTFOLIO_ANALYSIS',
      created_at: '2026-09-24T20:01:05Z',
      structured_metadata: {
        response_type: 'ANSWER',
        context_used: [
          { source_type: 'PORTFOLIO_HOLDINGS', title: 'Current Portfolio Holdings', freshness: 'CURRENT' },
          { source_type: 'INTELLIGENCE_STATE', title: 'THF Intelligence', freshness: 'CURRENT' },
        ],
      },
    },
  ],
}

describe('CopilotPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(copilotService.listConversations).mockResolvedValue(mockConversations)
    vi.mocked(copilotService.getConversation).mockResolvedValue(mockInitialConversation)
  })

  it('renders Copilot header, sessions, and messages with context provenance', async () => {
    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    // Header
    expect(screen.getAllByText('PortfolioMind Copilot').length).toBeGreaterThanOrEqual(1)

    // Session list
    await waitFor(() => {
      expect(screen.getByText('Portfolio Risks Discussion')).toBeDefined()
    })

    // Messages
    await waitFor(() => {
      expect(screen.getByText('Where are my biggest portfolio risks?')).toBeDefined()
      expect(screen.getByText('Your primary concentration risk is in US Tech Growth equities.')).toBeDefined()
    })

    // Context used section
    expect(screen.getByText('Context used:')).toBeDefined()
    expect(screen.getByText(/Current Portfolio Holdings/)).toBeDefined()
    expect(screen.getByText(/THF Intelligence/)).toBeDefined()
  })

  it('sends a new message in V1 mode and appends assistant response', async () => {
    vi.mocked(copilotService.sendMessage).mockResolvedValue({
      message: {
        id: 'msg-3',
        conversation_id: 'conv-1',
        role: 'assistant',
        raw_content: 'UBER thesis is supported by 22% EBITDA expansion.',
        intent: 'ASSET_ANALYSIS',
        created_at: '2026-09-24T20:06:00Z',
        structured_metadata: {
          response_type: 'ANSWER',
          context_used: [{ source_type: 'INSTRUMENT', title: 'UBER Instrument' }],
        },
      },
      structured_response: {
        response_type: 'ANSWER',
        answer: 'UBER thesis is supported by 22% EBITDA expansion.',
        intent: 'ASSET_ANALYSIS',
        context_used: [{ source_type: 'INSTRUMENT', title: 'UBER Instrument' }],
      },
      context_used: [{ source_type: 'INSTRUMENT', title: 'UBER Instrument' }],
    })

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Portfolio Risks Discussion')).toBeDefined()
    })

    const input = screen.getByPlaceholderText('Ask PortfolioMind Copilot...')
    fireEvent.change(input, { target: { value: 'What was my thesis for UBER?' } })
    const sendButton = screen.getByRole('button', { name: /Send/i })
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(screen.getByText('UBER thesis is supported by 22% EBITDA expansion.')).toBeDefined()
    })
  })

  it('toggles to V2 Beta and sends message through sendV2Message with telemetry trace', async () => {
    vi.mocked(copilotService.sendV2Message).mockImplementation(async (_convId, _content, onProgress) => {
      if (onProgress) {
        onProgress({
          type: 'STARTED',
          message: 'FAST orkestratör analiz ediyor...',
          profile: 'FAST',
        })
      }
      return {
        id: 'msg-v2-1',
        conversation_id: 'conv-1',
        role: 'assistant',
        raw_content: 'Toplam portföy değeriniz 1.250.000 TL.',
        intent: 'PORTFOLIO_ANALYSIS',
        created_at: '2026-09-24T20:10:00Z',
        structured_metadata: {
          trace: {
            conversation_id: 'conv-1',
            codex_session_id: 'sess-abc-123',
            final_profile: 'FAST',
            profile_sequence: ['FAST'],
            reasoning_effort: 'low',
            total_latency_ms: 450,
            tools_called: ['get_portfolio_summary'],
            codex_invocation_count: 1,
            tool_durations: {},
            tool_results_reused: 0,
            escalation_occurred: false,
            session_resume_failed: false,
            session_recovery_occurred: false,
            session_mode: 'RESUMED',
            reasoning_effort_sequence: ['low'],
          },
          external_sources: [
            {
              title: 'TEFAS Fon Bilgilendirme Raporu',
              source: 'Google News',
              url: 'https://news.google.com/test',
            },
          ],
        },
      }
    })

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Portfolio Risks Discussion')).toBeDefined()
    })

    // Click V2 Beta toggle button
    const v2ToggleBtn = screen.getByRole('button', { name: /V2 Beta \(Codex\)/i })
    fireEvent.click(v2ToggleBtn)

    expect(localStorage.getItem('portfoliomind_copilot_version')).toBe('v2')

    // Placeholder updates
    const v2Input = screen.getByPlaceholderText('Ask PortfolioMind Copilot V2 (Codex Engine)...')
    fireEvent.change(v2Input, { target: { value: 'Portföyüm toplam kaç TL?' } })

    const sendButton = screen.getByRole('button', { name: /Send/i })
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(screen.getByText('Toplam portföy değeriniz 1.250.000 TL.')).toBeDefined()
    })

    // Check telemetry badge rendered from V2DiagnosticsSection
    expect(screen.getByText('V2 Telemetry')).toBeDefined()
    expect(screen.getByText(/FAST · low · 450ms/)).toBeDefined()

    // Check external sources section rendered
    expect(screen.getByText('Kaynaklar')).toBeDefined()
  })

  it('renders ActionProposalCard when assistant message has a proposal and handles confirmation', async () => {
    const mockConvWithProposal: CopilotConversation = {
      id: 'conv-prop-1',
      user_id: 'user-1',
      title: 'THYAO Alış Talebi',
      created_at: '2026-10-01T10:00:00Z',
      updated_at: '2026-10-01T10:05:00Z',
      messages: [
        {
          id: 'msg-u1',
          conversation_id: 'conv-prop-1',
          role: 'user',
          raw_content: 'Bugün 50 lot THYAO aldım, kaydet',
          created_at: '2026-10-01T10:01:00Z',
        },
        {
          id: 'msg-a1',
          conversation_id: 'conv-prop-1',
          role: 'assistant',
          raw_content: '50 adet THYAO için alış kaydı önerisi hazırlandı. Onayınız bekleniyor.',
          intent: 'TRANSACTION_RECORD',
          created_at: '2026-10-01T10:01:05Z',
          structured_metadata: {
            response_type: 'PROPOSAL',
            proposal: {
              id: 'prop-123',
              user_id: 'user-1',
              conversation_id: 'conv-prop-1',
              action_type: 'TRANSACTION_RECORD',
              permission_level: 'LEVEL_2_CONFIRMATION',
              status: 'PENDING',
              parameters: {
                symbol: 'THYAO.IS',
                transaction_type: 'BUY',
                quantity: 50,
                price: 310,
                currency: 'TRY',
              },
              expected_impact: {
                action: 'BUY',
                symbol: 'THYAO.IS',
                previous_quantity: 0,
                new_quantity: 50,
                total_amount: 15500,
                cash_delta: -15500,
                currency: 'TRY',
              },
              human_readable_summary: '50 adet THYAO.IS için 310.00 TRY fiyattan portföy ALIŞ kaydı oluşturulacak.',
              warnings: [],
              idempotency_key: 'idem-123',
              created_at: '2026-10-01T10:01:05Z',
            },
          },
        },
      ],
    }

    vi.mocked(copilotService.listConversations).mockResolvedValue([mockConvWithProposal])
    vi.mocked(copilotService.getConversation).mockResolvedValue(mockConvWithProposal)
    vi.mocked(copilotService.confirmProposal).mockResolvedValue({
      proposal: {
        ...mockConvWithProposal.messages![1].structured_metadata!.proposal!,
        status: 'EXECUTED',
      },
      result: { transaction_id: 'tx-1' },
    })

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('PORTFÖY ALIŞ KAYDI')).toBeDefined()
      expect(screen.getByText('Onay Bekliyor')).toBeDefined()
    })

    // Click confirm button
    const confirmButton = screen.getByRole('button', { name: /Onayla ve Uygula/i })
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(copilotService.confirmProposal).toHaveBeenCalledWith('prop-123', undefined, 'CONFIRM')
      expect(screen.getByText('Uygulandı')).toBeDefined()
    })
  })

  it('persists EXECUTED status when conversation history is reloaded', async () => {
    const executedProposalConv: CopilotConversation = {
      id: 'conv-prop-exec',
      user_id: 'user-1',
      title: 'Geçmiş Onaylanmış İşlem',
      created_at: '2026-10-01T10:00:00Z',
      updated_at: '2026-10-01T10:05:00Z',
      messages: [
        {
          id: 'msg-exec-1',
          conversation_id: 'conv-prop-exec',
          role: 'assistant',
          raw_content: 'THYAO alış kaydı uygulandı.',
          intent: 'TRANSACTION_RECORD',
          created_at: '2026-10-01T10:02:00Z',
          structured_metadata: {
            response_type: 'PROPOSAL',
            proposal: {
              id: 'prop-exec-99',
              user_id: 'user-1',
              conversation_id: 'conv-prop-exec',
              action_type: 'TRANSACTION_RECORD',
              permission_level: 'LEVEL_2_CONFIRMATION',
              status: 'EXECUTED',
              parameters: {
                symbol: 'THYAO.IS',
                transaction_type: 'BUY',
                quantity: 50,
                price: 310,
              },
              expected_impact: {
                action: 'BUY',
                symbol: 'THYAO.IS',
                previous_quantity: 0,
                new_quantity: 50,
                total_amount: 15500,
                cash_delta: -15500,
              },
              human_readable_summary: '50 adet THYAO.IS portföy ALIŞ kaydı uygulandı.',
              warnings: [],
              idempotency_key: 'idem-exec-99',
              created_at: '2026-10-01T10:01:00Z',
            },
          },
        },
      ],
    }

    vi.mocked(copilotService.listConversations).mockResolvedValue([executedProposalConv])
    vi.mocked(copilotService.getConversation).mockResolvedValue(executedProposalConv)

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Uygulandı')).toBeDefined()
      expect(screen.getByText('İşlem başarıyla doğrulandı ve portföy kayıtlarınıza uygulandı.')).toBeDefined()
      expect(screen.queryByRole('button', { name: /Onayla ve Uygula/i })).toBeNull()
      expect(screen.queryByRole('button', { name: /İptal Et/i })).toBeNull()
    })
  })

  it('handles proposal cancellation and updates UI to CANCELLED', async () => {
    const pendingConv: CopilotConversation = {
      id: 'conv-cancel-1',
      user_id: 'user-1',
      title: 'İptal Edilecek İşlem',
      created_at: '2026-10-01T11:00:00Z',
      updated_at: '2026-10-01T11:05:00Z',
      messages: [
        {
          id: 'msg-cancel-1',
          conversation_id: 'conv-cancel-1',
          role: 'assistant',
          raw_content: 'PGSUS alış kaydı hazırlandı.',
          intent: 'TRANSACTION_RECORD',
          created_at: '2026-10-01T11:01:00Z',
          structured_metadata: {
            response_type: 'PROPOSAL',
            proposal: {
              id: 'prop-cancel-42',
              user_id: 'user-1',
              conversation_id: 'conv-cancel-1',
              action_type: 'TRANSACTION_RECORD',
              permission_level: 'LEVEL_2_CONFIRMATION',
              status: 'PENDING',
              parameters: {
                symbol: 'PGSUS.IS',
                transaction_type: 'BUY',
                quantity: 10,
                price: 240,
              },
              human_readable_summary: '10 adet PGSUS.IS için ALIŞ kaydı oluşturulacak.',
              warnings: [],
              idempotency_key: 'idem-cancel-42',
              created_at: '2026-10-01T11:01:00Z',
            },
          },
        },
      ],
    }

    vi.mocked(copilotService.listConversations).mockResolvedValue([pendingConv])
    vi.mocked(copilotService.getConversation).mockResolvedValue(pendingConv)
    vi.mocked(copilotService.cancelProposal).mockResolvedValue({
      proposal: {
        ...pendingConv.messages![0].structured_metadata!.proposal!,
        status: 'CANCELLED',
      },
    } as any)

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Onay Bekliyor')).toBeDefined()
    })

    const cancelBtn = screen.getByRole('button', { name: /İptal Et/i })
    fireEvent.click(cancelBtn)

    await waitFor(() => {
      expect(copilotService.cancelProposal).toHaveBeenCalledWith('prop-cancel-42')
      expect(screen.getByText('İptal Edildi')).toBeDefined()
    })
  })

  it('renders terminal STALE status on reload without action buttons', async () => {
    const staleConv: CopilotConversation = {
      id: 'conv-stale-1',
      user_id: 'user-1',
      title: 'Bayatlamış İşlem',
      created_at: '2026-10-01T12:00:00Z',
      updated_at: '2026-10-01T12:05:00Z',
      messages: [
        {
          id: 'msg-stale-1',
          conversation_id: 'conv-stale-1',
          role: 'assistant',
          raw_content: 'Öneri bayatladı.',
          intent: 'TRANSACTION_RECORD',
          created_at: '2026-10-01T12:01:00Z',
          structured_metadata: {
            response_type: 'PROPOSAL',
            proposal: {
              id: 'prop-stale-77',
              user_id: 'user-1',
              conversation_id: 'conv-stale-1',
              action_type: 'TRANSACTION_RECORD',
              permission_level: 'LEVEL_2_CONFIRMATION',
              status: 'STALE',
              parameters: {
                symbol: 'GARAN.IS',
                transaction_type: 'SELL',
                quantity: 100,
                price: 85,
              },
              human_readable_summary: '100 adet GARAN.IS için SATIŞ kaydı.',
              warnings: [],
              idempotency_key: 'idem-stale-77',
              created_at: '2026-10-01T12:01:00Z',
            },
          },
        },
      ],
    }

    vi.mocked(copilotService.listConversations).mockResolvedValue([staleConv])
    vi.mocked(copilotService.getConversation).mockResolvedValue(staleConv)

    render(
      <MemoryRouter>
        <CopilotPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Geçersiz (STALE)')).toBeDefined()
      expect(screen.queryByRole('button', { name: /Onayla ve Uygula/i })).toBeNull()
      expect(screen.queryByRole('button', { name: /İptal Et/i })).toBeNull()
    })
  })
})

