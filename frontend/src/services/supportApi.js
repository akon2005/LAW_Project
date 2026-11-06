/**
 * Support assistant API client.
 *
 * One place that knows the /api/support endpoints and how a session id survives
 * a page reload. No API keys live here — generation happens on the backend, and
 * nothing provider-related is ever shipped to the browser.
 */
import { API_BASE } from './apiBase.js'
import { createSessionId } from '../utils/supportChat.js'

const SESSION_KEY = 'vidhiveda.support.session'

/** Session id for the current tab. Kept in sessionStorage: no cross-tab identity. */
export function getSessionId() {
  if (typeof window === 'undefined') return ''
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY)
    if (existing) return existing
    const created = createSessionId()
    window.sessionStorage.setItem(SESSION_KEY, created)
    return created
  } catch {
    // Storage disabled (private mode, blocked cookies): use an in-memory id.
    return createSessionId()
  }
}

export function forgetSession() {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.removeItem(SESSION_KEY)
  } catch {
    /* ignore */
  }
}

class SupportError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'SupportError'
    this.status = status
    this.payload = payload
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (err) {
    throw new SupportError('Network error: could not reach the support backend.', 0, null)
  }

  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const detail = payload && typeof payload.detail === 'string' ? payload.detail : null
    throw new SupportError(detail || `Support request failed (${response.status}).`, response.status, payload)
  }
  return payload
}

export const supportApi = {
  /** Ask the support assistant. Throws SupportError with a real status. */
  chat(payload, { signal } = {}) {
    return request('/api/support/chat', { method: 'POST', body: JSON.stringify(payload), signal })
  },

  health({ probe = false } = {}) {
    return request(`/api/support/health${probe ? '?probe=true' : ''}`)
  },

  articles({ category, q, limit = 100 } = {}) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (category) params.set('category', category)
    if (q) params.set('q', q)
    return request(`/api/support/articles?${params.toString()}`)
  },

  article(id) {
    return request(`/api/support/articles/${encodeURIComponent(id)}`)
  },

  examples(category) {
    const params = category ? `?category=${encodeURIComponent(category)}` : ''
    return request(`/api/support/examples${params}`)
  },

  features() {
    return request('/api/support/features')
  },

  /**
   * File a problem report. Resolves only when the backend confirms it stored the
   * record; there is no optimistic success state.
   */
  report(payload, { sessionId } = {}) {
    const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
    return request(`/api/support/report${params}`, {
      method: 'POST',
      body: JSON.stringify({
        category: payload.category,
        title: payload.title,
        description: payload.description,
        steps: payload.steps || null,
        page: payload.page || null,
        contact: payload.contact || null,
      }),
    })
  },

  feedback(rating, { comment, messageId, sessionId, page } = {}) {
    const params = new URLSearchParams()
    if (sessionId) params.set('session_id', sessionId)
    if (page) params.set('page', page)
    const query = params.toString()
    return request(`/api/support/feedback${query ? `?${query}` : ''}`, {
      method: 'POST',
      body: JSON.stringify({ rating, comment: comment || null, message_id: messageId || null }),
    })
  },

  resetSession(sessionId) {
    const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
    return request(`/api/support/session/reset${params}`, { method: 'POST' })
  },
}

export { SupportError }
export default supportApi
