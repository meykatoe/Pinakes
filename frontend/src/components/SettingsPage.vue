<script setup lang="ts">
import { computed } from 'vue'
import LibraryForm from './LibraryForm.vue'
import MatchPreview from './MatchPreview.vue'
import PlayersForm from './PlayersForm.vue'
import RulesForm from './RulesForm.vue'
import SecurityForm from './SecurityForm.vue'
import SettingsForm from './SettingsForm.vue'

const props = defineProps<{ section?: string }>()
defineEmits<{ navigate: [section: string] }>()

const sections = [
  { id: 'connect', label: 'API 連線', desc: 'TMDB 與 AI 服務' },
  { id: 'library', label: '媒體庫', desc: '目錄、分類與整理方式' },
  { id: 'naming', label: '辨識與命名', desc: '命名樣板、正則與比對測試' },
  { id: 'playback', label: '播放', desc: '內建播放與外部播放器' },
  { id: 'notify', label: '通知', desc: 'Email、Telegram、Discord' },
  { id: 'security', label: '安全性', desc: '登入密碼' },
]

const active = computed(() =>
  sections.some((s) => s.id === props.section) ? props.section! : 'connect',
)
</script>

<template>
  <div class="settings-page">
    <aside>
      <nav aria-label="設定分類">
        <button
          v-for="s in sections"
          :key="s.id"
          type="button"
          :class="{ active: active === s.id }"
          :aria-current="active === s.id ? 'page' : undefined"
          @click="$emit('navigate', s.id)"
        >
          <strong>{{ s.label }}</strong>
          <small>{{ s.desc }}</small>
        </button>
      </nav>
    </aside>

    <div class="content">
      <template v-if="active === 'connect'">
        <SettingsForm section="connect" />
      </template>
      <template v-else-if="active === 'library'">
        <LibraryForm />
        <SettingsForm section="organize" />
      </template>
      <template v-else-if="active === 'naming'">
        <RulesForm />
        <MatchPreview />
      </template>
      <template v-else-if="active === 'playback'">
        <SettingsForm section="playback" />
        <PlayersForm />
      </template>
      <template v-else-if="active === 'notify'">
        <SettingsForm section="notify" />
      </template>
      <template v-else>
        <SecurityForm />
      </template>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  display: grid;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: 1.5rem;
  align-items: start;
}

aside {
  position: sticky;
  top: 4.5rem;
}

aside nav {
  display: grid;
  gap: 0.25rem;
}

aside button {
  all: unset;
  display: grid;
  gap: 0.1rem;
  padding: 0.6rem 0.85rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  border-left: 3px solid transparent;
}

aside button:hover {
  background: var(--surface-2);
}

aside button:focus-visible {
  outline: 2px solid var(--accent);
}

aside button.active {
  background: var(--surface);
  border-left-color: var(--accent);
}

aside small {
  color: var(--muted);
  font-size: 0.78rem;
}

.content {
  min-width: 0;
  max-width: 60rem;
}

@media (max-width: 52rem) {
  .settings-page {
    grid-template-columns: 1fr;
  }

  aside {
    position: static;
  }

  aside nav {
    display: flex;
    overflow-x: auto;
    gap: 0.25rem;
  }

  aside button {
    border-left: 0;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
  }

  aside button.active {
    border-bottom-color: var(--accent);
  }

  aside small {
    display: none;
  }
}
</style>
