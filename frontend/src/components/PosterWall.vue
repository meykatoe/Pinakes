<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  getItemRefs,
  listCategories,
  listMedia,
  scrapeAll,
  type Category,
  type MediaEntry,
} from '../api'
import { recentProgress } from '../playback'
import { buildResume, type ResumeCard } from '../resume'
import { go, route } from '../router'
import { toast, toastError } from '../ui/toast'
import MediaDetailDialog from './MediaDetailDialog.vue'
import PosterCard from './PosterCard.vue'

const entries = ref<MediaEntry[]>([])
const categories = ref<Category[]>([])
const query = ref('')
const sort = ref('recent')
const kind = ref<'' | 'movie' | 'tv'>('')
const category = ref<number | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const resume = ref<ResumeCard[]>([])
let timer: number | undefined

async function load() {
  try {
    entries.value = await listMedia(query.value, sort.value)
  } catch (err) {
    toastError(err)
  } finally {
    loading.value = false
  }
  loadResume()
}

async function loadResume() {
  const recent = recentProgress()
  if (!recent.length) {
    resume.value = []
    return
  }
  try {
    const refs = await getItemRefs(recent.map((r) => r.itemId))
    resume.value = buildResume(recent, refs, entries.value)
  } catch {
    // 略過失敗
    resume.value = []
  }
}

// 回到頁面時更新
function onVisible() {
  if (!document.hidden) load()
}

onMounted(async () => {
  document.addEventListener('visibilitychange', onVisible)
  try {
    categories.value = await listCategories()
  } catch {
    // 忽略
  }
  await load()
})

onUnmounted(() => document.removeEventListener('visibilitychange', onVisible))

watch([query, sort], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(load, 250)
})

const selected = computed(() => {
  if (route.value[1] !== 'movie' && route.value[1] !== 'tv') return null
  const id = Number(route.value[2])
  return entries.value.find((e) => e.media_type === route.value[1] && e.tmdb_id === id) ?? null
})

const open = (e: MediaEntry) => go('wall', e.media_type, String(e.tmdb_id))
const close = () => go('wall')

const resumeItem = computed(() =>
  route.value[3] === 'play' ? Number(route.value[4]) || null : null,
)
const openResume = (c: ResumeCard) =>
  go('wall', c.entry.media_type, String(c.entry.tmdb_id), 'play', String(c.itemId))
const resumed = () => {
  if (selected.value) open(selected.value)
}

watch(selected, (now) => {
  if (!now) loadResume()
})

const filtered = computed(() =>
  entries.value.filter(
    (e) =>
      (!kind.value || e.media_type === kind.value) &&
      (category.value === null || e.category_id === category.value),
  ),
)

const browsing = computed(
  () => !query.value && !kind.value && category.value === null && sort.value === 'recent',
)

const featured = computed(() =>
  browsing.value ? entries.value.find((e) => e.backdrop_url) ?? null : null,
)

