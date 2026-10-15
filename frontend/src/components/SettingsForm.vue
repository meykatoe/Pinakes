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
  tmdb_api_key: '',
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
  tmdb_language: '',
})
const results = reactive<Record<string, string>>({})
const message = ref('')

function fill(data: Settings) {
  saved.value = data
  form.openai_base_url = data.openai_base_url
  form.openai_model = data.openai_model
  form.tmdb_language = data.tmdb_language
  form.tmdb_api_key = ''
  form.openai_api_key = ''
}

onMounted(async () => fill(await getSettings()))

async function save() {
  // 空白金鑰不送出
  const body: Partial<Settings> = { ...form }
  if (!form.tmdb_api_key) delete body.tmdb_api_key
  if (!form.openai_api_key) delete body.openai_api_key
  fill(await saveSettings(body))
  message.value = '已儲存'
}

async function test(target: 'tmdb' | 'openai') {
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
      <button type="button" @click="test('openai')">測試連線</button>
      <span>{{ results.openai }}</span>
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
</style>
