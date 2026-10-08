import { api } from '@/services/api'
import type { AssetType } from '@/types'

export interface ResolvedAsset {
  symbol: string
  name: string
  asset_type: AssetType
  currency: string
  latest_price: number
  price_date: string | null
  market?: string | null
  provider?: string | null
  provider_id?: string | null
}

interface ResolveResponse {
  status: string
  data: ResolvedAsset
}

export const assetResolverService = {
  resolve: async (type: string, symbol: string): Promise<ResolvedAsset> => {
    const resp = await api.get<ResolveResponse>(
      `/symbols/resolve?type=${encodeURIComponent(type.toLowerCase())}&symbol=${encodeURIComponent(symbol.trim())}`
    )
    return (resp as ResolveResponse).data
  },
}
