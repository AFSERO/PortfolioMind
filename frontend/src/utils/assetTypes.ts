import {
  TrendingUp,
  Coins,
  Gem,
  ArrowRightLeft,
  Building2,
  PieChart,
  Package,
} from 'lucide-react'

export const ASSET_TYPE_META: Record<
  string,
  { label: string; color: string; icon: React.ElementType }
> = {
  STOCK: { label: 'Stocks', color: '#60A5FA', icon: TrendingUp },
  CRYPTO: { label: 'Crypto', color: '#A78BFA', icon: Coins },
  PRECIOUS_METALS: { label: 'Değerli Madenler / Precious Metals', color: '#FBBF24', icon: Gem },
  FOREX: { label: 'Forex', color: '#2DD4BF', icon: ArrowRightLeft },
  REAL_ESTATE: { label: 'Real Estate', color: '#FB923C', icon: Building2 },
  FUND: { label: 'Funds', color: '#34D399', icon: PieChart },
  CUSTOM: { label: 'Custom', color: '#94A3B8', icon: Package },
}

export function typeColor(type: string): string {
  return ASSET_TYPE_META[type]?.color ?? '#94A3B8'
}

export function typeLabel(type: string): string {
  return ASSET_TYPE_META[type]?.label ?? type
}
