import { ref } from 'vue'

function current(): string[] {
  const raw = window.location.hash.replace(/^#\/?/, '')
  return raw.split('/').filter(Boolean)
}

export const route = ref<string[]>(current())

window.addEventListener('hashchange', () => {
  route.value = current()
})

export function go(...parts: string[]) {
  window.location.hash = '/' + parts.join('/')
}
