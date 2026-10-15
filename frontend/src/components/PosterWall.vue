<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  listCategories,
  listMedia,
  scrapeAll,
  type Category,
  type MediaEntry,
} from '../api'
import MediaDetailDialog from './MediaDetailDialog.vue'
import PosterCard from './PosterCard.vue'

const entries = ref<MediaEntry[]>([])
const categories = ref<Category[]>([])
const query = ref('')
const sort = ref('recent')
const selected = ref<MediaEntry | null>(null)
const message = ref('')
let timer: number | undefined

async function load() {
  try {
    entries.value = await listMedia(query.value, sort.value)
  } catch (err) {
    message.value = (err as Error).message
  }
}

onMounted(async () => {
  categories.value = await listCategories()
  await load()
})

watch([query, sort], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(load, 250)
})

const rows = computed(() => {
  const list: { title: string; items: MediaEntry[] }[] = []
  if (!query.value) {
    const recent = [...entries.value]
      .sort((a, b) => b.added_at.localeCompare(a.added_at))
      .slice(0, 20)
    if (recent.length) list.push({ title: '最近新增', items: recent })
  }
  const known = new Set(categories.value.map((c) => c.id))
  for (const c of categories.value) {
    const items = entries.value.filter((e) => e.category_id === c.id)
    if (items.length) list.push({ title: c.name, items })
  }
  const other = entries.value.filter(
    (e) => e.category_id === null || !known.has(e.category_id),
  )
  if (other.length) list.push({ title: '其他', items: other })
  return list
})

async function refresh() {
  message.value = '更新中'
  try {
    const r = await scrapeAll()
    message.value = `已更新 ${r.scraped} 部作品`
    await load()
  } catch (err) {
    message.value = (err as Error).message
  }
}
</script>

<template>
  <section class="wall">
    <div class="bar">
      <input v-model="query" type="search" placeholder="搜尋片名" />
      <select v-model="sort">
        <option value="recent">最近新增</option>
        <option value="title">片名</option>
        <option value="rating">評分</option>
        <option value="year">年份</option>
      </select>
      <button type="button" @click="refresh">更新海報與資料</button>
      <span>{{ message }}</span>
    </div>

    <p v-if="!entries.length" class="empty">
      {{ query ? '找不到符合的作品' : '媒體庫還沒有已整理的作品' }}
    </p>

    <template v-if="query">
      <div class="grid">
        <PosterCard v-for="e in entries" :key="e.media_type + e.tmdb_id" :entry="e" @select="selected = $event" />
      </div>
    </template>
    <template v-else>
      <div v-for="row in rows" :key="row.title" class="row">
        <h2>{{ row.title }}</h2>
        <div class="strip">
          <PosterCard v-for="e in row.items" :key="e.media_type + e.tmdb_id" :entry="e" @select="selected = $event" />
        </div>
      </div>
    </template>

    <MediaDetailDialog v-if="selected" :entry="selected" @close="selected = null" @changed="load" />
  </section>
</template>

<style scoped>
.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1.5rem;
}

.row {
  margin-bottom: 2rem;
}

.row h2 {
  margin: 0 0 0.75rem;
  font-size: 1.15rem;
}

.strip {
  display: flex;
  gap: 1rem;
  overflow-x: auto;
  padding-bottom: 0.75rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
  gap: 1rem;
}

.empty {
  opacity: 0.7;
}
</style>
