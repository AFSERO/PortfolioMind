import { create } from 'zustand'

export type DashboardCurrency = 'TRY' | 'USD' | 'EUR'

interface DashboardState {
  currency: DashboardCurrency
  setCurrency: (currency: DashboardCurrency) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  currency: 'TRY',
  setCurrency: (currency) => set({ currency }),
}))
