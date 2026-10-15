export const posterThumb = (path: string | null, size = 'w92') =>
  path ? `https://image.tmdb.org/t/p/${size}${path}` : ''

export const pad2 = (n: number | null | undefined) => String(n ?? 0).padStart(2, '0')

export function episodeLabel(season: number | null, episode: number | null): string {
  if (season === null && episode === null) return ''
  if (episode === null) return `S${pad2(season)}`
  return `S${pad2(season)}E${pad2(episode)}`
}

export function relativeTime(iso: string | number | null): string {
  if (iso === null) return ''
  const t = typeof iso === 'number' ? iso * 1000 : Date.parse(iso)
  const diff = (Date.now() - t) / 1000
  if (diff < 60) return '剛剛'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分鐘前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小時前`
  return `${Math.floor(diff / 86400)} 天前`
}

export function basename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}
