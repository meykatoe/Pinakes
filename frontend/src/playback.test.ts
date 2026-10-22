import { beforeEach, describe, expect, it, vi } from 'vitest'
import { copyText, formatTime, getProgress, saveProgress } from './playback'

beforeEach(() => localStorage.clear())

describe('formatTime', () => {
  it('不滿一小時', () => {
    expect(formatTime(65)).toBe('1:05')
  })

  it('滿一小時', () => {
    expect(formatTime(3725)).toBe('1:02:05')
  })

  it('負數與小數', () => {
    expect(formatTime(-5)).toBe('0:00')
    expect(formatTime(9.9)).toBe('0:09')
  })
})

describe('saveProgress', () => {
  it('前 30 秒不記錄', () => {
    saveProgress(1, 20, 3600)
    expect(getProgress(1)).toBeNull()
  })

  it('記錄位置', () => {
    saveProgress(1, 120, 3600)
    expect(getProgress(1)).toMatchObject({ pos: 120, dur: 3600 })
  })

  it('接近片尾時清除紀錄', () => {
    saveProgress(1, 120, 3600)
    saveProgress(1, 3550, 3600)
    expect(getProgress(1)).toBeNull()
  })

  it('最多保留 500 筆並丟棄最舊的', () => {
    vi.useFakeTimers()
    for (let i = 1; i <= 502; i++) {
      vi.setSystemTime(i * 1000)
      saveProgress(i, 100, 3600)
    }
    vi.useRealTimers()
    expect(getProgress(1)).toBeNull()
    expect(getProgress(2)).toBeNull()
    expect(getProgress(3)).not.toBeNull()
    expect(getProgress(502)).not.toBeNull()
  })

  it('資料損毀時當作沒有紀錄', () => {
    localStorage.setItem('pinakes-progress', '{壞掉')
    expect(getProgress(1)).toBeNull()
  })
})

describe('copyText', () => {
  it('安全環境使用剪貼簿 API', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    vi.stubGlobal('isSecureContext', true)
    await copyText('abc')
    expect(writeText).toHaveBeenCalledWith('abc')
    vi.unstubAllGlobals()
  })

  it('非安全環境退回 execCommand', async () => {
    vi.stubGlobal('navigator', {})
    const exec = vi.fn().mockReturnValue(true)
    document.execCommand = exec
    await copyText('abc')
    expect(exec).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull()
    vi.unstubAllGlobals()
  })
})
