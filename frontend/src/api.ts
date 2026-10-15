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

export interface Paths {
  inbox_path: string
  library_path: string
  same_device: boolean | null
}

export interface Category {
  id: number
  name: string
  media_type: 'movie' | 'tv'
  subdir: string
  builtin: boolean
}

export type CategoryInput = Omit<Category, 'id' | 'builtin'>

async function detail(res: Response): Promise<never> {
  const body = await res.json().catch(() => null)
  throw new Error(body?.detail ?? `HTTP ${res.status}`)
}

async function send<T>(url: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) return detail(res)
  return res.status === 204 ? (undefined as T) : res.json()
}

export const getPaths = () => send<Paths>('/api/library/paths', 'GET')

export const savePaths = (body: Pick<Paths, 'inbox_path' | 'library_path'>) =>
  send<Paths>('/api/library/paths', 'PUT', body)

export const listCategories = () => send<Category[]>('/api/categories', 'GET')

export const createCategory = (body: CategoryInput) =>
  send<Category>('/api/categories', 'POST', body)

export const updateCategory = (id: number, body: CategoryInput) =>
  send<Category>(`/api/categories/${id}`, 'PUT', body)

export const deleteCategory = (id: number) =>
  send<void>(`/api/categories/${id}`, 'DELETE')
