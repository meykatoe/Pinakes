<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  getMedia,
  getPlayInfo,
  getTranscodeStatus,
  listPlayers,
  refreshMedia,
  removeMedia,
  type MediaDetail,
  type MediaEntry,
  type Player,
} from '../api'
import { basename, pad2 } from '../format'
import { copyText, formatTime, getProgress } from '../playback'
import { confirm } from '../ui/confirm'
import { toast, toastError } from '../ui/toast'
import VideoPlayer from './VideoPlayer.vue'

const props = defineProps<{ entry: MediaEntry }>()
const emit = defineEmits<{ close: []; changed: [] }>()

type FileRow = MediaDetail['files'][number]

const detail = ref<MediaDetail | null>(null)
const players = ref<Player[]>([])
const playerId = ref<number | null>(null)
const canTranscode = ref(false)
const playing = ref<FileRow | null>(null)
const season = ref<number>(0)
const refreshing = ref(false)
const progressTick = ref(0)
const PLAYER_KEY = 'pinakes-player'

async function load() {
  try {
    detail.value = await getMedia(props.entry.media_type, props.entry.tmdb_id)
    if (!seasons.value.some(([s]) => s === season.value)) {
      season.value = resumeTarget.value?.season ?? seasons.value[0]?.[0] ?? 0
    }
  } catch (err) {
    toastError(err)
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

async function external(f: FileRow) {
  try {
    const info = await getPlayInfo(f.item_id)
    const link = info.links.find((l) => l.player_id === playerId.value)
    if (!link) {
      toast('請先選擇外部播放器', 'error')
      return
    }
    if (link.kind === 'm3u') {
      window.location.href = link.href
      return
    }
    toast(`已送出到 ${link.name}，若沒有反應請確認已安裝並註冊協定`, 'info')
    window.location.href = link.href
  } catch (err) {
    toastError(err)
  }
}

async function copyLink(f: FileRow) {
  try {
    const info = await getPlayInfo(f.item_id)
    await copyText(info.stream_url)
    toast('已複製串流網址，可貼到任何播放器')
  } catch (err) {
    toastError(err)
  }
}

function play(f: FileRow) {
  if (canTranscode.value) playing.value = f
  else external(f)
}

onMounted(() => {
  document.body.style.overflow = 'hidden'
  load()
  getTranscodeStatus()
    .then((r) => (canTranscode.value = r.available))
    .catch(() => undefined)
  loadPlayers().catch(toastError)
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKey)
})

const seasons = computed(() => {
  const groups = new Map<number, FileRow[]>()
  for (const f of detail.value?.files ?? []) {
    const key = f.season ?? 0
    groups.set(key, [...(groups.get(key) ?? []), f])
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0])
})

const episodes = computed(() => seasons.value.find(([s]) => s === season.value)?.[1] ?? [])

const isTv = computed(() => props.entry.media_type === 'tv')

function progressOf(f: FileRow) {
  void progressTick.value
  const p = getProgress(f.item_id)
  return p && p.dur ? Math.min(100, (p.pos / p.dur) * 100) : 0
}

const resumeTarget = computed(() => {
  void progressTick.value
  const files = detail.value?.files ?? []
  let best: FileRow | null = null
  let at = 0
  for (const f of files) {
    const p = getProgress(f.item_id)
    if (p && p.at > at) {
      best = f
      at = p.at
    }
  }
  return best
})

const mainFile = computed(() => resumeTarget.value ?? detail.value?.files[0] ?? null)

const mainLabel = computed(() => {
  const f = mainFile.value
  if (!f) return '播放'
  const p = getProgress(f.item_id)
  const ep = isTv.value && f.episode !== null ? ` S${pad2(f.season)}E${pad2(f.episode)}` : ''
  return p ? `繼續播放${ep}（${formatTime(p.pos)}）` : `播放${ep}`
})

function closePlayer() {
  playing.value = null
  progressTick.value++
}

async function refresh() {
  refreshing.value = true
  try {
    await refreshMedia(props.entry.media_type, props.entry.tmdb_id)
    await load()
    emit('changed')
    toast('已重新抓取資料')
  } catch (err) {
    toastError(err)
  } finally {
    refreshing.value = false
  }
}

