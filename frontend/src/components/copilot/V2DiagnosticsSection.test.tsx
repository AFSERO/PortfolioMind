import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { V2DiagnosticsSection } from './V2DiagnosticsSection'
import type { CopilotV2Trace } from '@/types/copilot'

const mockTrace: CopilotV2Trace = {
  starting_profile: 'FAST',
  final_profile: 'BALANCED',
  profile_sequence: ['FAST', 'BALANCED'],
  reasoning_effort: 'medium',
  reasoning_effort_sequence: ['low', 'medium'],
  tool_results_reused: 1,
  escalation_occurred: true,
  session_recovery_occurred: false,
  session_resume_failed: false,
  session_mode: 'RESUMED',
  total_latency_ms: 1250,
  codex_invocation_count: 2,
  tools_called: ['get_portfolio_summary', 'get_asset_context'],
  tool_durations: {
    get_portfolio_summary: 45,
    get_asset_context: 60,
  },
  conversation_id: 'conv-123',
  codex_session_id: 'sess-abc',
}

describe('V2DiagnosticsSection', () => {
  it('renders collapsed summary telemetry bar with badges', () => {
    render(<V2DiagnosticsSection trace={mockTrace} />)

    expect(screen.getByText('V2 Telemetry')).toBeDefined()
    expect(screen.getByText(/BALANCED · medium · 1250ms/)).toBeDefined()
    expect(screen.getByText('Escalated')).toBeDefined()
  })

  it('expands to show execution details and tool calls on click', () => {
    render(<V2DiagnosticsSection trace={mockTrace} />)

    const toggleButton = screen.getByRole('button')
    fireEvent.click(toggleButton)

    // Check expanded details
    expect(screen.getByText(/FAST → BALANCED/)).toBeDefined()
    expect(screen.getByText('sess-abc')).toBeDefined()
    expect(screen.getByText('RESUMED')).toBeDefined()
    expect(screen.getByText(/tool output\(s\) reused across handoff boundary/)).toBeDefined()
    expect(screen.getByText('get_portfolio_summary')).toBeDefined()
    expect(screen.getByText('(45ms)')).toBeDefined()
    expect(screen.getByText('get_asset_context')).toBeDefined()
    expect(screen.getByText('(60ms)')).toBeDefined()
  })

  it('renders nothing when trace is missing', () => {
    const { container } = render(<V2DiagnosticsSection trace={null as any} />)
    expect(container.firstChild).toBeNull()
  })
})
