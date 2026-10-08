import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UploadDropzone from './UploadDropzone'

const { preflightPdf } = vi.hoisted(() => ({ preflightPdf: vi.fn() }))

vi.mock('@/services/statementService', () => ({
  STATEMENT_PDF_MAX_BYTES: 10 * 1024 * 1024,
  statementService: { preflightPdf },
}))

const readyResult = {
  filename: 'statement.pdf',
  size_bytes: 12,
  sha256: 'a'.repeat(64),
  is_pdf: true as const,
  is_duplicate: false,
  matched_statement_id: null,
  status: 'ready' as const,
  analysis_available: false as const,
}

function renderDropzone(maxBytes?: number) {
  return render(<MemoryRouter><UploadDropzone liabilityId="card-1" maxBytes={maxBytes} /></MemoryRouter>)
}

function select(file: File) {
  fireEvent.change(screen.getByLabelText('Choose credit-card statement PDF'), {
    target: { files: [file] },
  })
}

describe('UploadDropzone', () => {
  beforeEach(() => vi.clearAllMocks())

  it('keeps analysis unavailable and accepts a valid PDF for preflight', async () => {
    let resolve!: (value: typeof readyResult) => void
    preflightPdf.mockReturnValue(new Promise((done) => { resolve = done }))
    renderDropzone()

    expect(screen.getByRole('button', { name: 'Analyze statement' })).toBeDisabled()
    const file = new File(['%PDF-1.7 fixture'], 'statement.pdf', { type: 'application/pdf' })
    select(file)
    expect(screen.getByText('Checking PDF…')).toBeInTheDocument()

    resolve(readyResult)
    expect(await screen.findByText('PDF preflight complete')).toBeInTheDocument()
    expect(preflightPdf).toHaveBeenCalledWith('card-1', file)
    expect(screen.getByText(/Analysis is not available/)).toBeInTheDocument()
  })

  it('rejects invalid type and oversized files before the network call', () => {
    const { unmount } = renderDropzone(8)
    select(new File(['hello'], 'statement.txt', { type: 'text/plain' }))
    expect(screen.getByText(/Only PDF files are accepted/)).toBeInTheDocument()
    expect(preflightPdf).not.toHaveBeenCalled()
    unmount()

    renderDropzone(8)
    select(new File(['%PDF-123456789'], 'large.pdf', { type: 'application/pdf' }))
    expect(screen.getByText(/exceeds the 8 B limit/)).toBeInTheDocument()
    expect(preflightPdf).not.toHaveBeenCalled()
  })

  it('shows duplicate state with a link to the existing statement', async () => {
    preflightPdf.mockResolvedValue({
      ...readyResult,
      is_duplicate: true,
      matched_statement_id: 'statement-1',
      status: 'duplicate_statement_file',
    })
    renderDropzone()
    select(new File(['%PDF-1.7 fixture'], 'statement.pdf', { type: 'application/pdf' }))

    const link = await screen.findByRole('link', { name: 'Open the matching statement' })
    expect(link).toHaveAttribute('href', '/liabilities/card-1/statements/statement-1')
    expect(screen.getByText('This PDF was already used')).toBeInTheDocument()
  })

  it('recovers from a network error by removing the selected file', async () => {
    preflightPdf.mockRejectedValue(new Error('Network unavailable'))
    renderDropzone()
    select(new File(['%PDF-1.7 fixture'], 'statement.pdf', { type: 'application/pdf' }))

    expect(await screen.findByText('Network unavailable')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(screen.getByText('Drop a credit-card statement PDF here')).toBeInTheDocument())
  })
})
