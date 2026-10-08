import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ExternalSourcesSection } from './ExternalSourcesSection'
import type { CopilotExternalSource } from '@/types/copilot'

const mockSources: CopilotExternalSource[] = [
  {
    title: 'TEFAS Fon Analizi: THF Fonu Bilgilendirmesi',
    source: 'Google News',
    url: 'https://news.google.com/rss/articles/CBMi...',
    published_at: '2026-09-28 14:00',
    snippet: 'THF fonunun likidasyon süreci ve piyasa etkileri değerlendirildi.',
  },
  {
    title: 'Borsa ve Fon Bülteni',
    source: 'Ekonomim',
    url: 'https://www.ekonomim.com/piyasalar/haber-123',
    published_at: '2026-09-29 09:30',
  },
]

describe('ExternalSourcesSection', () => {
  it('renders collapsed sources header with count badge', () => {
    render(<ExternalSourcesSection sources={mockSources} />)

    expect(screen.getByText('Kaynaklar')).toBeDefined()
    expect(screen.getByText('2')).toBeDefined()
  })

  it('expands to reveal source titles, links, badges, and snippets', () => {
    render(<ExternalSourcesSection sources={mockSources} />)

    const button = screen.getByRole('button')
    fireEvent.click(button)

    expect(screen.getByText('TEFAS Fon Analizi: THF Fonu Bilgilendirmesi')).toBeDefined()
    expect(screen.getByText('Google News')).toBeDefined()
    expect(screen.getByText('THF fonunun likidasyon süreci ve piyasa etkileri değerlendirildi.')).toBeDefined()
    expect(screen.getByText('Borsa ve Fon Bülteni')).toBeDefined()
    expect(screen.getByText('Ekonomim')).toBeDefined()

    const links = screen.getAllByRole('link')
    expect(links.length).toBe(2)
    expect(links[0].getAttribute('href')).toBe('https://news.google.com/rss/articles/CBMi...')
    expect(links[0].getAttribute('target')).toBe('_blank')
    expect(links[0].getAttribute('rel')).toContain('noopener')
  })

  it('renders nothing when sources array is empty or undefined', () => {
    const { container: emptyContainer } = render(<ExternalSourcesSection sources={[]} />)
    expect(emptyContainer.firstChild).toBeNull()

    const { container: nullContainer } = render(<ExternalSourcesSection sources={null} />)
    expect(nullContainer.firstChild).toBeNull()
  })
})
