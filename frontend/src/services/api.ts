import type { ApiResponse } from '@/types'

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly code?: string,
    public readonly details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function extractErrorMessage(err: unknown, fallback = 'İşlem başarısız oldu'): string {
  if (err instanceof ApiError && err.message) {
    return err.message
  }
  if (err instanceof Error && err.message) {
    return err.message
  }
  if (typeof err === 'object' && err !== null) {
    const anyErr = err as Record<string, any>
    if (anyErr.response?.data?.message) return anyErr.response.data.message
    if (anyErr.response?.data?.detail) return anyErr.response.data.detail
    if (anyErr.message) return anyErr.message
  }
  return fallback
}

// Access token stored in memory only (never localStorage) for security
let accessToken: string | null = null
let _onSessionExpired: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

export function setOnSessionExpired(callback: (() => void) | null): void {
  _onSessionExpired = callback
}

// ---------------------------------------------------------------------------
// Refresh interceptor — called automatically on 401 responses
// ---------------------------------------------------------------------------

let _refreshing: Promise<boolean> | null = null

async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  if (typeof navigator !== 'undefined' && navigator.locks?.request) {
    return navigator.locks.request('portfoliomind_auth_refresh', fn)
  }
  return fn()
}

export async function tryRefresh(): Promise<boolean> {
  // Deduplicate concurrent refresh attempts within this tab
  if (_refreshing) return _refreshing

  _refreshing = withRefreshLock(async () => {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      })

      if (res.status === 401) {
        // Refresh token is truly invalid or expired
        setAccessToken(null)
        _onSessionExpired?.()
        return false
      }

      if (!res.ok) {
        // Rate limit 429 or temporary server error (5xx) — do NOT log out!
        return false
      }

      const data = await res.json()
      if (data.status === 'success' && data.data?.access_token) {
        setAccessToken(data.data.access_token)
        return true
      }

      return false
    } catch {
      // Network error or offline — do NOT log out!
      return false
    }
  }).finally(() => {
    _refreshing = null
  })

  return _refreshing
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {},
  isRetry = false,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const tokenUsed = accessToken
  if (tokenUsed) {
    headers['Authorization'] = `Bearer ${tokenUsed}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  // Automatic token refresh on 401 — but not for auth endpoints or retries
  if (
    response.status === 401 &&
    !isRetry &&
    !path.startsWith('/auth/')
  ) {
    // If token was already updated by another concurrent request while this was in flight,
    // retry immediately with the new token without calling refresh again!
    if (accessToken && accessToken !== tokenUsed) {
      return request<T>(path, options, true)
    }

    const refreshed = await tryRefresh()
    if (refreshed) {
      return request<T>(path, options, true)
    }

    // If refresh failed because session is truly dead (accessToken cleared)
    if (!accessToken) {
      throw new ApiError('Session expired. Please log in again.', 401)
    }

    // If refresh failed due to temporary issue (e.g. rate limit), throw without logout
    throw new ApiError('İşlem başarısız oldu. Lütfen tekrar deneyin.', response.status)
  }

  let data: (ApiResponse<T> & { code?: string; details?: unknown; message?: string }) | null = null
  try {
    data = await response.json()
  } catch {
    data = { status: 'error', message: response.statusText || 'An unexpected error occurred' }
  }

  if (!response.ok || !data || data.status === 'error') {
    throw new ApiError(
      data?.message ?? 'An unexpected error occurred',
      response.status,
      data?.code,
      data?.details,
    )
  }

  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
