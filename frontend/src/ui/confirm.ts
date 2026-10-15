import { reactive } from 'vue'

interface Pending {
  text: string
  ok: string
  danger: boolean
  resolve: (v: boolean) => void
}

export const pending = reactive<{ current: Pending | null }>({ current: null })

export function confirm(text: string, ok = '確定', danger = false): Promise<boolean> {
  pending.current?.resolve(false)
  return new Promise((resolve) => {
    pending.current = { text, ok, danger, resolve }
  })
}

export function answer(value: boolean) {
  pending.current?.resolve(value)
  pending.current = null
}
