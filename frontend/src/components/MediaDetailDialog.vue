<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import VideoPlayer from './VideoPlayer.vue'
import {
  getMedia,
  getTranscodeStatus,
  getPlayInfo,
  listPlayers,
  refreshMedia,
  type MediaDetail,
  type MediaEntry,
  type Player,
} from '../api'

const props = defineProps<{ entry: MediaEntry }>()
const emit = defineEmits<{ close: []; changed: [] }>()

const detail = ref<MediaDetail | null>(null)
const message = ref('')
const players = ref<Player[]>([])
const playerId = ref<number | null>(null)
const canTranscode = ref(false)
const playing = ref<number | null>(null)
const PLAYER_KEY = 'pinakes-player'

async function load() {
  try {
    detail.value = await getMedia(props.entry.media_type, props.entry.tmdb_id)
  } catch (err) {
    message.value = (err as Error).message
  }
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && playing.value === null) emit('close')
}

async function loadPlayers() {
  players.value = (await listPlayers()).filter((p) => p.enabled)
  let saved: number | null = null
  try {
    saved = Number(localStorage.getItem(PLAYER_KEY)) || null
  } catch {
    // 無法讀取
  }
  const found = players.value.find((p) => p.id === saved)
  playerId.value = found?.id ?? players.value[0]?.id ?? null
}

function rememberPlayer() {
  try {
    localStorage.setItem(PLAYER_KEY, String(playerId.value))
  } catch {
    // 無法寫入
  }
}

async function play(itemId: number) {
  try {
    const info = await getPlayInfo(itemId)
    const link = info.links.find((l) => l.player_id === playerId.value)
    if (!link) {
      message.value = '請先選擇播放器'
      return
    }
    message.value = `已送出到 ${link.name}，若沒有反應請確認已安裝並註冊協定`
    window.location.href = link.href
  } catch (err) {
    message.value = (err as Error).message
  }
}

onMounted(() => {
  load()
  getTranscodeStatus()
    .then((r) => (canTranscode.value = r.available))
    .catch(() => undefined)
  loadPlayers().catch((err) => (message.value = (err as Error).message))
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))

const seasons = computed(() => {
  const groups = new Map<number, MediaDetail['files']>()
  for (const f of detail.value?.files ?? []) {
    const key = f.season ?? 0
    groups.set(key, [...(groups.get(key) ?? []), f])
  }
  return [...groups.entries()]
})

async function refresh() {
  message.value = '更新中'
  try {
    await refreshMedia(props.entry.media_type, props.entry.tmdb_id)
    await load()
    emit('changed')
    message.value = '已更新'
  } catch (err) {
    message.value = (err as Error).message
  }
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <article class="dialog" role="dialog" aria-modal="true" :aria-label="entry.title">
      <div
        class="hero"
        :style="entry.backdrop_url ? { backgroundImage: `url(${entry.backdrop_url})` } : {}"
      >
        <button class="close" type="button" aria-label="關閉" @click="emit('close')">×</button>
      </div>

      <div class="body">
        <img v-if="entry.poster_url" :src="entry.poster_url" :alt="entry.title" class="poster" />
        <div class="info">
          <h2>{{ entry.title }}</h2>
          <p v-if="entry.original_title && entry.original_title !== entry.title" class="sub">
            {{ entry.original_title }}
          </p>
          <p class="facts">
            <span v-if="entry.year">{{ entry.year }}</span>
            <span v-if="entry.rating">★ {{ entry.rating }}</span>
            <span v-if="detail?.runtime">{{ detail.runtime }} 分鐘</span>
            <span v-if="detail?.seasons">{{ detail.seasons }} 季</span>
            <span v-if="entry.genres.length">{{ entry.genres.join(' / ') }}</span>
          </p>
          <p v-if="detail?.tagline" class="sub">{{ detail.tagline }}</p>
          <p>{{ entry.overview || '尚無簡介' }}</p>

          <template v-if="detail?.credits.length">
            <h3>演員</h3>
            <p class="cast">
              <span v-for="c in detail.credits" :key="c.name">
                {{ c.name }}<template v-if="c.character">（{{ c.character }}）</template>
              </span>
            </p>
          </template>

          <a
            v-if="detail?.trailer_key"
            :href="`https://www.youtube.com/watch?v=${detail.trailer_key}`"
            target="_blank"
            rel="noopener noreferrer"
          >
            觀看預告片
          </a>

          <h3>播放</h3>
          <label class="picker">
            播放器
            <select v-model="playerId" @change="rememberPlayer">
              <option v-for="p in players" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </label>
          <div v-for="[season, files] in seasons" :key="season">
            <h4 v-if="entry.media_type === 'tv'">第 {{ season }} 季</h4>
            <ul class="files">
              <li v-for="f in files" :key="f.item_id">
                <span v-if="f.episode !== null" class="ep">E{{ String(f.episode).padStart(2, '0') }}</span>
                {{ f.target_path }}
                <button type="button" :disabled="!canTranscode" @click="playing = f.item_id">
                  內建播放
                </button>
                <button type="button" :disabled="playerId === null" @click="play(f.item_id)">
                  外部播放器
                </button>
              </li>
            </ul>
          </div>

          <button type="button" @click="refresh">重新抓取資料</button>
          <span>{{ message }}</span>
        </div>
      </div>
    </article>
    <VideoPlayer
      v-if="playing !== null"
      :item-id="playing"
      :title="entry.title"
      @close="playing = null"
    />
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 0.6);
  display: grid;
  place-items: start center;
  overflow-y: auto;
  padding: 2rem 1rem;
  z-index: 10;
}

.dialog {
  width: min(52rem, 100%);
  background: Canvas;
  color: CanvasText;
  border-radius: 0.75rem;
  overflow: hidden;
}

.hero {
  position: relative;
  height: 14rem;
  background: color-mix(in srgb, currentColor 15%, transparent) center / cover;
}

.close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  font-size: 1.25rem;
  line-height: 1;
  width: 2rem;
  height: 2rem;
}

.body {
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem;
}

.poster {
  width: 9rem;
  align-self: flex-start;
  margin-top: -5rem;
  border-radius: 0.5rem;
  box-shadow: 0 4px 16px rgb(0 0 0 / 0.4);
}

.info {
  min-width: 0;
  flex: 1;
}

h2 {
  margin: 0;
}

.sub {
  opacity: 0.7;
  margin: 0.25rem 0;
}

.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  opacity: 0.85;
}

.cast {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 1rem;
  font-size: 0.9rem;
}

.picker {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.files {
  list-style: none;
  padding: 0;
  font-size: 0.85rem;
  word-break: break-all;
}

.ep {
  font-weight: 600;
  margin-right: 0.5rem;
}

@media (max-width: 40rem) {
  .body {
    flex-direction: column;
  }

  .poster {
    margin-top: -5rem;
  }
}
</style>
