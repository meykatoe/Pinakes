<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getPaths, getSettings, logout } from './api'
import { auth, refreshAuth } from './auth'
import LoginView from './components/LoginView.vue'
import OrganizePanel from './components/OrganizePanel.vue'
import PosterWall from './components/PosterWall.vue'
import SettingsPage from './components/SettingsPage.vue'
import SetupWizard from './components/SetupWizard.vue'
import { go, route } from './router'
import { theme, toggleTheme } from './ui/theme'
import UiLayer from './ui/UiLayer.vue'

const tabs = [
  { id: 'wall', label: '海報牆' },
  { id: 'organize', label: '整理' },
  { id: 'settings', label: '設定' },
]

const setup = ref(false)

onMounted(() => {
  refreshAuth().catch(() => {
    auth.value = { enabled: false, authenticated: true }
  })
})

// 首次啟動引導
watch(
  () => auth.value?.authenticated,
  async (ok) => {
    if (!ok) return
    try {
      if (localStorage.getItem('pinakes-setup-done')) return
    } catch {
      // 無法讀取
    }
    try {
      const [s, p] = await Promise.all([getSettings(), getPaths()])
      setup.value = !s.tmdb_api_key || !p.inbox_path || !p.library_path
    } catch {
      // 忽略
    }
  },
)

async function doLogout() {
  await logout().catch(() => undefined)
  if (auth.value) auth.value = { ...auth.value, authenticated: false }
}

const tab = computed(() =>
  tabs.some((t) => t.id === route.value[0]) ? route.value[0] : 'wall',
)
</script>

<template>
  <div v-if="!auth" class="boot"><span class="spin"></span></div>
  <LoginView v-else-if="!auth.authenticated" />
  <SetupWizard v-else-if="setup" @done="setup = false" />
  <template v-else>
    <header class="top">
      <a class="brand" href="#/wall">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="4" width="5" height="16" rx="1" />
          <rect x="9.5" y="4" width="5" height="16" rx="1" />
          <rect x="16" y="4" width="5" height="16" rx="1" transform="rotate(8 18.5 12)" />
        </svg>
        <span class="brand-name">Pinakes</span>
      </a>
      <nav>
        <a
          v-for="t in tabs"
          :key="t.id"
          :href="`#/${t.id}`"
          :aria-current="tab === t.id ? 'page' : undefined"
          :class="{ active: tab === t.id }"
        >
          {{ t.label }}
        </a>
      </nav>
      <span class="spacer"></span>
      <button
        type="button"
        class="btn ghost icon"
        :title="theme === 'dark' ? '切換為淺色' : '切換為深色'"
        :aria-label="theme === 'dark' ? '切換為淺色' : '切換為深色'"
        @click="toggleTheme"
      >
        {{ theme === 'dark' ? '☀' : '☾' }}
      </button>
      <button v-if="auth.enabled" type="button" class="btn ghost sm" @click="doLogout">登出</button>
    </header>

    <main class="page">
      <PosterWall v-if="tab === 'wall'" />
      <OrganizePanel v-else-if="tab === 'organize'" />
      <SettingsPage
        v-else
        :section="route[1]"
        @navigate="(s: string) => go('settings', s)"
      />
    </main>

    <footer class="credit">
      This product uses the TMDB API but is not endorsed or certified by TMDB.
    </footer>
  </template>

  <UiLayer />
</template>

<style scoped>
.boot {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: var(--muted);
}

.top {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.6rem 1.5rem;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text);
  font-weight: 700;
  font-size: 1.15rem;
  text-decoration: none;
  letter-spacing: 0.02em;
}

.brand svg {
  width: 1.4rem;
  height: 1.4rem;
  fill: var(--accent);
}

nav {
  display: flex;
  gap: 0.25rem;
}

nav a {
  padding: 0.4rem 0.85rem;
  white-space: nowrap;
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-weight: 500;
}

nav a:hover {
  color: var(--text);
  background: var(--surface-2);
}

nav a.active {
  color: var(--text);
  background: var(--surface-2);
  box-shadow: inset 0 -2px 0 var(--accent);
}

.page {
  padding: 1.5rem;
  max-width: 100rem;
  margin: 0 auto;
}

.credit {
  padding: 1rem 1.5rem 2rem;
  font-size: 0.78rem;
  color: var(--muted);
  text-align: center;
}

@media (max-width: 40rem) {
  .top {
    gap: 0.75rem;
    padding: 0.5rem 1rem;
  }

  .brand {
    font-size: 1rem;
  }

  nav a {
    padding: 0.35rem 0.6rem;
  }

  .page {
    padding: 1rem;
  }
}

@media (max-width: 26rem) {
  .brand-name {
    display: none;
  }
}
</style>