async function remove() {
  const ok = await confirm(
    `將「${props.entry.title}」移出媒體庫？\n整理出的檔案會被移除（移動模式則搬回原處），可在整理頁找到紀錄。`,
    '移出',
    true,
  )
  if (!ok) return
  try {
    const r = await removeMedia(props.entry.media_type, props.entry.tmdb_id)
    toast(r.failed ? `已移出 ${r.removed} 個，${r.failed} 個失敗` : '已移出媒體庫', r.failed ? 'error' : 'ok')
    emit('changed')
    emit('close')
  } catch (err) {
    toastError(err)
  }
}

const tmdbUrl = computed(
  () => `https://www.themoviedb.org/${props.entry.media_type}/${props.entry.tmdb_id}`,
)
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <article class="dialog" role="dialog" aria-modal="true" :aria-label="entry.title">
      <div
        class="hero"
        :style="entry.backdrop_url ? { backgroundImage: `url(${entry.backdrop_url})` } : {}"
      >
        <button class="close" type="button" aria-label="關閉" @click="emit('close')">✕</button>
      </div>

      <div class="body">
        <img v-if="entry.poster_url" :src="entry.poster_url" :alt="entry.title" class="poster" />
        <div class="info">
          <h2>{{ entry.title }}</h2>
          <p v-if="entry.original_title && entry.original_title !== entry.title" class="sub">
            {{ entry.original_title }}
          </p>
          <p class="facts">
            <span v-if="entry.rating" class="star">★ {{ entry.rating.toFixed(1) }}</span>
            <span v-if="entry.year">{{ entry.year }}</span>
            <span v-if="detail?.runtime">{{ detail.runtime }} 分鐘</span>
            <span v-if="detail?.seasons">{{ detail.seasons }} 季</span>
            <span v-for="g in entry.genres" :key="g" class="badge">{{ g }}</span>
          </p>

          <div class="cta">
            <button
              v-if="mainFile"
              type="button"
              class="btn primary big"
              :disabled="!canTranscode && playerId === null"
              @click="play(mainFile)"
            >
              ▶ {{ mainLabel }}
            </button>
            <a
              v-if="detail?.trailer_key"
              class="btn"
              :href="`https://www.youtube.com/watch?v=${detail.trailer_key}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              預告片
            </a>
            <a class="btn ghost" :href="tmdbUrl" target="_blank" rel="noopener noreferrer">TMDB</a>
          </div>

          <p v-if="detail?.tagline" class="tagline">「{{ detail.tagline }}」</p>
          <p class="overview">{{ entry.overview || '尚無簡介' }}</p>

          <div v-if="detail?.credits.length" class="cast">
            <span v-for="c in detail.credits" :key="c.name + c.character">
              <strong>{{ c.name }}</strong>
              <small v-if="c.character" class="muted">{{ c.character }}</small>
            </span>
          </div>
        </div>
      </div>

      <section class="files">
        <div class="files-head">
          <h3>{{ isTv ? '劇集' : '檔案' }}</h3>
          <div v-if="isTv && seasons.length > 1" class="tabs" role="tablist">
            <button
              v-for="[s] in seasons"
              :key="s"
              type="button"
              role="tab"
              :aria-selected="season === s"
              :class="{ on: season === s }"
              @click="season = s"
            >
              {{ s ? `第 ${s} 季` : '其他' }}
            </button>
          </div>
          <span class="spacer"></span>
          <label v-if="players.length" class="picker">
            <span class="muted">外部播放器</span>
            <select v-model="playerId" class="input" @change="rememberPlayer">
              <option v-for="p in players" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </label>
        </div>

        <p v-if="!canTranscode" class="hint nofm">
          找不到 ffmpeg，內建播放器無法使用，將改用外部播放器。
        </p>

        <ul>
          <li v-for="f in (isTv ? episodes : detail?.files ?? [])" :key="f.item_id">
            <button type="button" class="play" :disabled="!canTranscode" :title="canTranscode ? '內建播放' : '需要 ffmpeg'" @click="playing = f">
              ▶
            </button>
            <div class="name">
              <strong v-if="isTv && f.episode !== null">第 {{ f.episode }} 集</strong>
              <span class="muted break" :title="f.target_path">{{ basename(f.target_path) }}</span>
              <div v-if="progressOf(f)" class="prog"><div :style="{ width: progressOf(f) + '%' }"></div></div>
            </div>
            <button type="button" class="btn sm" :disabled="playerId === null" @click="external(f)">
              外部播放
            </button>
            <button type="button" class="btn sm ghost" title="複製串流網址" @click="copyLink(f)">
              複製連結
            </button>
          </li>
        </ul>

        <div class="foot">
          <button type="button" class="btn ghost sm danger" @click="remove">移出媒體庫</button>
          <span class="spacer"></span>
          <button type="button" class="btn ghost sm" :disabled="refreshing" @click="refresh">
            <span v-if="refreshing" class="spin"></span>
            重新抓取資料
          </button>
        </div>
      </section>
    </article>
    <VideoPlayer
      v-if="playing !== null"
      :item-id="playing.item_id"
      :title="isTv && playing.episode !== null ? `${entry.title} · S${pad2(playing.season)}E${pad2(playing.episode)}` : entry.title"
      @close="closePlayer"
    />
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 0.7);
  display: grid;
  place-items: start center;
  overflow-y: auto;
  padding: 2rem 1rem;
  z-index: 10;
}

