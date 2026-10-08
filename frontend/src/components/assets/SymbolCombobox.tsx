/**
 * SymbolCombobox — searchable symbol picker that queries the backend's
 * /api/symbols/search endpoint with 300ms debounce.
 *
 * Props:
 *   type          — "stock" | "us_stock" | "crypto" | "forex" | "fund" | "precious_metals"
 *   value         — current symbol string (controlled)
 *   onChange      — called with the chosen symbol string
 *   onNameSelect  — called with the name string when a symbol is picked
 *   onAssetSelect — called with full SymbolEntry when picked
 *   placeholder   — input placeholder text
 */

import { useState, useEffect, useRef, useCallback, KeyboardEvent } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { api } from '@/services/api'
import { cn } from '@/utils/cn'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SymbolEntry {
  symbol: string
  name: string
  asset_type?: string
  currency?: string
  market?: string
  coingecko_id?: string
}

interface SymbolSearchResponse {
  status: string
  data: SymbolEntry[]
}

export type SymbolType =
  | 'stock'
  | 'us_stock'
  | 'crypto'
  | 'forex'
  | 'fund'
  | 'precious_metals'

interface Props {
  type: SymbolType
  value: string
  onChange: (symbol: string) => void
  onNameSelect?: (name: string) => void
  onAssetSelect?: (entry: SymbolEntry) => void
  placeholder?: string
}

// ── Fetch helper ─────────────────────────────────────────────────────────────

async function searchSymbols(type: SymbolType, q: string): Promise<SymbolEntry[]> {
  try {
    const resp = await api.get<SymbolSearchResponse>(
      `/symbols/search?type=${type}&q=${encodeURIComponent(q)}&limit=20`,
    )
    return (resp as SymbolSearchResponse).data ?? []
  } catch {
    return []
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SymbolCombobox({
  type,
  value,
  onChange,
  onNameSelect,
  onAssetSelect,
  placeholder = 'Search…',
}: Props) {
  const [query, setQuery]       = useState(value ?? '')
  const [results, setResults]   = useState<SymbolEntry[]>([])
  const [isOpen, setIsOpen]     = useState(false)
  const [isLoading, setLoading] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef     = useRef<HTMLInputElement>(null)
  const debounceRef  = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep local query in sync when parent resets the value
  useEffect(() => {
    setQuery(value ?? '')
  }, [value])

  // Debounced search
  const runSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(async () => {
        setLoading(true)
        const data = await searchSymbols(type, q)
        setResults(data)
        setLoading(false)
        setActiveIdx(-1)
      }, 300)
    },
    [type],
  )

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value
    setQuery(q)
    onChange(q)          // keep parent form field in sync as the user types
    setIsOpen(true)
    runSearch(q)
  }

  const handleFocus = () => {
    setIsOpen(true)
    runSearch(query)
  }

  const handleSelect = (entry: SymbolEntry) => {
    setQuery(entry.symbol)
    onChange(entry.symbol)
    onNameSelect?.(entry.name)
    onAssetSelect?.(entry)
    setIsOpen(false)
    setResults([])
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || results.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault()
      handleSelect(results[activeIdx])
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const showDropdown = isOpen && (isLoading || results.length > 0 || query.length > 0)

  return (
    <div ref={containerRef} className="relative">
      {/* Input */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
        <input
          ref={inputRef}
          value={query}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className={cn(
            'w-full rounded-md border border-slate-700 bg-slate-800 pl-8 pr-8 py-2',
            'text-sm text-slate-100 placeholder:text-slate-500',
            'focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500',
            'transition-colors',
          )}
        />
        {isLoading && (
          <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 animate-spin pointer-events-none" />
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-slate-700 bg-slate-800 shadow-xl overflow-hidden">
          {isLoading && results.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-500">Searching…</div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-xs text-slate-500">No symbols found</div>
          ) : (
            <ul className="max-h-56 overflow-y-auto divide-y divide-slate-700/50">
              {results.map((entry, idx) => (
                <li
                  key={`${entry.symbol}-${entry.market ?? ''}-${idx}`}
                  onMouseDown={(e) => {
                    e.preventDefault() // keep focus on input until select
                    handleSelect(entry)
                  }}
                  onMouseEnter={() => setActiveIdx(idx)}
                  className={cn(
                    'flex items-center justify-between px-3 py-2 text-sm cursor-pointer select-none',
                    idx === activeIdx
                      ? 'bg-slate-700 text-slate-100'
                      : 'text-slate-300 hover:bg-slate-700/60',
                  )}
                >
                  <div className="flex flex-col min-w-0 pr-2">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-medium text-slate-100">{entry.symbol}</span>
                      {entry.market && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-900/80 text-slate-400 border border-slate-700/80 font-sans">
                          {entry.market}
                        </span>
                      )}
                      {entry.currency && (
                        <span className="text-[10px] text-slate-400 font-mono font-normal">
                          {entry.currency}
                        </span>
                      )}
                    </div>
                    <span className="text-slate-400 text-xs truncate mt-0.5">
                      {entry.name}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
