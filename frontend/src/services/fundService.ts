import { api } from '@/services/api'

export interface FundInfo {
  fund_code: string
  fund_name: string
  price: number
  currency: string
  price_date: string | null
  provider: string
}

interface FundInfoResponse {
  status: string
  data: FundInfo
}

export const fundService = {
  getInfo: (code: string) =>
    api
      .get<FundInfoResponse>(`/funds/info/${encodeURIComponent(code.trim().toUpperCase())}`)
      .then((r) => (r as FundInfoResponse).data),
}
