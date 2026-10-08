import { useEffect } from 'react'
import { useAuthStore } from '@/store'
import { initAuthSync, type AuthSyncMessage } from '@/services/authSync'

/**
 * Runs checkAuth on mount — silently restores a session from the
 * httpOnly refresh-token cookie if one exists.
 * Also subscribes to cross-tab auth events (LOGIN, LOGOUT, SESSION_INVALIDATED)
 * so that state across tabs in the same browser profile stays strictly in sync.
 */
export default function AuthInitializer() {
  const checkAuth = useAuthStore((s) => s.checkAuth)
  const clearAuth = useAuthStore((s) => s.clearAuth)

  useEffect(() => {
    // 1. Initial session restore
    checkAuth()

    // 2. Cross-tab synchronization
    const unsubscribe = initAuthSync((msg: AuthSyncMessage) => {
      const currentUser = useAuthStore.getState().user

      if (msg.type === 'LOGIN') {
        // If another tab logged in with a different user, invalidate stale memory state
        // and restore session for the newly active account.
        if (currentUser?.id !== msg.userId) {
          clearAuth()
          checkAuth()
        }
      } else if (msg.type === 'LOGOUT' || msg.type === 'SESSION_INVALIDATED') {
        clearAuth()
      }
    })

    return () => {
      unsubscribe()
    }
  }, [checkAuth, clearAuth])

  return null
}

