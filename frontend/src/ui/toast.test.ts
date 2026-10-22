import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dismiss, toast, toastError, toasts } from './toast'

beforeEach(() => {
  vi.useFakeTimers()
  toasts.splice(0)
})

afterEach(() => vi.useRealTimers())

describe('toast', () => {
  it('到時間自動消失', () => {
    toast('完成')
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(3500)
    expect(toasts).toHaveLength(0)
  })

  it('錯誤訊息停留更久', () => {
    toast('壞了', 'error')
    vi.advanceTimersByTime(3500)
    expect(toasts).toHaveLength(1)
    vi.advanceTimersByTime(2500)
    expect(toasts).toHaveLength(0)
  })

  it('最多同時四則，擠掉最舊的', () => {
    for (let i = 1; i <= 5; i++) toast(`第 ${i} 則`)
    expect(toasts).toHaveLength(4)
    expect(toasts[0].text).toBe('第 2 則')
  })

  it('可手動關閉', () => {
    toast('a')
    dismiss(toasts[0].id)
    expect(toasts).toHaveLength(0)
  })

  it('toastError 取出 Error 的訊息', () => {
    toastError(new Error('連線失敗'))
    expect(toasts[0]).toMatchObject({ kind: 'error', text: '連線失敗' })
  })

  it('toastError 接受非 Error 值', () => {
    toastError('字串錯誤')
    expect(toasts[0].text).toBe('字串錯誤')
  })
})
