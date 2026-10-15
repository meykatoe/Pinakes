export interface Settings {
  tmdb_api_key: string
  openai_api_key: string
  openai_base_url: string
  openai_model: string
  tmdb_language: string
}

export interface TestResult {
  ok: boolean
  message: string
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const getSettings = () => request<Settings>('/api/settings')

export const saveSettings = (body: Partial<Settings>) =>
  request<Settings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  })

export const testConnection = (target: 'tmdb' | 'openai') =>
  request<TestResult>(`/api/settings/test/${target}`, { method: 'POST' })
