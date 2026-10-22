import { describe, expect, it } from 'vitest'
import { answer, confirm, pending } from './confirm'

describe('confirm', () => {
  it('確定時回傳 true', async () => {
    const p = confirm('刪除？', '刪除', true)
    expect(pending.current).toMatchObject({ text: '刪除？', ok: '刪除', danger: true })
    answer(true)
    expect(await p).toBe(true)
    expect(pending.current).toBeNull()
  })

  it('取消時回傳 false', async () => {
    const p = confirm('繼續？')
    answer(false)
    expect(await p).toBe(false)
  })

  it('新的詢問會取消前一個', async () => {
    const first = confirm('第一個')
    const second = confirm('第二個')
    expect(await first).toBe(false)
    answer(true)
    expect(await second).toBe(true)
  })
})
