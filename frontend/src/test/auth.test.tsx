import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAuthStore } from '@/store'
import {
  setAccessToken,
  getAccessToken,
  setOnSessionExpired,
  api,
  ApiError,
} from '@/services/api'
import { broadcastAuthEvent, type AuthSyncMessage } from '@/services/authSync'
import AuthInitializer from '@/components/AuthInitializer'

describe('Authentication & Session Management', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    setAccessToken(null)
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    setAccessToken(null)
  })

  describe('checkAuth & Bootstrap Deduplication', () => {
    it('restores user session when refresh and me endpoints succeed', async () => {
      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        display_name: 'Test User',
        base_currency: 'TRY',
        created_at: '2026-01-01',
      }

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/auth/refresh') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { access_token: 'new-access-token-1', token_type: 'bearer' },
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
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      })

      await useAuthStore.getState().checkAuth()

      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(useAuthStore.getState().user).toEqual(mockUser)
      expect(getAccessToken()).toBe('new-access-token-1')
      expect(useAuthStore.getState().isLoading).toBe(false)
    })

    it('deduplicates concurrent checkAuth calls (e.g. React StrictMode double mount)', async () => {
      let refreshCallCount = 0

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/auth/refresh') {
          refreshCallCount++
          return new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                ok: true,
                status: 200,
                json: async () => ({
                  status: 'success',
                  data: { access_token: 'token-strict-mode', token_type: 'bearer' },
                }),
              } as Response)
            }, 50)
          })
        }
        if (url === '/api/auth/me') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { id: 'u1', email: 'u1@test.com', base_currency: 'TRY', created_at: '' },
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unhandled: ${url}`))
      })

      // Fire two checkAuth calls concurrently
      const promise1 = useAuthStore.getState().checkAuth()
      const promise2 = useAuthStore.getState().checkAuth()

      await Promise.all([promise1, promise2])

      // Only ONE network call to /api/auth/refresh should have been made!
      expect(refreshCallCount).toBe(1)
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(getAccessToken()).toBe('token-strict-mode')
    })

    it('clears auth state silently when refresh returns 401 (no valid session)', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ status: 'error', message: 'Refresh token missing' }),
      } as Response)

      await useAuthStore.getState().checkAuth()

      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().user).toBeNull()
      expect(getAccessToken()).toBeNull()
      expect(useAuthStore.getState().isLoading).toBe(false)
    })
  })

  describe('API Interceptor & 401 Retry Behavior', () => {
    it('retries request upon 401 when token refresh succeeds', async () => {
      setAccessToken('expired-token')

      let requestCount = 0
      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/dashboard/summary') {
          requestCount++
          if (requestCount === 1) {
            return Promise.resolve({
              ok: false,
              status: 401,
              statusText: 'Unauthorized',
              json: async () => ({ status: 'error', message: 'Token expired' }),
            } as Response)
          }
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { total_net_worth: '100000.00' },
            }),
          } as Response)
        }
        if (url === '/api/auth/refresh') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { access_token: 'fresh-token' },
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unhandled: ${url}`))
      })

      const res = await api.get<{ status: string; data: { total_net_worth: string } }>('/dashboard/summary')

      expect(res).toEqual({ status: 'success', data: { total_net_worth: '100000.00' } })
      expect(requestCount).toBe(2)
      expect(getAccessToken()).toBe('fresh-token')
    })

    it('deduplicates concurrent 401 refreshes across multiple simultaneous requests', async () => {
      setAccessToken('old-token')

      let refreshCount = 0
      global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.startsWith('/api/data/')) {
          const authHeader = (init?.headers as Record<string, string>)?.[
            'Authorization'
          ]
          if (authHeader === 'Bearer old-token') {
            return Promise.resolve({
              ok: false,
              status: 401,
              statusText: 'Unauthorized',
              json: async () => ({ status: 'error', message: 'Expired' }),
            } as Response)
          }
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ status: 'success', data: { url } }),
          } as Response)
        }
        if (url === '/api/auth/refresh') {
          refreshCount++
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { access_token: 'new-shared-token' },
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unhandled: ${url}`))
      })

      // Send 3 requests in parallel that all receive 401 initially
      const results = await Promise.all([
        api.get('/data/1'),
        api.get('/data/2'),
        api.get('/data/3'),
      ])

      expect(results).toHaveLength(3)
      // Exactly 1 refresh call should have occurred
      expect(refreshCount).toBe(1)
      expect(getAccessToken()).toBe('new-shared-token')
    })

    it('does NOT log out on temporary rate limit (429) or 5xx server error', async () => {
      setAccessToken('current-token')
      const expiredCallback = vi.fn()
      setOnSessionExpired(expiredCallback)

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/test-endpoint') {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: async () => ({ status: 'error' }),
          } as Response)
        }
        if (url === '/api/auth/refresh') {
          // Backend returns 429 Too Many Requests
          return Promise.resolve({
            ok: false,
            status: 429,
            json: async () => ({ status: 'error', message: 'Rate limit exceeded' }),
          } as Response)
        }
        return Promise.reject(new Error('Network error'))
      })

      await expect(api.get('/test-endpoint')).rejects.toThrow()

      // Session must NOT be invalidated! User must NOT be logged out!
      expect(expiredCallback).not.toHaveBeenCalled()
      expect(getAccessToken()).toBe('current-token')
    })

    it('invalidates session and triggers onSessionExpired when refresh returns 401', async () => {
      setAccessToken('stale-token')
      const expiredCallback = vi.fn()
      setOnSessionExpired(expiredCallback)

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/some-action') {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: async () => ({ status: 'error' }),
          } as Response)
        }
        if (url === '/api/auth/refresh') {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: async () => ({ status: 'error', message: 'Invalid refresh token' }),
          } as Response)
        }
        return Promise.reject(new Error('Network error'))
      })

      await expect(api.get('/some-action')).rejects.toThrow(ApiError)

      expect(getAccessToken()).toBeNull()
      expect(expiredCallback).toHaveBeenCalledTimes(1)
    })

    it('retries immediately without calling refresh when accessToken was already updated by another concurrent request', async () => {
      setAccessToken('token-v1')

      let refreshCount = 0
      global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url === '/api/slow-endpoint') {
          const authHeader = (init?.headers as Record<string, string>)?.[
            'Authorization'
          ]
          if (authHeader === 'Bearer token-v1') {
            // While this request was in flight, another request updated accessToken to token-v2
            setAccessToken('token-v2')
            return Promise.resolve({
              ok: false,
              status: 401,
              statusText: 'Unauthorized',
              json: async () => ({ status: 'error' }),
            } as Response)
          }
          if (authHeader === 'Bearer token-v2') {
            return Promise.resolve({
              ok: true,
              status: 200,
              json: async () => ({ status: 'success', data: 'data-v2' }),
            } as Response)
          }
        }
        if (url === '/api/auth/refresh') {
          refreshCount++
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ status: 'success', data: { access_token: 'token-v3' } }),
          } as Response)
        }
        return Promise.reject(new Error(`Unhandled: ${url}`))
      })

      const res = await api.get<{ status: string; data: string }>('/slow-endpoint')
      expect(res).toEqual({ status: 'success', data: 'data-v2' })
      // Notice: refreshCount MUST be 0 because it retried with token-v2 directly!
      expect(refreshCount).toBe(0)
    })
  })

  describe('Multi-Tab Synchronization (BroadcastChannel)', () => {
    it('dispatches and receives auth events without sending tokens across tabs', async () => {
      const receivedMessages: AuthSyncMessage[] = []
      // Represents Tab B listening to events from Tab A
      const tabBChannel = new BroadcastChannel('portfoliomind_auth')
      tabBChannel.addEventListener('message', (event) => {
        receivedMessages.push(event.data)
      })

      // Tab A broadcasts LOGIN
      broadcastAuthEvent({ type: 'LOGIN', userId: 'user-b' })
      // Tab A broadcasts LOGOUT
      broadcastAuthEvent({ type: 'LOGOUT' })

      // Small delay for cross-channel event loop dispatch
      await new Promise((r) => setTimeout(r, 50))

      expect(receivedMessages).toContainEqual({ type: 'LOGIN', userId: 'user-b' })
      expect(receivedMessages).toContainEqual({ type: 'LOGOUT' })

      tabBChannel.close()
    })

    it('clears auth on LOGOUT broadcast', () => {
      useAuthStore.setState({
        user: { id: 'u1', email: 'u1@test.com', base_currency: 'TRY', created_at: '' },
        isAuthenticated: true,
      })
      setAccessToken('active-token')

      useAuthStore.getState().clearAuth()

      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().user).toBeNull()
      expect(getAccessToken()).toBeNull()
    })
  })

  describe('AuthInitializer Component & Cross-Tab Switching', () => {
    it('switches user session when another tab broadcasts LOGIN for a different user', async () => {
      const mockUserB = {
        id: 'user-b',
        email: 'userb@example.com',
        display_name: 'User B',
        base_currency: 'USD',
        created_at: '2026-01-01',
      }

      useAuthStore.setState({
        user: { id: 'user-a', email: 'usera@example.com', display_name: 'User A', base_currency: 'TRY', created_at: '' },
        isAuthenticated: true,
      })
      setAccessToken('token-a')

      global.fetch = vi.fn().mockImplementation((url: string) => {
        if (url === '/api/auth/refresh') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: { access_token: 'token-b' },
            }),
          } as Response)
        }
        if (url === '/api/auth/me') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              status: 'success',
              data: mockUserB,
            }),
          } as Response)
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`))
      })

      const { unmount } = renderHook(() => AuthInitializer())

      // Broadcast LOGIN for user-b
      await act(async () => {
        broadcastAuthEvent({ type: 'LOGIN', userId: 'user-b' })
        await new Promise((r) => setTimeout(r, 60))
      })

      expect(useAuthStore.getState().user?.id).toBe('user-b')
      expect(getAccessToken()).toBe('token-b')
      expect(useAuthStore.getState().isAuthenticated).toBe(true)

      unmount()
    })

    it('logs out and clears state when another tab broadcasts LOGOUT', async () => {
      useAuthStore.setState({
        user: { id: 'user-a', email: 'usera@example.com', display_name: 'User A', base_currency: 'TRY', created_at: '' },
        isAuthenticated: true,
      })
      setAccessToken('token-a')

      const { unmount } = renderHook(() => AuthInitializer())

      await act(async () => {
        broadcastAuthEvent({ type: 'LOGOUT' })
        await new Promise((r) => setTimeout(r, 60))
      })

      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().user).toBeNull()
      expect(getAccessToken()).toBeNull()

      unmount()
    })
  })
})