const rows = computed(() => {
  const list: { title: string; items: MediaEntry[] }[] = []
  const recent = [...entries.value]
    .sort((a, b) => b.added_at.localeCompare(a.added_at))
    .slice(0, 20)
  if (recent.length) list.push({ title: '最近新增', items: recent })
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

const counts = computed(() => ({
  movie: entries.value.filter((e) => e.media_type === 'movie').length,
  tv: entries.value.filter((e) => e.media_type === 'tv').length,
}))

async function refresh() {
  refreshing.value = true
  try {
    const r = await scrapeAll()
    toast(r.scraped ? `已更新 ${r.scraped} 部作品的資料` : '所有作品資料都是最新的')
    await load()
  } catch (err) {
    toastError(err)
  } finally {
    refreshing.value = false
  }
}

function scroll(e: MouseEvent, dir: number) {
  const strip = (e.currentTarget as HTMLElement).parentElement?.querySelector('.strip')
  strip?.scrollBy({ left: dir * strip.clientWidth * 0.85, behavior: 'smooth' })
}
</script>

<template>
  <section class="wall">
    <div
      v-if="featured"
      class="hero"
      :style="{ backgroundImage: `url(${featured.backdrop_url})` }"
    >
      <div class="shade">
        <span class="badge">最新加入</span>
        <h1>{{ featured.title }}</h1>
        <p class="facts">
          <span v-if="featured.year">{{ featured.year }}</span>
          <span v-if="featured.rating">★ {{ featured.rating.toFixed(1) }}</span>
          <span v-if="featured.genres.length">{{ featured.genres.slice(0, 3).join(' · ') }}</span>
        </p>
        <p class="overview">{{ featured.overview }}</p>
        <button type="button" class="btn primary" @click="open(featured)">查看詳情</button>
      </div>
    </div>

    <div class="bar">
      <input v-model="query" type="search" class="input search" placeholder="搜尋片名或原文片名" />
      <div class="chips">
        <button type="button" :class="{ on: !kind }" @click="kind = ''">全部</button>
        <button type="button" :class="{ on: kind === 'movie' }" @click="kind = 'movie'">
          電影 <small>{{ counts.movie }}</small>
        </button>
        <button type="button" :class="{ on: kind === 'tv' }" @click="kind = 'tv'">
          影集 <small>{{ counts.tv }}</small>
        </button>
      </div>
      <select v-if="categories.length > 2" v-model="category" class="input narrow" aria-label="分類">
        <option :value="null">所有分類</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-model="sort" class="input narrow" aria-label="排序">
        <option value="recent">最近新增</option>
        <option value="title">片名</option>
        <option value="rating">評分</option>
        <option value="year">年份</option>
      </select>
      <span class="spacer"></span>
      <button
        type="button"
        class="btn ghost sm"
        :disabled="refreshing"
        title="補抓缺少的海報與資料"
        @click="refresh"
      >
        <span v-if="refreshing" class="spin"></span>
        更新資料
      </button>
    </div>

    <div v-if="loading" class="grid">
      <div v-for="n in 12" :key="n" class="ph skeleton"></div>
    </div>

    <div v-else-if="!entries.length && !query" class="card welcome">
      <h2>媒體庫還是空的</h2>
      <p class="muted">整理完成的影片會出現在這裡，並自動抓取海報與簡介。</p>
      <a class="btn primary" href="#/organize">開始整理</a>
    </div>

    <p v-else-if="!filtered.length" class="empty">找不到符合的作品</p>

    <template v-else-if="browsing">
      <div v-if="resume.length" class="shelf">
        <h2>繼續觀看 <small class="muted">{{ resume.length }}</small></h2>
        <div class="strip-wrap">
          <button type="button" class="nav prev" aria-label="向左" @click="scroll($event, -1)">‹</button>
          <div class="strip">
            <PosterCard
              v-for="c in resume"
              :key="c.itemId"
              :entry="c.entry"
              :progress="c.progress"
              :note="c.note"
              @select="openResume(c)"
            />
          </div>
          <button type="button" class="nav next" aria-label="向右" @click="scroll($event, 1)">›</button>
        </div>
      </div>
      <div v-for="row in rows" :key="row.title" class="shelf">
        <h2>{{ row.title }} <small class="muted">{{ row.items.length }}</small></h2>
        <div class="strip-wrap">
          <button type="button" class="nav prev" aria-label="向左" @click="scroll($event, -1)">‹</button>
          <div class="strip">
            <PosterCard
              v-for="e in row.items"
              :key="e.media_type + e.tmdb_id"
              :entry="e"
              @select="open"
            />
          </div>
          <button type="button" class="nav next" aria-label="向右" @click="scroll($event, 1)">›</button>
        </div>
      </div>
    </template>

    <div v-else class="grid">
      <PosterCard
        v-for="e in filtered"
        :key="e.media_type + e.tmdb_id"
        :entry="e"
        @select="open"
      />
    </div>

    <MediaDetailDialog
      v-if="selected"
      :key="selected.media_type + selected.tmdb_id"
      :entry="selected"
      :resume-item="resumeItem"
      @resumed="resumed"
      @close="close"
      @changed="load"
    />
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  margin: -1.5rem -1.5rem 1.5rem;
  min-height: 22rem;
  background: center 25% / cover no-repeat;
  display: flex;
  align-items: flex-end;
}

.shade {
  width: 100%;
  padding: 4rem 1.5rem 1.75rem;
  background:
    linear-gradient(to top, var(--bg) 2%, transparent 70%),
    linear-gradient(to right, rgb(0 0 0 / 0.7), transparent 65%);
  color: #fff;
}

.hero h1 {
  font-size: clamp(1.6rem, 4vw, 2.6rem);
  margin: 0.5rem 0 0.25rem;
  text-shadow: 0 2px 12px rgb(0 0 0 / 0.5);
}

.hero .facts {
  display: flex;
  gap: 0.9rem;
  margin: 0 0 0.5rem;
  opacity: 0.9;
  font-size: 0.92rem;
}

.hero .overview {
  max-width: 40rem;
  margin: 0 0 1rem;
  opacity: 0.85;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

:root[data-theme='light'] .shade {
  color: var(--text);
  background:
    linear-gradient(to top, var(--bg) 5%, transparent 75%),
    linear-gradient(to right, rgb(255 255 255 / 0.85), transparent 70%);
}

:root[data-theme='light'] .hero h1 {
  text-shadow: none;
}

.bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 1.5rem;
}

.search {
  width: 16rem;
  max-width: 100%;
}

.narrow {
  width: auto;
}

.chips {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.chips button {
  all: unset;
  cursor: pointer;
  padding: 0.35rem 0.8rem;
  font-size: 0.9rem;
}

.chips button + button {
  border-left: 1px solid var(--border);
}

.chips button.on {
  background: var(--surface-3);
  font-weight: 600;
}

.chips button:focus-visible {
  outline: 2px solid var(--accent);
}

.chips small {
  color: var(--muted);
}

.shelf {
  margin-bottom: 2rem;
}

.shelf h2 {
  margin: 0 0 0.75rem;
  font-size: 1.15rem;
}

.shelf h2 small {
  font-size: 0.8rem;
  font-weight: 400;
}

.strip-wrap {
  position: relative;
}

.strip {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 9.5rem;
  gap: 1rem;
  overflow-x: auto;
  padding: 0.35rem 0 0.75rem;
  scroll-snap-type: x proximity;
  scrollbar-width: thin;
}

.strip > * {
  scroll-snap-align: start;
}

.nav {
  all: unset;
  position: absolute;
  top: 0;
  bottom: 3.5rem;
  z-index: 2;
  width: 2.5rem;
  display: grid;
  place-items: center;
  font-size: 2rem;
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.prev {
  left: 0;
  background: linear-gradient(to right, rgb(0 0 0 / 0.6), transparent);
}

.next {
  right: 0;
  background: linear-gradient(to left, rgb(0 0 0 / 0.6), transparent);
}

.strip-wrap:hover .nav {
  opacity: 1;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
  gap: 1.25rem 1rem;
}

.ph {
  aspect-ratio: 2 / 3;
  border-radius: 0.55rem;
}

.welcome {
  text-align: center;
  padding: 3rem 1rem;
}

@media (hover: none) {
  .nav {
    display: none;
  }
}

@media (max-width: 40rem) {
  .hero {
    margin: -1rem -1rem 1rem;
    min-height: 16rem;
  }

  .shade {
    padding: 3rem 1rem 1.25rem;
  }

  .strip {
    grid-auto-columns: 7.5rem;
    gap: 0.75rem;
  }

  .grid {
    grid-template-columns: repeat(auto-fill, minmax(7.5rem, 1fr));
    gap: 1rem 0.75rem;
  }

  .search {
    width: 100%;
  }
}
</style>
