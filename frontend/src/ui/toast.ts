import { reactive } from 'vue'

export type ToastKind = 'ok' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  text: string
}

export const toasts = reactive<Toast[]>([])
let seq = 0

export function dismiss(id: number) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i >= 0) toasts.splice(i, 1)
}

export function toast(text: string, kind: ToastKind = 'ok', ms = 3500) {
  const id = ++seq
  toasts.push({ id, kind, text })
  if (toasts.length > 4) toasts.shift()
  window.setTimeout(() => dismiss(id), kind === 'error' ? ms + 2500 : ms)
}

export const toastError = (err: unknown) =>
  toast(err instanceof Error ? err.message : String(err), 'error')
