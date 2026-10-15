<script setup lang="ts">
import Hls from 'hls.js'
import { onMounted, onUnmounted, ref } from 'vue'
import { keepAliveHls, startHls, stopHls } from '../api'

const props = defineProps<{ itemId: number; title: string }>()
const emit = defineEmits<{ close: [] }>()

const video = ref<HTMLVideoElement | null>(null)
const status = ref('準備中')
const error = ref('')
const modeText: Record<string, string> = {
  direct: '直接播放',
  remux: '轉封裝（快速）',
  transcode: '轉碼中',
}
let hls: Hls | null = null
let sessionId: string | null = null
let timer: number | undefined

async function begin() {
  try {
    const info = await startHls(props.itemId)
    status.value = modeText[info.mode] ?? info.mode
    const el = video.value
    if (!el) return
    if (info.direct_url) {
      el.src = info.direct_url
      return
    }
    sessionId = info.session_id
    const url = info.playlist_url as string
    if (Hls.isSupported()) {
      hls = new Hls()
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) error.value = `播放失敗：${data.details}`
      })
      hls.loadSource(url)
      hls.attachMedia(el)
    } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
      el.src = url
    } else {
      error.value = '此瀏覽器不支援 HLS 播放'
      return
    }
    timer = window.setInterval(() => {
      if (sessionId) keepAliveHls(sessionId).catch(() => undefined)
    }, 30000)
  } catch (err) {
    error.value = (err as Error).message
  }
}

function cleanup() {
  window.clearInterval(timer)
  hls?.destroy()
  hls = null
  if (sessionId) stopHls(sessionId).catch(() => undefined)
  sessionId = null
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('pagehide', cleanup)
  begin()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('pagehide', cleanup)
  cleanup()
})
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="player" role="dialog" aria-modal="true" :aria-label="title">
      <div class="head">
        <strong>{{ title }}</strong>
        <span class="status">{{ error || status }}</span>
        <button type="button" aria-label="關閉" @click="emit('close')">×</button>
      </div>
      <video ref="video" controls autoplay playsinline></video>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 0.85);
  padding: 1rem;
}

.player {
  width: min(70rem, 100%);
  color: #fff;
}

.head {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-bottom: 0.5rem;
}

.head strong {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.status {
  opacity: 0.8;
  font-size: 0.85rem;
}

video {
  width: 100%;
  max-height: 80vh;
  background: #000;
}
</style>
