import { create } from 'zustand'
import type { User } from '@/types'
import { authService, type LoginPayload, type RegisterPayload } from '@/services/authService'
import { getAccessToken, setAccessToken, setOnSessionExpired, tryRefresh } from '@/services/api'
import { broadcastAuthEvent } from '@/services/authSync'
import { triggerLoginPriceRefresh, resetPriceRefreshState } from '@/services/priceService'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  clearAuth: () => void
}

let _checkAuthPromise: Promise<void> | null = null

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (payload) => {
    const data = await authService.login(payload)
    setAccessToken(data.access_token)
    set({ user: data.user, isAuthenticated: true })
    broadcastAuthEvent({ type: 'LOGIN', userId: data.user.id })
    // Background price refresh for user's auto-fetchable assets — non-blocking
    void triggerLoginPriceRefresh()
  },

  register: async (payload) => {
    const data = await authService.register(payload)
    setAccessToken(data.access_token)
    set({ user: data.user, isAuthenticated: true })
    broadcastAuthEvent({ type: 'LOGIN', userId: data.user.id })
  },

  logout: async () => {
    try {
      await authService.logout()
    } finally {
      resetPriceRefreshState()
      setAccessToken(null)
      set({ user: null, isAuthenticated: false })
      broadcastAuthEvent({ type: 'LOGOUT' })
    }
  },

  /**
   * Called once on app startup — attempts to restore session via refresh token
   * cookie, then fetches the current user profile.
   * Deduplicated so concurrent calls (e.g. React StrictMode) share the single in-flight promise.
   */
  checkAuth: async () => {
    if (_checkAuthPromise) return _checkAuthPromise

    _checkAuthPromise = (async () => {
      set({ isLoading: true })
      try {
        const ok = await tryRefresh()
        if (ok) {
          const token = getAccessToken()
          if (token) {
            const user = await authService.me(token)
            set({ user, isAuthenticated: true })
            return
          }
        }
        // No valid session — silently stay logged out
        setAccessToken(null)
        set({ user: null, isAuthenticated: false })
      } catch {
        setAccessToken(null)
        set({ user: null, isAuthenticated: false })
      } finally {
        set({ isLoading: false })
        _checkAuthPromise = null
      }
    })()

    return _checkAuthPromise
  },

  clearAuth: () => {
    resetPriceRefreshState()
    setAccessToken(null)
    set({ user: null, isAuthenticated: false })
  },
}))

// Wire api.ts session expiration to store and cross-tab sync
setOnSessionExpired(() => {
  useAuthStore.getState().clearAuth()
  broadcastAuthEvent({ type: 'SESSION_INVALIDATED' })
})

