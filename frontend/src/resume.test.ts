import { describe, expect, it } from 'vitest'
import type { ItemRef, MediaEntry } from './api'
import { buildResume } from './resume'

const entry = (media_type: string, tmdb_id: number, title: string) =>
  ({ media_type, tmdb_id, title }) as MediaEntry

const ref = (item_id: number, media_type: string, tmdb_id: number, season = 1, episode = 1) =>
  ({ item_id, media_type, tmdb_id, season, episode }) as ItemRef

const recent = (itemId: number, at: number, pos = 600, dur = 1200) => ({ itemId, pos, dur, at })

const entries = [entry('tv', 10, '熊家餐館'), entry('movie', 20, '沙丘')]

describe('buildResume', () => {
  it('依最近觀看時間排序', () => {
    const refs = [ref(1, 'tv', 10), ref(2, 'movie', 20)]
    const cards = buildResume([recent(1, 100), recent(2, 200)], refs, entries)
    expect(cards.map((c) => c.entry.title)).toEqual(['沙丘', '熊家餐館'])
  })

  it('同一部影集只留最近看的一集', () => {
    const refs = [ref(1, 'tv', 10, 3, 4), ref(2, 'tv', 10, 3, 5)]
    const cards = buildResume([recent(1, 100), recent(2, 200)], refs, entries)
    expect(cards).toHaveLength(1)
    expect(cards[0].itemId).toBe(2)
    expect(cards[0].note).toBe('S03E05 · 10:00')
  })

  it('電影備註只顯示時間', () => {
    const cards = buildResume([recent(2, 1, 75)], [ref(2, 'movie', 20)], entries)
    expect(cards[0].note).toBe('1:15')
  })

  it('略過查不到或已移出的項目', () => {
    const refs = [ref(1, 'tv', 10), ref(3, 'tv', 99)]
    const cards = buildResume([recent(1, 1), recent(2, 2), recent(3, 3)], refs, entries)
    expect(cards.map((c) => c.itemId)).toEqual([1])
  })

  it('進度百分比不超過一百', () => {
    const cards = buildResume([recent(2, 1, 900, 600)], [ref(2, 'movie', 20)], entries)
    expect(cards[0].progress).toBe(100)
  })

  it('總長未知時進度為零', () => {
    const cards = buildResume([recent(2, 1, 90, 0)], [ref(2, 'movie', 20)], entries)
    expect(cards[0].progress).toBe(0)
  })

  it('可限制張數', () => {
    const refs = [ref(1, 'tv', 10), ref(2, 'movie', 20)]
    expect(buildResume([recent(1, 1), recent(2, 2)], refs, entries, 1)).toHaveLength(1)
  })
})
