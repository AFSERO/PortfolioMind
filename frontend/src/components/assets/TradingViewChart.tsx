import { useEffect, useState } from 'react'
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets'
import { resolveStockMarket } from '@/utils/stockMarket'

interface Props {
  symbol: string
  assetType: string
}

interface MappedSymbol {
  tvSymbol: string
  note?: string
}

/**
 * Synchronously map non-STOCK asset types to a TradingView ticker.
 * STOCK symbols need an async market lookup — handled separately.
 */
function mapNonStock(symbol: string, assetType: string): MappedSymbol {
  const upper = symbol.toUpperCase()

  switch (assetType) {
    case 'CRYPTO':
      // BTC → BINANCE:BTCUSDT
      return { tvSymbol: `BINANCE:${upper}USDT` }

    case 'FOREX':
      // "USD/TRY" or "USD-TRY" → FX:USDTRY
      return { tvSymbol: `FX:${upper.replace(/[/\-]/, '')}` }

    case 'PRECIOUS_METALS': {
      if (upper === 'XAU') return { tvSymbol: 'TVC:GOLD' }
      if (upper === 'XAG') return { tvSymbol: 'TVC:SILVER' }
      if (upper === 'XPT') return { tvSymbol: 'TVC:PLATINUM' }
      if (upper === 'XPD') return { tvSymbol: 'TVC:PALLADIUM' }
      if (['GR', 'QTR', 'HALF', 'FULL'].includes(upper)) {
        return {
          tvSymbol: 'TVC:GOLD',
          note: 'Showing XAU/USD (troy ounce). Your position is denominated in a per-gram or Turkish coin unit.',
        }
      }
      if (upper === 'SILVER_GR') {
        return {
          tvSymbol: 'TVC:SILVER',
          note: 'Showing XAG/USD (troy ounce). Your position is denominated in grams.',
        }
      }
      return { tvSymbol: 'TVC:GOLD' }
    }

    default:
      return { tvSymbol: upper }
  }
}

export default function TradingViewChart({ symbol, assetType }: Props) {
  // For STOCK: null = resolving, string = ready. For all other types: set immediately.
  const [mapped, setMapped] = useState<MappedSymbol | null>(
    assetType !== 'STOCK' ? mapNonStock(symbol, assetType) : null
  )

  useEffect(() => {
    if (assetType !== 'STOCK') {
      setMapped(mapNonStock(symbol, assetType))
      return
    }

    let cancelled = false
    const upper = symbol.toUpperCase()

    resolveStockMarket(upper).then((market) => {
      if (cancelled) return
      // Strip .IS suffix if present (already handled by resolveStockMarket returning BIST)
      const bare = upper.endsWith('.IS') ? upper.slice(0, -3) : upper
      setMapped({ tvSymbol: `${market}:${bare}` })
    })

    return () => { cancelled = true }
  }, [symbol, assetType])

  return (
    <div className="space-y-2">
      <div className="h-[400px] w-full rounded-lg overflow-hidden bg-slate-800">
        {mapped ? (
          <AdvancedRealTimeChart
            symbol={mapped.tvSymbol}
            theme="dark"
            interval="D"
            range="6M"
            autosize
            hide_top_toolbar={false}
            hide_side_toolbar={false}
            allow_symbol_change={false}
            save_image={false}
          />
        ) : (
          // Skeleton while market is being resolved (STOCK type only)
          <div className="h-full w-full animate-pulse bg-slate-800 rounded-lg" />
        )}
      </div>

      {mapped?.note && (
        <p className="text-xs text-amber-500/80 px-1">
          ⚠ {mapped.note}
        </p>
      )}

      <p className="text-xs text-slate-600 text-right px-1">
        Chart powered by{' '}
        <a
          href="https://www.tradingview.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-500 hover:text-slate-400 underline underline-offset-2"
        >
          TradingView
        </a>
      </p>
    </div>
  )
}
