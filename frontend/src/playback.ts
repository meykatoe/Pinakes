const KEY = 'pinakes-progress'

interface Entry {
  pos: number
  dur: number
  at: number
}

function all(): Record<string, Entry> {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch {
    return {}
  }
}

export function getProgress(itemId: number): Entry | null {
  return all()[itemId] ?? null
}

export function saveProgress(itemId: number, pos: number, dur: number) {
  const data = all()
  if (dur > 0 && pos > dur - 90) delete data[itemId]
  else if (pos > 30) data[itemId] = { pos, dur, at: Date.now() }
  else return
  const keys = Object.keys(data)
  if (keys.length > 500) {
    keys.sort((a, b) => data[a].at - data[b].at)
    for (const k of keys.slice(0, keys.length - 500)) delete data[k]
  }
  try {
    localStorage.setItem(KEY, JSON.stringify(data))
  } catch {
    // 無法寫入
  }
}

export function formatTime(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${r}` : `${m}:${r}`
}

export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }
  const el = document.createElement('textarea')
  el.value = text
  el.style.position = 'fixed'
  el.style.opacity = '0'
  document.body.appendChild(el)
  el.select()
  document.execCommand('copy')
  el.remove()
}
