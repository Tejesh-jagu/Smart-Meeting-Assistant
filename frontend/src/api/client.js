const localApiUrl = typeof window === 'undefined'
  ? 'http://localhost:8000'
  : `${window.location.protocol}//${window.location.hostname}:${import.meta.env.VITE_API_PORT || 8000}`

export const API_URL = (
  import.meta.env.VITE_API_PORT ? localApiUrl : import.meta.env.VITE_API_URL || localApiUrl
).replace(/\/$/, '')


export function responseMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join(' ') || fallback
  }
  return fallback
}

export async function readApiJson(response, fallback) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new Error(responseMessage(payload, fallback))
  if (payload === null) throw new Error('The server returned an invalid response.')
  return payload
}


export function createApiClient(getCsrfToken, onUnauthorized) {
  return async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {})
    const method = (options.method || 'GET').toUpperCase()
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      headers.set('X-CSRF-Token', getCsrfToken())
    }
    const response = await fetch(url, { ...options, headers, credentials: 'include' })
    if (response.status === 401) await onUnauthorized()
    return response
  }
}
