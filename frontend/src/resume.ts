import type { ItemRef, MediaEntry } from './api'
import { episodeLabel } from './format'
import { formatTime, type RecentItem } from './playback'

export interface ResumeCard {
  entry: MediaEntry
  itemId: number
  progress: number
  note: string
}

export function buildResume(
  recent: RecentItem[],
  refs: ItemRef[],
  entries: MediaEntry[],
  limit = 12,
): ResumeCard[] {
  const byItem = new Map(refs.map((r) => [r.item_id, r]))
  const byWork = new Map(entries.map((e) => [`${e.media_type}:${e.tmdb_id}`, e]))
  const seen = new Set<string>()
  const cards: ResumeCard[] = []
  for (const r of [...recent].sort((a, b) => b.at - a.at)) {
    const ref = byItem.get(r.itemId)
    if (!ref) continue
    const key = `${ref.media_type}:${ref.tmdb_id}`
    const entry = byWork.get(key)
    if (!entry || seen.has(key)) continue
    seen.add(key)
    const ep = ref.media_type === 'tv' ? episodeLabel(ref.season, ref.episode) : ''
    cards.push({
      entry,
      itemId: r.itemId,
      progress: r.dur > 0 ? Math.min(100, (r.pos / r.dur) * 100) : 0,
      note: [ep, formatTime(r.pos)].filter(Boolean).join(' · '),
    })
    if (cards.length >= limit) break
  }
  return cards
}
