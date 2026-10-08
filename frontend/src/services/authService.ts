/**
 * Auth service — direct fetch calls to avoid circular dependency with api.ts.
 * Access token lives in api.ts memory; refresh token is an httpOnly cookie.
 */

const API = '/api/auth'

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  display_name?: string
  base_currency?: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    email: string
    display_name?: string
    base_currency: string
    created_at: string
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok || data.status === 'error') {
    throw new Error(data.message ?? 'Request failed')
  }
  return data.data as T
}

async function get<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = await res.json()
  if (!res.ok || data.status === 'error') {
    throw new Error(data.message ?? 'Request failed')
  }
  return data.data as T
}

export const authService = {
  login: (payload: LoginPayload) => post<AuthResponse>(`${API}/login`, payload),
  register: (payload: RegisterPayload) => post<AuthResponse>(`${API}/register`, payload),
  logout: () => post<void>(`${API}/logout`),
  refresh: () => post<{ access_token: string; token_type: string }>(`${API}/refresh`),
  me: (token: string) =>
    get<AuthResponse['user']>(`${API}/me`, token),
}
