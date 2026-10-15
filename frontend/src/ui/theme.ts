import { ref, watch } from 'vue'

type Theme = 'dark' | 'light'
const KEY = 'pinakes-theme'

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // 無法讀取
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export const theme = ref<Theme>(initial())

function apply(value: Theme) {
  document.documentElement.dataset.theme = value
}

apply(theme.value)

watch(theme, (value) => {
  apply(value)
  try {
    localStorage.setItem(KEY, value)
  } catch {
    // 無法寫入
  }
})

export const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}
