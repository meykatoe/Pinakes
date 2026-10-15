<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  changePassword,
  getPaths,
  getSettings,
  savePaths,
  saveSettings,
  scan,
  testConnection,
} from '../api'
import { auth } from '../auth'
import { toastError } from '../ui/toast'
import DirPicker from './DirPicker.vue'

const emit = defineEmits<{ done: [] }>()

const step = ref(0)
const steps = ['TMDB 金鑰', '媒體庫目錄', '自動整理', '登入密碼']
const busy = ref(false)
const error = ref('')

const tmdb = reactive({ key: '', saved: '', language: 'zh-TW', ok: false })
const paths = reactive({ inbox: '', library: '', sameDevice: null as boolean | null })
const opts = reactive({ mode: 'hardlink', watch: true, auto: true })
const pw = reactive({ next: '', again: '' })

onMounted(async () => {
  try {
    const [s, p] = await Promise.all([getSettings(), getPaths()])
    tmdb.saved = s.tmdb_api_key
    tmdb.language = s.tmdb_language
    tmdb.ok = !!s.tmdb_api_key
    paths.inbox = p.inbox_path
    paths.library = p.library_path
    paths.sameDevice = p.same_device
    opts.mode = s.organize_mode
    opts.watch = s.watch_enabled || !p.inbox_path
    opts.auto = s.auto_execute
  } catch (err) {
    toastError(err)
  }
})

