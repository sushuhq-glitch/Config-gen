const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* keep default */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  leagues: () => request('/leagues'),
  fixtures: (params) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v)),
    ).toString()
    return request(`/fixtures${qs ? `?${qs}` : ''}`)
  },
  analyze: (payload) =>
    request('/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  liveRefresh: (fixtureId, targetOdds) =>
    request(`/fixtures/${encodeURIComponent(fixtureId)}/live?target_odds=${targetOdds}`),
  history: () => request('/history'),
}
