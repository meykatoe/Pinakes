<script setup lang="ts">
import { ref } from 'vue'
import { previewMatch, type MatchResult } from '../api'
import { posterThumb } from '../format'
import { toastError } from '../ui/toast'

const path = ref('')
const result = ref<MatchResult | null>(null)
const busy = ref(false)
const methodText: Record<string, string> = {
  rule: '規則比對',
  ai: 'AI 判斷',
  manual: '手動指定',
}

async function run(tmdbId?: number) {
  busy.value = true
  try {
    result.value = await previewMatch(path.value, tmdbId)
  } catch (err) {
    toastError(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <div class="card-head"><h2>TMDB 比對測試</h2></div>
    <p class="hint intro">完整模擬整理流程，會連線 TMDB（與 AI），確認檔名能否正確辨識。</p>
    <form class="row" @submit.prevent="run()">
      <input
        v-model="path"
        class="input mono grow"
        placeholder="The.Matrix.1999.1080p.BluRay.x264.mkv"
      />
      <button type="submit" class="btn primary" :disabled="busy || !path.trim()">
        <span v-if="busy" class="spin"></span>
        比對
      </button>
    </form>

    <div v-if="result" class="result">
      <div v-if="result.target" class="notice info">
        <span class="badge info">{{ methodText[result.method ?? ''] ?? '比對' }}</span>
        <code class="break">{{ result.target }}</code>
      </div>
      <div v-else class="notice">無法自動確定，實際整理時會列為待確認</div>
      <p v-if="result.reason" class="muted">{{ result.reason }}</p>
      <p v-if="result.error" class="danger-text">{{ result.error }}</p>

      <ul v-if="result.candidates.length" class="cands">
        <li
          v-for="c in result.candidates"
          :key="c.tmdb_id"
          :class="{ chosen: result.chosen?.tmdb_id === c.tmdb_id }"
        >
          <img v-if="c.poster_path" :src="posterThumb(c.poster_path)" alt="" loading="lazy" />
          <div v-else class="noimg"></div>
          <div class="info">
            <strong>{{ c.title }}</strong>
            <span class="muted">
              {{ c.original_title !== c.title ? c.original_title + ' · ' : '' }}{{ c.year ?? '年份不明' }}
            </span>
            <span class="muted score">相似度 {{ Math.round(c.score * 100) }}%</span>
          </div>
          <button type="button" class="btn sm" :disabled="busy" @click="run(c.tmdb_id)">選用</button>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.intro {
  margin: -0.5rem 0 1rem;
}

.grow {
  flex: 1;
  min-width: 12rem;
}

.result {
  margin-top: 1rem;
}

.notice {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.cands {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0;
  display: grid;
  gap: 0.5rem;
}

.cands li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  border: 1px solid transparent;
}

.cands li.chosen {
  border-color: var(--accent);
}

.cands img,
.noimg {
  width: 2.5rem;
  aspect-ratio: 2 / 3;
  border-radius: 4px;
  object-fit: cover;
  background: var(--surface-3);
  flex: none;
}

.info {
  flex: 1;
  min-width: 0;
  display: grid;
  font-size: 0.9rem;
}

.score {
  font-size: 0.8rem;
}
</style>
