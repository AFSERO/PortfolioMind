import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { toast } from 'sonner'
import { useAuthStore } from '@/store'
import { setAccessToken, getAccessToken } from '@/services/api'
import {
  resetPriceRefreshState,
  notifyPricesRefreshed,
} from '@/services/priceService'
import { useAssets } from '@/hooks/useAssets'
import { useDashboardSummary } from '@/hooks/useDashboard'
import AuthInitializer from '@/components/AuthInitializer'

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

describe('Post-Login Background Price Refresh Flow & Invalidation', () => {
  const mockUser = {
    id: 'user-456',
    email: 'investor@example.com',
    display_name: 'Investor User',
    base_currency: 'TRY',
    created_at: '2026-01-01',
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    resetPriceRefreshState()
    setAccessToken(null)
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetPriceRefreshState()
    setAccessToken(null)
  })

  it('scenario 1: login succeeds and triggers background price refresh without blocking login completion', async () => {
    let refreshResolved = false
    let resolveRefresh: (value: unknown) => void = () => {}
    const refreshPromise = new Promise((resolve) => {
      resolveRefresh = (val) => {
        refreshResolved = true
        resolve(val)
      }
    })

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/login') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'login-token-123', token_type: 'bearer', user: mockUser },
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        return refreshPromise.then((data) => ({
          ok: true,
          status: 200,
          json: async () => data,
        })) as Promise<Response>
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`))
    })
    global.fetch = fetchMock

    // Execute login
    const loginPromise = useAuthStore.getState().login({
      email: 'investor@example.com',
      password: 'password123',
    })

    // The login promise must resolve IMMEDIATELY without waiting for price refresh to complete!
    await loginPromise

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().user).toEqual(mockUser)
    expect(getAccessToken()).toBe('login-token-123')
    // Background refresh is still in flight at this point
    expect(refreshResolved).toBe(false)

    // Complete background refresh
    resolveRefresh({
      status: 'success',
      data: [
        { asset_id: 'a1', symbol: 'THYAO.IS', status: 'updated', price: 310.5, currency: 'TRY' },
        { asset_id: 'a2', symbol: 'BTC', status: 'updated', price: 65000, currency: 'USD' },
      ],
    })

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('Prices refreshed — 2 updated')
    })
  })

  it('scenario 2a: login succeeds + price provider partial/total failure (200 with failed status) maintains valid auth', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/login') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'login-token-fail', token_type: 'bearer', user: mockUser },
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: [
              { asset_id: 'a1', symbol: 'THYAO.IS', status: 'failed', error: 'yfinance timeout' },
            ],
          }),
        } as Response)
      }
      return Promise.reject(new Error(`Unhandled: ${url}`))
    })

    await useAuthStore.getState().login({
      email: 'investor@example.com',
      password: 'password123',
    })

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith('Could not update live asset prices')
    })

    // Auth must remain intact!
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().user).toEqual(mockUser)
    expect(getAccessToken()).toBe('login-token-fail')
  })

  it('scenario 2b: login succeeds + price refresh network/server 500 error maintains valid auth without logout', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/login') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'login-token-500', token_type: 'bearer', user: mockUser },
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        return Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: async () => ({ status: 'error', message: 'Pricing service unavailable' }),
        } as Response)
      }
      return Promise.reject(new Error(`Unhandled: ${url}`))
    })

    await useAuthStore.getState().login({
      email: 'investor@example.com',
      password: 'password123',
    })

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith('Could not refresh asset prices')
    })

    // Auth must NOT be cleared, user must remain logged in
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().user).toEqual(mockUser)
    expect(getAccessToken()).toBe('login-token-500')
  })

  it('scenario 3: hard refresh (checkAuth) does NOT trigger price refresh', async () => {
    const pricesRefreshCalled = vi.fn()

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/refresh') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'restored-token-999' },
          }),
        } as Response)
      }
      if (url === '/api/auth/me') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: mockUser,
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        pricesRefreshCalled()
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', data: [] }),
        } as Response)
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`))
    })

    // Simulate page reload / hard refresh session restore
    await useAuthStore.getState().checkAuth()

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(getAccessToken()).toBe('restored-token-999')
    // Crucial check: /prices/refresh MUST NEVER be called on session restore / hard refresh!
    expect(pricesRefreshCalled).not.toHaveBeenCalled()
  })

  it('scenario 4: new tab session restore (AuthInitializer) does NOT trigger price refresh', async () => {
    const pricesRefreshCalled = vi.fn()

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/refresh') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'new-tab-token' },
          }),
        } as Response)
      }
      if (url === '/api/auth/me') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: mockUser,
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        pricesRefreshCalled()
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', data: [] }),
        } as Response)
      }
      return Promise.reject(new Error(`Unhandled: ${url}`))
    })

    const { unmount } = renderHook(() => AuthInitializer())

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
    })

    // Crucial check: New tab mount must NOT call /prices/refresh
    expect(pricesRefreshCalled).not.toHaveBeenCalled()
    unmount()
  })

  it('scenario 5: rapid duplicate login actions do not cause redundant price refresh calls', async () => {
    let refreshCallCount = 0

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/login') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: { access_token: 'token-rapid', token_type: 'bearer', user: mockUser },
          }),
        } as Response)
      }
      if (url === '/api/prices/refresh') {
        refreshCallCount++
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              status: 200,
              json: async () => ({
                status: 'success',
                data: [{ asset_id: 'a1', symbol: 'THYAO.IS', status: 'updated', price: 320 }],
              }),
            } as Response)
          }, 30)
        })
      }
      return Promise.reject(new Error(`Unhandled: ${url}`))
    })

    // Rapid double login call
    const login1 = useAuthStore.getState().login({ email: 'u@test.com', password: '123' })
    const login2 = useAuthStore.getState().login({ email: 'u@test.com', password: '123' })

    await Promise.all([login1, login2])

    // Wait for in-flight price refresh to complete
    await waitFor(() => {
      expect(refreshCallCount).toBe(1)
    })

    // Allow the setTimeout(..., 30) and finally block to fully settle
    await new Promise((resolve) => setTimeout(resolve, 80))

    // Exactly 1 network request to /prices/refresh should have been made!
    expect(refreshCallCount).toBe(1)
  })

  it('scenario 6: price refresh completion triggers invalidation and refetch in useAssets and useDashboardSummary', async () => {
    let assetListCalls = 0
    let dashboardSummaryCalls = 0

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/assets') {
        assetListCalls++
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: [
              {
                id: 'asset-1',
                name: 'THY',
                symbol: 'THYAO.IS',
                asset_type: 'STOCK',
                current_price: assetListCalls === 1 ? 290 : 315,
                current_price_currency: 'TRY',
              },
            ],
          }),
        } as Response)
      }
      if (url === '/api/dashboard/summary') {
        dashboardSummaryCalls++
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            status: 'success',
            data: {
              total_assets: dashboardSummaryCalls === 1 ? 29000 : 31500,
              net_worth: dashboardSummaryCalls === 1 ? 29000 : 31500,
              base_currency: 'TRY',
            },
          }),
        } as Response)
      }
      return Promise.reject(new Error(`Unhandled: ${url}`))
    })

    setAccessToken('valid-token')

    const { result: assetsHook, unmount: unmountAssets } = renderHook(() => useAssets())
    const { result: dashboardHook, unmount: unmountDashboard } = renderHook(() => useDashboardSummary())

    // Initial load
    await waitFor(() => {
      expect(assetsHook.current.isLoading).toBe(false)
      expect(dashboardHook.current.isLoading).toBe(false)
    })

    expect(assetListCalls).toBe(1)
    expect(dashboardSummaryCalls).toBe(1)
    expect(assetsHook.current.assets[0].current_price).toBe(290)
    expect(dashboardHook.current.data?.total_assets).toBe(29000)

    // Trigger price update invalidation
    act(() => {
      notifyPricesRefreshed()
    })

    // Both hooks should refetch and have the updated values
    await waitFor(() => {
      expect(assetListCalls).toBe(2)
      expect(dashboardSummaryCalls).toBe(2)
    })

    expect(assetsHook.current.assets[0].current_price).toBe(315)
    expect(dashboardHook.current.data?.total_assets).toBe(31500)

    unmountAssets()
    unmountDashboard()
  })
})
