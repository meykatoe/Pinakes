export interface Settings {
  tmdb_api_key: string
  openai_api_key: string
  openai_base_url: string
  openai_model: string
  tmdb_language: string
  ai_enabled: boolean
  ai_daily_limit: number
  ai_auto_apply: boolean
  nfo_enabled: boolean
  nfo_images: boolean
  watch_enabled: boolean
  watch_interval: number
  stable_seconds: number
  auto_execute: boolean
  organize_mode: string
  conflict_policy: string
  public_base_url: string
  ffmpeg_path: string
  hwaccel: string
  precache_enabled: boolean
  precache_max_gb: number
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password: string
  smtp_security: string
  smtp_from: string
  notify_to: string
  notify_enabled: boolean
  telegram_enabled: boolean
  telegram_token: string
  telegram_chat_id: string
  discord_enabled: boolean
  discord_webhook: string
  sync_enabled: boolean
  sync_source_path: string
  sync_interval: number
  sync_auto_organize: boolean
  sync_rc_url: string
}

export interface TestResult {
  ok: boolean
  message: string
}

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

function describe(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => String(d?.msg ?? '').replace(/^Value error, /, ''))
      .filter(Boolean)
    if (msgs.length) return msgs.join('；')
  }
  if (status === 401) return '請先登入'
  if (status >= 500) return '伺服器錯誤，請稍後再試'
  return `請求失敗（HTTP ${status}）`
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function detail(res: Response): Promise<never> {
  const body = await res.json().catch(() => null)
  throw new ApiError(describe(body?.detail, res.status), res.status)
}

async function send<T>(url: string, method: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('無法連線到伺服器', 0)
  }
  if (res.status === 401 && !url.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event('pinakes:unauthorized'))
  }
  if (!res.ok) return detail(res)
  return res.status === 204 ? (undefined as T) : res.json()
}

export const getSettings = () => send<Settings>('/api/settings', 'GET')

export const saveSettings = (body: Partial<Settings>) =>
  send<Settings>('/api/settings', 'PUT', body)

export const testConnection = (
  target: 'tmdb' | 'openai' | 'smtp' | 'telegram' | 'discord',
) =>
  send<TestResult>(`/api/settings/test/${target}`, 'POST')

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

export interface Rule {
  id: number
  name: string
  pattern: string
  priority: number
  enabled: boolean
  media_type: 'movie' | 'tv' | null
}

export type RuleInput = Omit<Rule, 'id'>

export interface Naming {
  movie_template: string
  tv_template: string
}

export interface Preview {
  parsed: Record<string, string | number | null>
  rule: string | null
  target: string | null
  error: string | null
}

export const listRules = () => send<Rule[]>('/api/rules', 'GET')

export const createRule = (body: RuleInput) =>
  send<Rule>('/api/rules', 'POST', body)

export const updateRule = (id: number, body: RuleInput) =>
  send<Rule>(`/api/rules/${id}`, 'PUT', body)

export const deleteRule = (id: number) =>
  send<void>(`/api/rules/${id}`, 'DELETE')

export const getNaming = () => send<Naming>('/api/naming', 'GET')

export const saveNaming = (body: Naming) =>
  send<Naming>('/api/naming', 'PUT', body)

export const previewPath = (path: string) =>
  send<Preview>('/api/parse/preview', 'POST', { path })

export interface Candidate {
  tmdb_id: number
  media_type: string
  title: string
  original_title: string
  year: number | null
  overview: string
  poster_path: string | null
  popularity: number
  score: number
}

export interface MatchResult {
  parsed: Record<string, string | number | null>
  candidates: Candidate[]
  chosen: Candidate | null
  confident: boolean
  method: string | null
  reason: string
  target: string | null
  error: string | null
}

export const previewMatch = (path: string, tmdbId?: number) =>
  send<MatchResult>('/api/match/preview', 'POST', { path, tmdb_id: tmdbId })

export interface Item {
  id: number
  source_path: string
  status: string
  media_type: string
  tmdb_id: number | null
  title: string
  year: number | null
  season: number | null
  episode: number | null
  category_id: number | null
  target_path: string
  mode: string
  method: string | null
  reason: string
  error: string
  candidates: Candidate[]
  companions: { src: string; dst: string }[]
}

export const listItems = (status = '', q = '') =>
  send<Item[]>(
    `/api/organize/items?status=${encodeURIComponent(status)}&q=${encodeURIComponent(q)}`,
    'GET',
  )

export const getSummary = () => send<Record<string, number>>('/api/organize/summary', 'GET')

export interface ScanProgress {
  running: boolean
  done: number
  total: number
  current: string
}

export const getScanProgress = () =>
  send<ScanProgress>('/api/organize/scan/progress', 'GET')

export const searchTmdb = (q: string, mediaType: string, year?: number | null) =>
  send<Candidate[]>(
    `/api/tmdb/search?q=${encodeURIComponent(q)}&media_type=${mediaType}` +
      (year ? `&year=${year}` : ''),
    'GET',
  )

export const scan = () =>
  send<{ created: number; planned: number; pending_review: number }>(
    '/api/organize/scan',
    'POST',
  )

export const executeItem = (id: number) =>
  send<Item>(`/api/organize/items/${id}/execute`, 'POST')

