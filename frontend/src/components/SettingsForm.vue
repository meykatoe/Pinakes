<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { getSettings, saveSettings, testConnection, type Settings } from '../api'
import { toast, toastError } from '../ui/toast'

type Section = 'connect' | 'organize' | 'playback' | 'notify'
type Key = keyof Settings

const props = defineProps<{ section: Section }>()

const FIELDS: Record<Section, Key[]> = {
  connect: [
    'tmdb_api_key', 'tmdb_language', 'openai_api_key', 'openai_base_url',
    'openai_model', 'ai_enabled', 'ai_auto_apply', 'ai_daily_limit',
  ],
  organize: [
    'organize_mode', 'conflict_policy', 'watch_enabled', 'auto_execute',
    'watch_interval', 'stable_seconds',
  ],
  playback: ['public_base_url', 'ffmpeg_path'],
  notify: [
    'notify_enabled', 'notify_to', 'smtp_host', 'smtp_port', 'smtp_security',
    'smtp_user', 'smtp_password', 'smtp_from',
  ],
}
const SECRETS: Key[] = ['tmdb_api_key', 'openai_api_key', 'smtp_password']

const saved = ref<Settings | null>(null)
const form = reactive<Partial<Settings>>({})
const results = reactive<Record<string, { ok: boolean; text: string } | null>>({})
const testing = reactive<Record<string, boolean>>({})
const saving = ref(false)

const dirty = computed(() => {
  if (!saved.value) return false
  return FIELDS[props.section].some((k) =>
    SECRETS.includes(k) ? !!form[k] : form[k] !== saved.value![k],
  )
})

function fill(data: Settings) {
  saved.value = data
  for (const key of FIELDS[props.section]) {
    ;(form as Record<string, unknown>)[key] = SECRETS.includes(key) ? '' : data[key]
  }
}

onMounted(async () => {
  try {
    fill(await getSettings())
  } catch (err) {
    toastError(err)
  }
})

async function save() {
  const body: Partial<Settings> = {}
  for (const key of FIELDS[props.section]) {
    if (SECRETS.includes(key) && !form[key]) continue
    ;(body as Record<string, unknown>)[key] = form[key]
  }
  saving.value = true
  try {
    fill(await saveSettings(body))
    toast('設定已儲存')
  } catch (err) {
    toastError(err)
  } finally {
    saving.value = false
  }
}

async function clearSecret(key: Key) {
  try {
    fill(await saveSettings({ [key]: '' } as Partial<Settings>))
    toast('已清除')
  } catch (err) {
    toastError(err)
  }
}

async function test(target: 'tmdb' | 'openai' | 'smtp') {
  if (dirty.value) await save()
  testing[target] = true
  results[target] = null
  try {
    const res = await testConnection(target)
    results[target] = { ok: res.ok, text: res.message }
  } catch (err) {
    results[target] = { ok: false, text: (err as Error).message }
  } finally {
    testing[target] = false
  }
}
</script>