async function guard(fn: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try {
    await fn()
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

const saveTmdb = () =>
  guard(async () => {
    if (tmdb.key) {
      const s = await saveSettings({ tmdb_api_key: tmdb.key.trim(), tmdb_language: tmdb.language })
      tmdb.saved = s.tmdb_api_key
      tmdb.key = ''
    }
    const r = await testConnection('tmdb')
    if (!r.ok) throw new Error(`TMDB 連線失敗：${r.message}`)
    tmdb.ok = true
    step.value = 1
  })

const savePathsStep = () =>
  guard(async () => {
    const p = await savePaths({ inbox_path: paths.inbox, library_path: paths.library })
    paths.sameDevice = p.same_device
    if (p.same_device === false && opts.mode === 'hardlink') opts.mode = 'move'
    step.value = 2
  })

const saveOpts = () =>
  guard(async () => {
    await saveSettings({
      organize_mode: opts.mode,
      watch_enabled: opts.watch,
      auto_execute: opts.auto,
    })
    step.value = 3
  })

const pwValid = computed(() => pw.next.length >= 6 && pw.next === pw.again)

async function finish(setPassword: boolean) {
  await guard(async () => {
    if (setPassword) auth.value = await changePassword('', pw.next)
    try {
      localStorage.setItem('pinakes-setup-done', '1')
    } catch {
      // 無法寫入
    }
    scan().catch(() => undefined)
    window.location.hash = '/organize'
    emit('done')
  })
}

function later() {
  try {
    localStorage.setItem('pinakes-setup-done', '1')
  } catch {
    // 無法寫入
  }
  emit('done')
}
</script>

<template>
  <div class="wizard">
    <div class="panel card">
      <div class="brand">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="4" width="5" height="16" rx="1" />
          <rect x="9.5" y="4" width="5" height="16" rx="1" />
          <rect x="16" y="4" width="5" height="16" rx="1" transform="rotate(8 18.5 12)" />
        </svg>
        <div>
          <h1>歡迎使用 Pinakes</h1>
          <p class="muted">幾個步驟完成設定，之後放進下載目錄的影片就會自動整理成海報牆。</p>
        </div>
      </div>

      <ol class="steps">
        <li v-for="(s, i) in steps" :key="s" :class="{ on: i === step, done: i < step }">
          <span class="num">{{ i < step ? '✓' : i + 1 }}</span>
          {{ s }}
        </li>
      </ol>

      <form v-if="step === 0" class="body" @submit.prevent="saveTmdb">
        <p>
          Pinakes 用 TMDB 辨識影片並下載海報。請到
          <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noopener noreferrer">TMDB 帳號設定</a>
          免費申請 API 金鑰（v3 Key 或 v4 讀取權杖皆可）。
        </p>
        <label class="field">
          <span>API 金鑰</span>
          <input
            v-model="tmdb.key"
            class="input"
            type="password"
            autocomplete="off"
            :placeholder="tmdb.saved ? `已設定 ${tmdb.saved}` : '貼上金鑰'"
          />
        </label>
        <label class="field">
          <span>資料語言</span>
          <select v-model="tmdb.language" class="input">
            <option value="zh-TW">繁體中文（zh-TW）</option>
            <option value="zh-CN">簡體中文（zh-CN）</option>
            <option value="zh-HK">香港中文（zh-HK）</option>
            <option value="en-US">English（en-US）</option>
            <option value="ja-JP">日本語（ja-JP）</option>
          </select>
        </label>
        <p v-if="error" class="notice danger">{{ error }}</p>
        <div class="nav">
          <button type="button" class="btn ghost" @click="later">稍後再設定</button>
          <span class="spacer"></span>
          <button type="submit" class="btn primary" :disabled="busy || (!tmdb.key && !tmdb.saved)">
            <span v-if="busy" class="spin"></span>
            測試並繼續
          </button>
        </div>
      </form>

      <form v-else-if="step === 1" class="body" @submit.prevent="savePathsStep">
        <p>
          選擇兩個目錄。Pinakes 不會修改待整理目錄裡的原檔（預設使用硬連結）。
        </p>
        <div class="field">
          <span>待整理目錄（下載資料夾）</span>
          <DirPicker v-model="paths.inbox" placeholder="/downloads" />
        </div>
        <div class="field">
          <span>已整理目錄（媒體庫）</span>
          <DirPicker v-model="paths.library" placeholder="/media" />
          <p class="hint">會自動建立「電影」「影集」子目錄，可在設定中新增分類</p>
        </div>
        <p v-if="error" class="notice danger">{{ error }}</p>
        <div class="nav">
          <button type="button" class="btn ghost" @click="step = 0">上一步</button>
          <span class="spacer"></span>
          <button type="submit" class="btn primary" :disabled="busy || !paths.inbox || !paths.library">
            繼續
          </button>
        </div>
      </form>

      <form v-else-if="step === 2" class="body" @submit.prevent="saveOpts">
        <p v-if="paths.sameDevice === false" class="notice">
          兩個目錄不在同一磁碟，無法使用硬連結，已改為移動模式。
        </p>
        <label class="field">
          <span>整理方式</span>
          <select v-model="opts.mode" class="input">
            <option value="hardlink" :disabled="paths.sameDevice === false">硬連結（推薦，不佔空間，原檔可繼續做種）</option>
            <option value="move">移動</option>
            <option value="copy">複製</option>
            <option value="symlink">軟連結</option>
          </select>
        </label>
        <label class="check">
          <input v-model="opts.watch" type="checkbox" />
          <span>
            自動監控下載目錄
            <p class="hint">新檔案下載完成後自動辨識</p>
          </span>
        </label>
        <label class="check">
          <input v-model="opts.auto" type="checkbox" />
          <span>
            辨識確定後直接整理
            <p class="hint">不確定的項目一律會留給你確認</p>
          </span>
        </label>
        <p v-if="error" class="notice danger">{{ error }}</p>
        <div class="nav">
          <button type="button" class="btn ghost" @click="step = 1">上一步</button>
          <span class="spacer"></span>
          <button type="submit" class="btn primary" :disabled="busy">繼續</button>
        </div>
      </form>

      <form v-else class="body" @submit.prevent="finish(true)">
        <template v-if="auth?.enabled">
          <p>已設定登入密碼。</p>
        </template>
        <template v-else>
          <p>
            若 Pinakes 可從其他裝置連到，建議設定登入密碼。在本機自用可略過，之後也能在設定頁設定。
          </p>
          <input type="text" autocomplete="username" value="pinakes" hidden />
          <label class="field">
            <span>密碼</span>
            <input
              v-model="pw.next"
              class="input"
              type="password"
              autocomplete="new-password"
              placeholder="至少 6 個字元"
            />
          </label>
          <label class="field">
            <span>再次輸入</span>
            <input v-model="pw.again" class="input" type="password" autocomplete="new-password" />
          </label>
        </template>
        <p v-if="error" class="notice danger">{{ error }}</p>
        <div class="nav">
          <button type="button" class="btn ghost" @click="step = 2">上一步</button>
          <span class="spacer"></span>
          <button v-if="!auth?.enabled" type="button" class="btn" :disabled="busy" @click="finish(false)">
            不設密碼，完成
          </button>
          <button
            v-if="!auth?.enabled"
            type="submit"
            class="btn primary"
            :disabled="busy || !pwValid"
          >
            設定密碼並完成
          </button>
          <button v-else type="button" class="btn primary" :disabled="busy" @click="finish(false)">
            完成並開始掃描
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.wizard {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem 1rem;
  background:
    radial-gradient(circle at 20% 10%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 40%),
    var(--bg);
}

.panel {
  width: min(38rem, 100%);
  padding: 2rem;
  box-shadow: var(--shadow);
}

.brand {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.brand svg {
  width: 2.6rem;
  height: 2.6rem;
  fill: var(--accent);
  flex: none;
}

.brand h1 {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
}

.brand p {
  margin: 0;
  font-size: 0.92rem;
}

.steps {
  list-style: none;
  padding: 0;
  margin: 1.75rem 0 1.5rem;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--muted);
}

.steps li {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-top: 0.5rem;
  border-top: 3px solid var(--surface-3);
}

.steps li.on {
  color: var(--text);
  border-top-color: var(--accent);
  font-weight: 600;
}

.steps li.done {
  border-top-color: color-mix(in srgb, var(--accent) 50%, transparent);
}

.num {
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--surface-3);
  font-size: 0.75rem;
}

.on .num {
  background: var(--accent);
  color: var(--accent-text);
}

.body {
  display: grid;
  gap: 1rem;
}

.body > p {
  margin: 0;
  line-height: 1.7;
}

.nav {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

@media (max-width: 30rem) {
  .panel {
    padding: 1.25rem;
  }

  .steps {
    font-size: 0.72rem;
  }
}
</style>