.dialog {
  width: min(58rem, 100%);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}

.hero {
  position: relative;
  height: 18rem;
  background: var(--surface-3) center 25% / cover;
}

.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, var(--surface) 0%, transparent 60%);
}

.close {
  all: unset;
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  z-index: 1;
  width: 2.25rem;
  height: 2.25rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgb(0 0 0 / 0.55);
  color: #fff;
  cursor: pointer;
}

.close:focus-visible {
  outline: 2px solid var(--accent);
}

.body {
  position: relative;
  display: flex;
  gap: 1.75rem;
  padding: 0 1.75rem 1rem;
  margin-top: -7rem;
}

.poster {
  width: 11rem;
  align-self: flex-start;
  border-radius: 0.5rem;
  box-shadow: 0 8px 24px rgb(0 0 0 / 0.5);
  flex: none;
}

.info {
  min-width: 0;
  flex: 1;
  padding-top: 3.5rem;
}

h2 {
  margin: 0;
  font-size: 1.8rem;
}

.sub {
  color: var(--muted);
  margin: 0.15rem 0 0;
}

.facts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.85rem;
  margin: 0.75rem 0;
  font-size: 0.92rem;
}

.star {
  color: #f5b301;
  font-weight: 700;
}

.cta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 1rem 0;
}

.big {
  min-height: 2.6rem;
  padding: 0 1.25rem;
  font-size: 1rem;
}

.tagline {
  font-style: italic;
  color: var(--muted);
  margin: 0 0 0.4rem;
}

.overview {
  margin: 0 0 1rem;
  line-height: 1.7;
}

.cast {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.25rem;
  font-size: 0.86rem;
}

.cast span {
  display: grid;
}

.files {
  padding: 1rem 1.75rem 1.5rem;
  border-top: 1px solid var(--border);
}

.files-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.files-head h3 {
  margin: 0;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.tabs button {
  all: unset;
  cursor: pointer;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  font-size: 0.86rem;
  color: var(--muted);
}

.tabs button.on {
  background: var(--surface-3);
  color: var(--text);
  font-weight: 600;
}

.tabs button:focus-visible {
  outline: 2px solid var(--accent);
}

.picker {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.picker .input {
  width: auto;
  min-height: 1.9rem;
  padding: 0 0.5rem;
}

.nofm {
  margin: -0.25rem 0 0.75rem;
}

ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.35rem;
}

li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.6rem;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.play {
  all: unset;
  flex: none;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--accent);
  color: var(--accent-text);
  cursor: pointer;
  font-size: 0.85rem;
}

.play:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.play:focus-visible {
  outline: 2px solid var(--text);
}

.name {
  flex: 1;
  min-width: 0;
  display: grid;
  font-size: 0.88rem;
}

.name .muted {
  font-size: 0.8rem;
}

.prog {
  height: 3px;
  margin-top: 0.3rem;
  background: var(--surface-3);
  border-radius: 3px;
  overflow: hidden;
}

.prog div {
  height: 100%;
  background: var(--accent);
}

.foot {
  margin-top: 1rem;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 40rem) {
  .overlay {
    padding: 0;
  }

  .dialog {
    border-radius: 0;
    min-height: 100vh;
  }

  .hero {
    height: 12rem;
  }

  .body {
    flex-direction: column;
    gap: 0.75rem;
    padding: 0 1rem 1rem;
    margin-top: -5rem;
  }

  .poster {
    width: 7rem;
  }

  .info {
    padding-top: 0;
  }

  h2 {
    font-size: 1.4rem;
  }

  .files {
    padding: 1rem;
  }

  li {
    flex-wrap: wrap;
  }

  .name {
    flex-basis: calc(100% - 3rem);
  }
}
</style>