<template>
  <form v-if="saved" class="settings" @submit.prevent="save">
    <template v-if="section === 'connect'">
      <section class="card">
        <div class="card-head">
          <h2>TMDB</h2>
          <span v-if="saved.tmdb_api_key" class="badge ok">已設定</span>
          <span v-else class="badge warn">必填</span>
        </div>
        <p class="hint intro">
          用於辨識影片與抓取海報。到
          <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noopener noreferrer">
            TMDB 帳號設定
          </a>
          申請，API Key（v3）或讀取權杖（v4）皆可。
        </p>
        <div class="form-grid">
          <label class="field">
            <span>API 金鑰或讀取權杖</span>
            <input
              v-model="form.tmdb_api_key"
              class="input"
              type="password"
              autocomplete="off"
              :placeholder="saved.tmdb_api_key || '尚未設定'"
            />
          </label>
          <label class="field">
            <span>語言</span>
            <input v-model="form.tmdb_language" class="input" placeholder="zh-TW" />
            <p class="hint">影響片名與簡介語言，例如 zh-TW、zh-CN、en-US、ja-JP</p>
          </label>
        </div>
        <div class="row test">
          <button type="button" class="btn sm" :disabled="testing.tmdb" @click="test('tmdb')">
            <span v-if="testing.tmdb" class="spin"></span>
            測試連線
          </button>
          <span v-if="results.tmdb" :class="results.tmdb.ok ? 'ok-text' : 'danger-text'">
            {{ results.tmdb.text }}
          </span>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>AI 輔助辨識</h2>
          <span class="badge">選用</span>
        </div>
        <p class="hint intro">
          檔名難以辨識時，讓 AI 改寫搜尋字串或從候選中挑選。支援任何相容 OpenAI 的接口。
        </p>
        <div class="form-grid">
          <label class="check full">
            <input v-model="form.ai_enabled" type="checkbox" />
            <span>啟用 AI 輔助辨識</span>
          </label>
          <label class="field">
            <span>API 金鑰</span>
            <input
              v-model="form.openai_api_key"
              class="input"
              type="password"
              autocomplete="off"
              :placeholder="saved.openai_api_key || '尚未設定'"
            />
          </label>
          <label class="field">
            <span>模型</span>
            <input v-model="form.openai_model" class="input" placeholder="gpt-4o-mini" />
          </label>
          <label class="field full">
            <span>接口網址</span>
            <input v-model="form.openai_base_url" class="input" placeholder="https://api.openai.com/v1" />
          </label>
          <label class="field">
            <span>每日呼叫上限</span>
            <input v-model.number="form.ai_daily_limit" class="input" type="number" min="0" />
          </label>
          <label class="check">
            <input v-model="form.ai_auto_apply" type="checkbox" />
            <span>
              自動採用 AI 的判斷
              <p class="hint">取消則 AI 選出的結果需人工確認</p>
            </span>
          </label>
        </div>
        <div class="row test">
          <button type="button" class="btn sm" :disabled="testing.openai" @click="test('openai')">
            <span v-if="testing.openai" class="spin"></span>
            測試連線
          </button>
          <button
            v-if="saved.openai_api_key"
            type="button"
            class="btn sm ghost danger"
            @click="clearSecret('openai_api_key')"
          >
            清除金鑰
          </button>
          <span v-if="results.openai" :class="results.openai.ok ? 'ok-text' : 'danger-text'">
            {{ results.openai.text }}
          </span>
        </div>
      </section>
    </template>

    <template v-else-if="section === 'organize'">
      <section class="card">
        <div class="card-head"><h2>整理方式</h2></div>
        <div class="form-grid">
          <label class="field">
            <span>檔案處理模式</span>
            <select v-model="form.organize_mode" class="input">
              <option value="hardlink">硬連結（推薦，不佔空間，需同磁碟）</option>
              <option value="move">移動</option>
              <option value="copy">複製</option>
              <option value="symlink">軟連結</option>
            </select>
            <p class="hint">硬連結可保留原檔繼續做種，且不額外佔用空間</p>
          </label>
          <label class="field">
            <span>目標已存在時</span>
            <select v-model="form.conflict_policy" class="input">
              <option value="skip">略過</option>
              <option value="keep_larger">保留較大的檔案</option>
              <option value="overwrite">覆蓋（舊檔會備份）</option>
            </select>
          </label>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2>自動監控</h2>
          <span v-if="saved.watch_enabled" class="badge ok">運作中</span>
        </div>
        <div class="form-grid">
          <label class="check full">
            <input v-model="form.watch_enabled" type="checkbox" />
            <span>
              監控待整理目錄
              <p class="hint">定期掃描新檔案，下載完成後自動辨識</p>
            </span>
          </label>
          <label class="check full">
            <input v-model="form.auto_execute" type="checkbox" />
            <span>
              辨識確定後自動執行
              <p class="hint">取消則只產生計畫，需到「整理」頁手動執行</p>
            </span>
          </label>
          <label class="field">
            <span>掃描間隔（秒）</span>
            <input v-model.number="form.watch_interval" class="input" type="number" min="5" />
          </label>
          <label class="field">
            <span>檔案穩定時間（秒）</span>
            <input v-model.number="form.stable_seconds" class="input" type="number" min="0" />
            <p class="hint">大小與修改時間維持不變多久才處理，避免處理下載中的檔案</p>
          </label>
        </div>
      </section>
    </template>

    <template v-else-if="section === 'playback'">
      <section class="card">
        <div class="card-head"><h2>串流與轉碼</h2></div>
        <div class="form-grid">
          <label class="field full">
            <span>串流網址前綴</span>
            <input v-model="form.public_base_url" class="input" placeholder="http://192.168.1.10:8000" />
            <p class="hint">
              留空則依瀏覽器網址自動判斷。外部播放器在其他裝置、或經過反向代理時請填入可連到 Pinakes 的網址
            </p>
          </label>
          <label class="field full">
            <span>ffmpeg 路徑</span>
            <input v-model="form.ffmpeg_path" class="input mono" placeholder="/usr/bin/ffmpeg" />
            <p class="hint">內建播放器轉碼用，留空則從系統 PATH 尋找，ffprobe 需在同一目錄</p>
          </label>
        </div>
      </section>
    </template>

    <template v-else>
      <section class="card">
        <div class="card-head">
          <h2>Email 通知</h2>
          <span v-if="saved.notify_enabled" class="badge ok">已啟用</span>
        </div>
        <div class="form-grid">
          <label class="check full">
            <input v-model="form.notify_enabled" type="checkbox" />
            <span>
              自動整理後寄出摘要
              <p class="hint">監控每次處理完新檔案，彙整成一封信寄出</p>
            </span>
          </label>
          <label class="field">
            <span>收件 Email</span>
            <input v-model="form.notify_to" class="input" type="email" />
          </label>
          <label class="field">
            <span>寄件人</span>
            <input v-model="form.smtp_from" class="input" type="email" placeholder="留空則使用帳號" />
          </label>
          <label class="field">
            <span>SMTP 主機</span>
            <input v-model="form.smtp_host" class="input" placeholder="smtp.gmail.com" />
          </label>
          <label class="field">
            <span>連接埠</span>
            <input v-model.number="form.smtp_port" class="input" type="number" min="1" max="65535" />
          </label>
          <label class="field">
            <span>加密方式</span>
            <select v-model="form.smtp_security" class="input">
              <option value="starttls">STARTTLS（通常 587）</option>
              <option value="ssl">SSL（通常 465）</option>
              <option value="none">不加密</option>
            </select>
          </label>
          <label class="field">
            <span>帳號</span>
            <input v-model="form.smtp_user" class="input" autocomplete="off" />
          </label>
          <label class="field">
            <span>密碼</span>
            <input
              v-model="form.smtp_password"
              class="input"
              type="password"
              autocomplete="new-password"
              :placeholder="saved.smtp_password || '尚未設定'"
            />
            <p class="hint">Gmail 請使用應用程式密碼</p>
          </label>
        </div>
        <div class="row test">
          <button type="button" class="btn sm" :disabled="testing.smtp" @click="test('smtp')">
            <span v-if="testing.smtp" class="spin"></span>
            寄送測試信
          </button>
          <span v-if="results.smtp" :class="results.smtp.ok ? 'ok-text' : 'danger-text'">
            {{ results.smtp.text }}
          </span>
        </div>
      </section>
    </template>

    <div class="savebar" :class="{ show: dirty }">
      <span class="muted">有未儲存的變更</span>
      <button type="button" class="btn ghost" @click="fill(saved!)">捨棄</button>
      <button type="submit" class="btn primary" :disabled="saving">
        <span v-if="saving" class="spin"></span>
        儲存
      </button>
    </div>
  </form>
  <div v-else class="card skeleton placeholder"></div>
</template>

<style scoped>
.settings {
  display: grid;
  gap: 1rem;
  margin-bottom: 1rem;
}

.card + .card {
  margin-top: 0;
}

.intro {
  margin: -0.5rem 0 1rem;
}

.test {
  margin-top: 1rem;
  font-size: 0.88rem;
}

.check .hint {
  margin-top: 0.1rem;
}

.savebar {
  position: fixed;
  left: 50%;
  bottom: 1.25rem;
  z-index: 20;
  width: min(40rem, calc(100% - 2rem));
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.6rem;
  padding: 0.6rem 0.8rem;
  border-radius: var(--radius);
  background: var(--surface-2);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  opacity: 0;
  transform: translate(-50%, 0.75rem);
  pointer-events: none;
  transition: all 0.2s;
}

.savebar.show {
  opacity: 1;
  transform: translate(-50%, 0);
  pointer-events: auto;
}

.savebar .muted {
  margin-right: auto;
  font-size: 0.88rem;
}

.placeholder {
  height: 16rem;
  margin-bottom: 1rem;
}
</style>
