<script setup lang="ts">
import { ref } from 'vue'
import { previewMatch, type MatchResult } from '../api'

const path = ref('')
const result = ref<MatchResult | null>(null)
const message = ref('')

async function run(tmdbId?: number) {
  try {
    result.value = await previewMatch(path.value, tmdbId)
    message.value = ''
  } catch (err) {
    message.value = (err as Error).message
  }
}
</script>

<template>
  <section class="match">
    <h2>TMDB 比對測試</h2>
    <form @submit.prevent="run()">
      <input v-model="path" placeholder="貼上檔名或相對路徑" />
      <button type="submit">比對</button>
    </form>
    <p>{{ message }}</p>

    <div v-if="result">
      <p v-if="result.target">
        {{ result.confident ? '已確定' : '已選擇' }}：{{ result.target }}
      </p>
      <p v-else class="warn">無法確定，需要人工確認</p>
      <p v-if="result.error" class="warn">{{ result.error }}</p>

      <table v-if="result.candidates.length">
        <thead>
          <tr>
            <th>片名</th>
            <th>原名</th>
            <th>年份</th>
            <th>分數</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in result.candidates" :key="c.tmdb_id">
            <td>{{ c.title }}</td>
            <td>{{ c.original_title }}</td>
            <td>{{ c.year }}</td>
            <td>{{ c.score }}</td>
            <td><button type="button" @click="run(c.tmdb_id)">選用</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.match {
  max-width: 48rem;
  margin-top: 2rem;
}

form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
}

.warn {
  color: #b45309;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  text-align: left;
  padding: 0.25rem;
}
</style>
