import { afterEach, describe, expect, it, vi } from 'vitest'
import { basename, episodeLabel, episodeRanges, pad2, posterThumb, relativeTime } from './format'

describe('episodeRanges', () => {
  it('空清單回傳空字串', () => {
    expect(episodeRanges([])).toBe('')
  })

  it('連續集數合併成範圍', () => {
    expect(episodeRanges([2, 3, 4, 7, 9, 10])).toBe('2–4、7、9–10')
  })

  it('排序並去除重複', () => {
    expect(episodeRanges([5, 3, 4, 3])).toBe('3–5')
  })

  it('單集不加範圍', () => {
    expect(episodeRanges([6])).toBe('6')
  })
})

describe('posterThumb', () => {
  it('無路徑回傳空字串', () => {
    expect(posterThumb(null)).toBe('')
  })

  it('組出預設尺寸網址', () => {
    expect(posterThumb('/a.jpg')).toBe('https://image.tmdb.org/t/p/w92/a.jpg')
  })

  it('可指定尺寸', () => {
    expect(posterThumb('/a.jpg', 'w500')).toBe('https://image.tmdb.org/t/p/w500/a.jpg')
  })
})

describe('pad2', () => {
  it('補零', () => {
    expect(pad2(3)).toBe('03')
    expect(pad2(12)).toBe('12')
  })

  it('空值視為 0', () => {
    expect(pad2(null)).toBe('00')
    expect(pad2(undefined)).toBe('00')
  })
})

describe('episodeLabel', () => {
  it('季與集都沒有', () => {
    expect(episodeLabel(null, null)).toBe('')
  })

  it('只有季', () => {
    expect(episodeLabel(2, null)).toBe('S02')
  })

  it('季與集', () => {
    expect(episodeLabel(1, 5)).toBe('S01E05')
  })

  it('只有集時季補 00', () => {
    expect(episodeLabel(null, 7)).toBe('S00E07')
  })
})

describe('relativeTime', () => {
  afterEach(() => vi.useRealTimers())

  const at = (offset: number) => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-10T12:00:00Z'))
    return new Date(Date.now() - offset * 1000).toISOString()
  }

  it('空值回傳空字串', () => {
    expect(relativeTime(null)).toBe('')
  })

  it('一分鐘內', () => {
    expect(relativeTime(at(30))).toBe('剛剛')
  })

  it('分鐘', () => {
    expect(relativeTime(at(5 * 60))).toBe('5 分鐘前')
  })

  it('小時', () => {
    expect(relativeTime(at(3 * 3600))).toBe('3 小時前')
  })

  it('天', () => {
    expect(relativeTime(at(2 * 86400))).toBe('2 天前')
  })

  it('數字視為秒級時間戳', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-10T12:00:00Z'))
    const sec = Date.now() / 1000 - 600
    expect(relativeTime(sec)).toBe('10 分鐘前')
  })
})

describe('basename', () => {
  it('支援斜線與反斜線', () => {
    expect(basename('/a/b/c.mkv')).toBe('c.mkv')
    expect(basename('C:\\a\\b\\c.mkv')).toBe('c.mkv')
  })

  it('無目錄時原樣回傳', () => {
    expect(basename('c.mkv')).toBe('c.mkv')
  })
})
