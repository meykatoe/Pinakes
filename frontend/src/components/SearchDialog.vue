<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { searchTmdb, type Candidate, type Item } from '../api'
import { basename, posterThumb } from '../format'

const props = defineProps<{ item: Item }>()
const emit = defineEmits<{ close: []; pick: [c: Candidate] }>()

const query = ref(props.item.title || guess(props.item.source_path))
const year = ref<number | null>(props.item.year)
const mediaType = ref(props.item.media_type)
const results = ref<Candidate[]>(props.item.candidates)
const busy = ref(false)
const error = ref('')
const input = ref<HTMLInputElement | null>(null)

function guess(path: string): string {
  return basename(path)
    .replace(/\.[^.]+$/, '')
    .replace(/[._]+/g, ' ')
    .replace(/\b((19|20)\d{2}|\d{3,4}[pi]|4k|[xh] ?26[45]|hevc|avc|web(-?dl|rip)?|blu-?ray|bdrip|remux|hdtv|s\d{1,2}e\d{1,4}|s\d{1,2})\b.*$/i, '')
    .trim()
}

async function search() {
  if (!query.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    results.value = await searchTmdb(query.value, mediaType.value, year.value)
    if (!results.value.length) error.value = '找不到結果，試試原文片名或拿掉年份'
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  input.value?.select()
  if (mediaType.value !== props.item.media_type || !results.value.length) search()
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="dialog card" role="dialog" aria-modal="true" aria-label="搜尋 TMDB">
      <div class="card-head">
        <h3>指定作品</h3>
        <button type="button" class="btn ghost icon" aria-label="關閉" @click="emit('close')">✕</button>
      </div>
      <p class="hint file break">{{ basename(item.source_path) }}</p>
      <form class="search" @submit.prevent="search">
        <div class="seg" role="radiogroup" aria-label="類型">
          <button
            v-for="[v, label] in [['movie', '電影'], ['tv', '影集']]"
            :key="v"
            type="button"
            role="radio"
            :aria-checked="mediaType === v"
            :class="{ on: mediaType === v }"
            @click="mediaType = v; search()"
          >
            {{ label }}
          </button>
        </div>
        <input ref="input" v-model="query" class="input q" placeholder="片名" />
        <input
          v-model.number="year"
          class="input y"
          type="number"
          placeholder="年份"
          min="1900"
          max="2100"
        />
        <button type="submit" class="btn primary" :disabled="busy">
          <span v-if="busy" class="spin"></span>
          搜尋
        </button>
      </form>

      <p v-if="error" class="muted">{{ error }}</p>
      <ul class="results">
        <li v-for="c in results" :key="c.media_type + c.tmdb_id">
          <button type="button" class="pick" @click="emit('pick', { ...c, media_type: mediaType })">
            <img v-if="c.poster_path" :src="posterThumb(c.poster_path, 'w154')" alt="" loading="lazy" />
            <div v-else class="noimg">無海報</div>
            <div class="info">
              <strong>{{ c.title }}</strong>
              <span class="muted">
                {{ c.original_title && c.original_title !== c.title ? c.original_title + ' · ' : '' }}{{ c.year ?? '年份不明' }}
              </span>
              <p class="overview">{{ c.overview || '沒有簡介' }}</p>
            </div>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: grid;
  place-items: start center;
  overflow-y: auto;
  padding: 3rem 1rem;
  background: rgb(0 0 0 / 0.6);
}

.dialog {
  width: min(44rem, 100%);
  box-shadow: var(--shadow);
}

.card-head {
  margin-bottom: 0.25rem;
}

.file {
  margin-bottom: 1rem;
  font-family: ui-monospace, Menlo, monospace;
}

.search {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.q {
  flex: 1;
  min-width: 10rem;
  width: auto;
}

.y {
  width: 6rem;
}

.seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.seg button {
  all: unset;
  padding: 0 0.8rem;
  cursor: pointer;
  font-size: 0.9rem;
  display: grid;
  place-items: center;
}

.seg button.on {
  background: var(--accent);
  color: var(--accent-text);
  font-weight: 600;
}

.seg button:focus-visible {
  outline: 2px solid var(--accent);
}

.results {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0;
  display: grid;
  gap: 0.5rem;
}

.pick {
  all: unset;
  box-sizing: border-box;
  width: 100%;
  display: flex;
  gap: 0.85rem;
  padding: 0.6rem;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  border: 1px solid transparent;
  cursor: pointer;
}

.pick:hover,
.pick:focus-visible {
  border-color: var(--accent);
}

.pick img,
.noimg {
  width: 3.5rem;
  aspect-ratio: 2 / 3;
  object-fit: cover;
  border-radius: 4px;
  background: var(--surface-3);
  flex: none;
  display: grid;
  place-items: center;
  font-size: 0.7rem;
  color: var(--muted);
}

.info {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 0.15rem;
}

.overview {
  margin: 0.25rem 0 0;
  font-size: 0.82rem;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
