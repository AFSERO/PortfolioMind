import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import VerdictCard from './VerdictCard'
import type { InstrumentIntelligenceState } from '@/types'

describe('VerdictCard', () => {
  it('renders clean empty state when no intelligence state exists', () => {
    render(<VerdictCard state={null} />)

    expect(screen.getByText('Investment Intelligence Verdict')).toBeInTheDocument()
    expect(screen.getByText(/No investment review has been completed/)).toBeInTheDocument()
  })

  it('renders recommendation badge, status dimensions, and human brief', () => {
    const state: InstrumentIntelligenceState = {
      id: 'state-1',
      instrument_id: 'inst-1',
      thesis_status: 'STRONGER',
      valuation_status: 'ATTRACTIVE',
      technical_status: 'ON_TRACK',
      recommendation: 'ADD',
      human_brief: 'Strong unit economics and market share expansion.',
      last_review_at: '2026-09-14T10:00:00Z',
      created_at: '',
      updated_at: '',
    }

    render(<VerdictCard state={state} />)

    expect(screen.getByText('ADD')).toBeInTheDocument()
    expect(screen.getByText('STRONGER')).toBeInTheDocument()
    expect(screen.getByText('ATTRACTIVE')).toBeInTheDocument()
    expect(screen.getByText('ON TRACK')).toBeInTheDocument()
    expect(screen.getByText('Strong unit economics and market share expansion.')).toBeInTheDocument()
    expect(screen.getByText(/Reviewed Sep 14, 2026/)).toBeInTheDocument()
  })

  it('renders execution restriction, alert banner, and recovery confidence for distressed fund', () => {
    const state: InstrumentIntelligenceState = {
      id: 'state-2',
      instrument_id: 'inst-2',
      thesis_status: 'INVALIDATED',
      valuation_status: 'UNKNOWN',
      technical_status: 'N_A',
      recommendation: 'SELL',
      execution_status: 'RESTRICTED',
      recovery_value_confidence: 'LOW',
      confidence_score: 65,
      human_brief: 'Fon itfa temerrüdünde olup tasfiye sürecindedir.',
      last_review_at: '2026-09-24T10:00:00Z',
      created_at: '',
      updated_at: '',
    }

    render(<VerdictCard state={state} assetType="FUND" />)

    expect(screen.getByText('SELL')).toBeInTheDocument()
    expect(screen.getByText('UYGULANABİLİRLİK: KISITLI')).toBeInTheDocument()
    expect(screen.getByText(/Kurtarma Güveni: LOW/)).toBeInTheDocument()
    expect(screen.getByText(/Uygulanabilirlik Bildirimi/)).toBeInTheDocument()
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
    expect(screen.getByText('N/A')).toBeInTheDocument()
  })
})
