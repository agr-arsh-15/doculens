const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const SLOW_MS = 3500

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// Set by the AuthProvider: returns the current access token (refreshing it if needed), and handles expiry.
let tokenProvider = async () => null
let onUnauthorized = () => {}
export function configureAuth({ getToken, unauthorized }) {
  tokenProvider = getToken
  onUnauthorized = unauthorized
}

// "Waking up the server" signal: requests that take longer than SLOW_MS (a sleeping free-tier host).
const slowListeners = new Set()
let slowCount = 0
export function onSlowRequests(listener) {
  slowListeners.add(listener)
  return () => slowListeners.delete(listener)
}
function trackSlow() {
  let flagged = false
  const timer = setTimeout(() => {
    flagged = true
    slowCount += 1
    slowListeners.forEach((l) => l(slowCount > 0))
  }, SLOW_MS)
  return () => {
    clearTimeout(timer)
    if (flagged) {
      slowCount -= 1
      slowListeners.forEach((l) => l(slowCount > 0))
    }
  }
}

async function authFetch(path, { method = 'GET', body, json, signal, headers = {} } = {}) {
  const token = await tokenProvider()
  const allHeaders = { ...headers }
  if (token) allHeaders.Authorization = `Bearer ${token}`
  if (json !== undefined) allHeaders['Content-Type'] = 'application/json'
  const done = trackSlow()
  try {
    return await fetch(`${BASE}${path}`, {
      method,
      signal,
      headers: allHeaders,
      body: json !== undefined ? JSON.stringify(json) : body,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError('Cannot reach the DocuLens server. Check your connection and try again.', 0)
  } finally {
    done()
  }
}

async function errorFrom(res) {
  let detail = `${res.status} ${res.statusText}`
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') detail = data.detail
    else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join('; ')
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 401) onUnauthorized()
  return new ApiError(detail, res.status)
}

async function request(path, options) {
  const res = await authFetch(path, options)
  if (!res.ok) throw await errorFrom(res)
  const type = res.headers.get('content-type') || ''
  return type.includes('application/json') ? res.json() : res
}

async function blob(path) {
  const res = await authFetch(path)
  if (!res.ok) throw await errorFrom(res)
  return res.blob()
}

function saveBlob(data, filename) {
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

// Server-sent events over fetch, so the Authorization header can be sent (EventSource cannot).
async function streamEvents(path, onEvent, signal) {
  const res = await authFetch(path, { signal, headers: { Accept: 'text/event-stream' } })
  if (!res.ok) throw await errorFrom(res)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const data = chunk.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trim()).join('\n')
      if (data) onEvent(JSON.parse(data))
    }
  }
}

export const api = {
  health: () => request('/api/health'),
  meta: () => request('/api/meta'),
  playbooks: () => request('/api/playbooks'),
  me: () => request('/api/me'),
  setLlmKey: (apiKey) => request('/api/me/llm-key', { method: 'PUT', json: { api_key: apiKey } }),
  deleteLlmKey: () => request('/api/me/llm-key', { method: 'DELETE' }),
  deleteAccount: () => request('/api/me', { method: 'DELETE' }),
  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/documents', { method: 'POST', body: form })
  },
  createTextDocument: (text, filename) => request('/api/documents/text', { method: 'POST', json: { text, filename } }),
  document: (id) => request(`/api/documents/${id}`),
  documentFile: (id) => blob(`/api/documents/${id}/file`),
  createAnalysis: (payload) => request('/api/analyses', { method: 'POST', json: payload }),
  analysis: (id) => request(`/api/analyses/${id}`),
  analysisStatus: (id) => request(`/api/analyses/${id}/status`),
  analyses: (q = '') => request(`/api/analyses?q=${encodeURIComponent(q)}`),
  deleteAnalysis: (id) => request(`/api/analyses/${id}`, { method: 'DELETE' }),
  streamEvents: (id, onEvent, signal) => streamEvents(`/api/analyses/${id}/events`, onEvent, signal),
  chat: (id, question, history) => request(`/api/analyses/${id}/chat`, { method: 'POST', json: { question, history } }),
  downloadReport: async (id, filename) => saveBlob(await blob(`/api/analyses/${id}/report.pdf`), filename),
  lab: (id) => request(`/api/analyses/${id}/lab`),
  compare: (a, b) => request('/api/compare', { method: 'POST', json: { analysis_a: a, analysis_b: b } }),
  admin: {
    kpis: () => request('/api/admin/kpis'),
    users: (q = '', offset = 0) => request(`/api/admin/users?q=${encodeURIComponent(q)}&offset=${offset}&limit=25`),
    updateUser: (id, patch) => request(`/api/admin/users/${id}`, { method: 'PATCH', json: patch }),
    settings: () => request('/api/admin/settings'),
    saveSettings: (body) => request('/api/admin/settings', { method: 'PUT', json: body }),
  },
}
