<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  getSettings,
  saveSettings,
  testConnection,
  type Settings,
} from '../api'

const saved = ref<Settings | null>(null)
const form = reactive({
  ffmpeg_path: '',
  public_base_url: '',
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_security: 'starttls',
  smtp_from: '',
  notify_to: '',
  notify_enabled: false,
  tmdb_api_key: '',
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
  tmdb_language: '',
  ai_enabled: true,
  ai_daily_limit: 200,
  ai_auto_apply: true,
  watch_enabled: false,
  watch_interval: 30,
  stable_seconds: 60,
  auto_execute: true,
  organize_mode: 'hardlink',
  conflict_policy: 'skip',
})
const results = reactive<Record<string, string>>({})
const message = ref('')

function fill(data: Settings) {
  saved.value = data
  form.openai_base_url = data.openai_base_url
  form.openai_model = data.openai_model
  form.tmdb_language = data.tmdb_language
  form.ai_enabled = data.ai_enabled
  form.ai_daily_limit = data.ai_daily_limit
  form.ai_auto_apply = data.ai_auto_apply
  form.watch_enabled = data.watch_enabled
  form.watch_interval = data.watch_interval
  form.stable_seconds = data.stable_seconds
  form.auto_execute = data.auto_execute
  form.organize_mode = data.organize_mode
  form.conflict_policy = data.conflict_policy
  form.tmdb_api_key = ''
  form.openai_api_key = ''
  form.smtp_password = ''
  form.public_base_url = data.public_base_url
  form.ffmpeg_path = data.ffmpeg_path
  form.smtp_host = data.smtp_host
  form.smtp_port = data.smtp_port
  form.smtp_user = data.smtp_user
  form.smtp_security = data.smtp_security
  form.smtp_from = data.smtp_from
  form.notify_to = data.notify_to
  form.notify_enabled = data.notify_enabled
}

onMounted(async () => fill(await getSettings()))

async function save() {
  // 空白金鑰不送出
  const body: Partial<Settings> = { ...form }
  if (!form.tmdb_api_key) delete body.tmdb_api_key
  if (!form.openai_api_key) delete body.openai_api_key
  if (!form.smtp_password) delete body.smtp_password
  try {
    fill(await saveSettings(body))
    message.value = '已儲存'
  } catch (err) {
    message.value = (err as Error).message
  }
}

async function test(target: 'tmdb' | 'openai' | 'smtp') {
  results[target] = '測試中'
  const res = await testConnection(target)
  results[target] = `${res.ok ? '成功' : '失敗'}：${res.message}`
}
</script>

<template>
  <form class="settings" @submit.prevent="save">
    <h2>API 設定</h2>

    <fieldset>
      <legend>TMDB</legend>
      <label>
        API 金鑰或讀取權杖
        <input
          v-model="form.tmdb_api_key"
          type="password"
          autocomplete="off"
          :placeholder="saved?.tmdb_api_key || '尚未設定'"
        />
      </label>
      <label>
        語言
        <input v-model="form.tmdb_language" />
      </label>
      <button type="button" @click="test('tmdb')">測試連線</button>
      <span>{{ results.tmdb }}</span>
    </fieldset>

    <fieldset>
      <legend>OpenAI</legend>
      <label>
        API 金鑰
        <input
          v-model="form.openai_api_key"
          type="password"
          autocomplete="off"
          :placeholder="saved?.openai_api_key || '尚未設定'"
        />
      </label>
      <label>
        接口網址
        <input v-model="form.openai_base_url" />
      </label>
      <label>
        模型
        <input v-model="form.openai_model" />
      </label>
      <label class="check">
        <input v-model="form.ai_enabled" type="checkbox" />
        啟用 AI 輔助辨識
      </label>
      <label class="check">
        <input v-model="form.ai_auto_apply" type="checkbox" />
        AI 的判斷結果自動採用（取消則需人工確認）
      </label>
      <label>
        每日呼叫上限
        <input v-model.number="form.ai_daily_limit" type="number" min="0" />
      </label>
      <button type="button" @click="test('openai')">測試連線</button>
      <span>{{ results.openai }}</span>
    </fieldset>

    <fieldset>
      <legend>整理方式</legend>
      <label>
        檔案處理模式
        <select v-model="form.organize_mode">
          <option value="hardlink">硬連結（需同磁碟）</option>
          <option value="move">移動</option>
          <option value="copy">複製</option>
          <option value="symlink">軟連結</option>
        </select>
      </label>
      <label>
        目標已存在時
        <select v-model="form.conflict_policy">
          <option value="skip">略過</option>
          <option value="keep_larger">保留較大的檔案</option>
          <option value="overwrite">覆蓋（舊檔會備份）</option>
        </select>
      </label>
    </fieldset>

    <fieldset>
      <legend>自動監控</legend>
      <label class="check">
        <input v-model="form.watch_enabled" type="checkbox" />
        啟用待整理目錄監控
      </label>
      <label class="check">
        <input v-model="form.auto_execute" type="checkbox" />
        辨識確定後自動執行（取消則只產生計畫）
      </label>
      <label>
        掃描間隔（秒，最少 5）
        <input v-model.number="form.watch_interval" type="number" min="5" />
      </label>
      <label>
        檔案穩定時間（秒，大小與修改時間不變多久才處理）
        <input v-model.number="form.stable_seconds" type="number" min="0" />
      </label>
    </fieldset>

    <fieldset>
      <legend>播放</legend>
      <label>
        串流網址前綴（留空則自動判斷，播放器在別台裝置時填後端的區網位址）
        <input v-model="form.public_base_url" placeholder="http://192.168.1.10:8000" />
      </label>
      <label>
        ffmpeg 路徑（內建播放用，留空則從系統 PATH 尋找）
        <input v-model="form.ffmpeg_path" placeholder="/usr/bin/ffmpeg" />
      </label>
    </fieldset>

    <fieldset>
      <legend>Email 通知</legend>
      <label class="check">
        <input v-model="form.notify_enabled" type="checkbox" />
        自動整理完成後寄出通知
      </label>
      <label>
        收件 Email
        <input v-model="form.notify_to" type="email" />
      </label>
      <label>
        SMTP 主機
        <input v-model="form.smtp_host" placeholder="smtp.gmail.com" />
      </label>
      <label>
        連接埠
        <input v-model.number="form.smtp_port" type="number" min="1" max="65535" />
      </label>
      <label>
        加密方式
        <select v-model="form.smtp_security">
          <option value="starttls">STARTTLS（通常 587）</option>
          <option value="ssl">SSL（通常 465）</option>
          <option value="none">不加密</option>
        </select>
      </label>
      <label>
        帳號
        <input v-model="form.smtp_user" autocomplete="off" />
      </label>
      <label>
        密碼
        <input
          v-model="form.smtp_password"
          type="password"
          autocomplete="off"
          :placeholder="saved?.smtp_password || '尚未設定'"
        />
      </label>
      <label>
        寄件人（留空則使用帳號）
        <input v-model="form.smtp_from" type="email" />
      </label>
      <button type="button" @click="test('smtp')">寄送測試信</button>
      <span>{{ results.smtp }}</span>
    </fieldset>

    <button type="submit">儲存</button>
    <span>{{ message }}</span>
  </form>
</template>

<style scoped>
.settings {
  max-width: 32rem;
}

fieldset {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

label {
  display: grid;
  gap: 0.25rem;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
