<script setup lang="ts">
import { ref, watch } from 'vue'
import LibraryForm from './components/LibraryForm.vue'
import MatchPreview from './components/MatchPreview.vue'
import OrganizePanel from './components/OrganizePanel.vue'
import PosterWall from './components/PosterWall.vue'
import RulesForm from './components/RulesForm.vue'
import SettingsForm from './components/SettingsForm.vue'

const tabs = [
  { id: 'wall', label: '海報牆' },
  { id: 'organize', label: '整理' },
  { id: 'settings', label: '設定' },
]

function loadTab(): string {
  try {
    const saved = localStorage.getItem('pinakes-tab')
    if (saved && tabs.some((t) => t.id === saved)) return saved
  } catch {
    // 無法讀取
  }
  return 'wall'
}

const tab = ref(loadTab())

watch(tab, (value) => {
  try {
    localStorage.setItem('pinakes-tab', value)
  } catch {
    // 無法寫入
  }
})
</script>

<template>
  <header class="top">
    <h1>Pinakes</h1>
    <nav>
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        :aria-current="tab === t.id ? 'page' : undefined"
        :class="{ active: tab === t.id }"
        @click="tab = t.id"
      >
        {{ t.label }}
      </button>
    </nav>
  </header>

  <main class="page">
    <PosterWall v-if="tab === 'wall'" />
    <OrganizePanel v-else-if="tab === 'organize'" />
    <template v-else>
      <SettingsForm />
      <LibraryForm />
      <RulesForm />
      <MatchPreview />
    </template>
  </main>

  <footer class="credit">
    This product uses the TMDB API but is not endorsed or certified by TMDB.
  </footer>
</template>

<style scoped>
.top {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1rem 2rem;
  border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent);
}

.top h1 {
  margin: 0;
  font-size: 1.5rem;
}

nav {
  display: flex;
  gap: 0.5rem;
}

nav .active {
  font-weight: 700;
  text-decoration: underline;
}

.page {
  padding: 2rem;
}

.credit {
  padding: 1rem 2rem 2rem;
  font-size: 0.8rem;
  opacity: 0.6;
}
</style>
