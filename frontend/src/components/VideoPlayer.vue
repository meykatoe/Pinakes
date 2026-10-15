<script setup lang="ts">
import type Hls from 'hls.js'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { keepAliveHls, startHls, stopHls, type HlsInfo } from '../api'
import { formatTime, getProgress, saveProgress } from '../playback'

const props = defineProps<{ itemId: number; title: string }>()
const emit = defineEmits<{ close: [] }>()

const video = ref<HTMLVideoElement | null>(null)
const info = ref<HlsInfo | null>(null)
const loading = ref(true)
const error = ref('')
const offset = ref(0)
const now = ref(0)
const resumed = ref(0)
const modeText: Record<string, string> = {
  direct: '直接播放',
  remux: '轉封裝',
  transcode: '即時轉碼',
}
let hls: Hls | null = null
let sessionId: string | null = null
let keepTimer: number | undefined
let saveTimer: number | undefined
let generation = 0

const duration = computed(() => info.value?.duration ?? 0)
const custom = computed(() => !!info.value && info.value.mode !== 'direct' && duration.value > 0)

function absolute(): number {
  return offset.value + (video.value?.currentTime ?? 0)
}

function teardown() {
  window.clearInterval(keepTimer)
  hls?.destroy()
  hls = null
  if (sessionId) stopHls(sessionId).catch(() => undefined)
  sessionId = null
}

async function begin(start: number) {
  const gen = ++generation
  teardown()
  loading.value = true
  error.value = ''
  const el = video.value
  if (!el) return
  try {
    const data = await startHls(props.itemId, start)
    if (gen !== generation) {
      if (data.session_id) stopHls(data.session_id).catch(() => undefined)
      return
    }
    info.value = data
    if (data.direct_url) {
      offset.value = 0
      el.src = data.direct_url
      if (start > 0) {
        el.addEventListener('loadedmetadata', () => (el.currentTime = start), { once: true })
      }
      return
    }
    offset.value = start
    sessionId = data.session_id
    const url = data.playlist_url as string
    const { default: HlsLib } = await import('hls.js')
    if (gen !== generation) return
    if (HlsLib.isSupported()) {
      hls = new HlsLib({ maxBufferLength: 60 })
      hls.on(HlsLib.Events.ERROR, (_, d) => {
        if (d.fatal) {
          error.value = `播放失敗：${d.details}`
          loading.value = false
        }
      })
      hls.loadSource(url)
      hls.attachMedia(el)
    } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
      el.src = url
    } else {
      error.value = '此瀏覽器不支援 HLS 播放，請改用外部播放器'
      loading.value = false
      return
    }
    keepTimer = window.setInterval(() => {
      if (sessionId) keepAliveHls(sessionId).catch(() => undefined)
    }, 30000)
  } catch (err) {
    if (gen !== generation) return
    error.value = (err as Error).message
    loading.value = false
  }
}

function seekTo(target: number) {
  const el = video.value
  if (!el) return
  target = Math.max(0, Math.min(target, duration.value || target))
  if (!custom.value) {
    el.currentTime = target
    return
  }
  const rel = target - offset.value
  const end = el.seekable.length ? el.seekable.end(el.seekable.length - 1) : 0
  if (rel >= 0 && rel <= end - 1) el.currentTime = rel
  else begin(target)
}

function onSlider(e: Event) {
  seekTo(Number((e.target as HTMLInputElement).value))
}

function onTime() {
  now.value = absolute()
}

function persist() {
  if (!info.value) return
  const dur = duration.value || video.value?.duration || 0
  saveProgress(props.itemId, absolute(), Number.isFinite(dur) ? dur : 0)
}

function restart() {
  resumed.value = 0
  if (custom.value) begin(0)
  else seekTo(0)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    emit('close')
    return
  }
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'SELECT') return
  if (e.key === 'ArrowRight' && custom.value) {
    e.preventDefault()
    seekTo(absolute() + 10)
  } else if (e.key === 'ArrowLeft' && custom.value) {
    e.preventDefault()
    seekTo(absolute() - 10)
  }
}

function cleanup() {
  persist()
  window.clearInterval(saveTimer)
  generation++
  teardown()
}

onMounted(() => {
  window.addEventListener('keydown', onKey, true)
  window.addEventListener('pagehide', cleanup)
  saveTimer = window.setInterval(persist, 5000)
  const saved = getProgress(props.itemId)
  resumed.value = saved?.pos ?? 0
  begin(resumed.value)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey, true)
  window.removeEventListener('pagehide', cleanup)
  cleanup()
})
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="player" role="dialog" aria-modal="true" :aria-label="title">
      <div class="head">
        <strong>{{ title }}</strong>
        <span v-if="info" class="mode">{{ modeText[info.mode] ?? info.mode }}</span>
        <button type="button" class="x" aria-label="關閉" @click="emit('close')">✕</button>
      </div>
      <div class="stage">
        <video
          ref="video"
          controls
          autoplay
          playsinline
          @playing="loading = false"
          @canplay="loading = false"
          @waiting="loading = true"
          @timeupdate="onTime"
          @pause="persist"
        ></video>
        <div v-if="loading && !error" class="veil">
          <span class="spin big"></span>
          <span>{{ info && info.mode === 'transcode' ? '轉碼準備中…' : '載入中…' }}</span>
        </div>
        <div v-if="error" class="veil err">
          <p>{{ error }}</p>
          <button type="button" class="btn" @click="begin(absolute())">重試</button>
        </div>
      </div>
      <div v-if="custom" class="seek">
        <span>{{ formatTime(now) }}</span>
        <input
          type="range"
          min="0"
          :max="duration"
          step="1"
          :value="now"
          aria-label="播放進度"
          @change="onSlider"
        />
        <span>{{ formatTime(duration) }}</span>
      </div>
      <div class="foot">
        <span v-if="custom" class="hint">此格式需轉換，請用上方進度條跳轉，← → 可快轉 10 秒</span>
        <span class="spacer"></span>
        <button v-if="resumed > 0" type="button" class="btn sm ghost light" @click="restart">
          從頭播放
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 0.92);
  padding: 1rem;
}

.player {
  width: min(78rem, 100%);
  color: #fff;
}

.head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-bottom: 0.6rem;
}

.head strong {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.mode {
  font-size: 0.78rem;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: rgb(255 255 255 / 0.15);
}

.x {
  all: unset;
  cursor: pointer;
  width: 2rem;
  height: 2rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
}

.x:hover,
.x:focus-visible {
  background: rgb(255 255 255 / 0.15);
}

.stage {
  position: relative;
}

video {
  display: block;
  width: 100%;
  max-height: 78vh;
  background: #000;
  border-radius: 6px;
}

.veil {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 0.75rem;
  pointer-events: none;
  background: rgb(0 0 0 / 0.35);
  font-size: 0.9rem;
}

.veil.err {
  pointer-events: auto;
  background: rgb(0 0 0 / 0.75);
  padding: 1rem;
  text-align: center;
}

.spin.big {
  width: 2.5rem;
  height: 2.5rem;
  border-width: 3px;
}

.seek {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.6rem;
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

.seek input {
  flex: 1;
  accent-color: var(--accent);
}

.foot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.4rem;
  min-height: 2rem;
}

.foot .hint {
  color: rgb(255 255 255 / 0.6);
}

.light {
  color: #fff;
}

.light:hover {
  background: rgb(255 255 255 / 0.12) !important;
}
</style>