export const executeAll = () =>
  send<{ done: number; skipped: number; failed: number }>(
    '/api/organize/execute',
    'POST',
  )

export const undoItem = (id: number) =>
  send<Item>(`/api/organize/items/${id}/undo`, 'POST')

export const skipItem = (id: number) =>
  send<Item>(`/api/organize/items/${id}/skip`, 'POST')

export const chooseItem = (
  id: number,
  body: { tmdb_id?: number; category_id?: number; media_type?: string },
) => send<Item>(`/api/organize/items/${id}/choose`, 'POST', body)

export interface WatchStatus {
  enabled: boolean
  running: boolean
  last_run: number | null
  last_error: string
  last_mail_error: string
  waiting: number
  last_processed: { id: number; source: string; status: string; target: string }[]
}

export const getWatchStatus = () => send<WatchStatus>('/api/watch/status', 'GET')

export interface SyncStatus {
  enabled: boolean
  running: boolean
  busy: boolean
  last_run: number | null
  last_error: string
  last_count: number
  last_failed: number
}

export const getSyncStatus = () => send<SyncStatus>('/api/sync/status', 'GET')

export const runSync = () =>
  send<{ started: boolean }>('/api/sync/run', 'POST')

export interface MediaEntry {
  media_type: 'movie' | 'tv'
  tmdb_id: number
  title: string
  original_title: string
  year: number | null
  overview: string
  rating: number
  genres: string[]
  poster_url: string | null
  backdrop_url: string | null
  category_id: number | null
  file_count: number
  added_at: string
}

export interface MediaDetail extends MediaEntry {
  tagline: string
  runtime: number | null
  seasons: number | null
  credits: { name: string; character: string }[]
  trailer_key: string
  files: {
    item_id: number
    season: number | null
    episode: number | null
    target_path: string
  }[]
}

export const listMedia = (q = '', sort = 'recent') =>
  send<MediaEntry[]>(
    `/api/library/media?q=${encodeURIComponent(q)}&sort=${sort}`,
    'GET',
  )

export const getMedia = (type: string, id: number) =>
  send<MediaDetail>(`/api/library/media/${type}/${id}`, 'GET')

export const scrapeAll = () =>
  send<{ scraped: number }>('/api/library/scrape', 'POST')

export const rebuildNfo = () =>
  send<{ started: boolean }>('/api/library/nfo', 'POST')

export const refreshMedia = (type: string, id: number) =>
  send<{ ok: boolean }>(`/api/library/media/${type}/${id}/refresh`, 'POST')

export interface Player {
  id: number
  name: string
  kind: 'link' | 'm3u'
  template: string
  enabled: boolean
}

export type PlayerInput = Omit<Player, 'id'>

export interface PlayInfo {
  title: string
  stream_url: string
  links: { player_id: number; name: string; kind: string; href: string }[]
}

export const listPlayers = () => send<Player[]>('/api/players', 'GET')

export const createPlayer = (body: PlayerInput) =>
  send<Player>('/api/players', 'POST', body)

export const updatePlayer = (id: number, body: PlayerInput) =>
  send<Player>(`/api/players/${id}`, 'PUT', body)

export const deletePlayer = (id: number) =>
  send<void>(`/api/players/${id}`, 'DELETE')

export const getPlayInfo = (itemId: number) =>
  send<PlayInfo>(`/api/play/${itemId}`, 'GET')

export const regenerateToken = () =>
  send<{ ok: boolean }>('/api/play/token/regenerate', 'POST')

export interface HlsInfo {
  mode: 'direct' | 'remux' | 'transcode'
  duration: number | null
  session_id: string | null
  playlist_url: string | null
  direct_url: string | null
  cached?: boolean
}

export const getTranscodeStatus = () =>
  send<{ available: boolean; ffmpeg: string | null; hwaccel: string | null }>(
    '/api/transcode/status',
    'GET',
  )

export const startHls = (itemId: number, start = 0) =>
  send<HlsInfo>(`/api/play/${itemId}/hls`, 'POST', { start })

export const keepAliveHls = (sid: string) =>
  send<{ ok: boolean }>(`/api/hls/${sid}/keepalive`, 'POST')

export const stopHls = (sid: string) =>
  fetch(`/api/hls/${sid}`, { method: 'DELETE', keepalive: true })

export interface AuthStatus {
  enabled: boolean
  authenticated: boolean
}

export const getAuthStatus = () => send<AuthStatus>('/api/auth/status', 'GET')

export const login = (password: string) =>
  send<AuthStatus>('/api/auth/login', 'POST', { password })

export const logout = () => send<void>('/api/auth/logout', 'POST')

export const changePassword = (current: string, next: string) =>
  send<AuthStatus>('/api/auth/password', 'PUT', { current, new: next })

export interface DirListing {
  path: string
  parent: string | null
  dirs: string[]
}

export const listDirs = (path = '') =>
  send<DirListing>(`/api/fs/dirs?path=${encodeURIComponent(path)}`, 'GET')

export const removeMedia = (type: string, id: number) =>
  send<{ removed: number; failed: number }>(`/api/library/media/${type}/${id}`, 'DELETE')

export const listSubtitles = (itemId: number) =>
  send<{ index: number; label: string }[]>(`/api/play/${itemId}/subtitles`, 'GET')
