<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  chooseItem,
  executeAll,
  executeItem,
  getPaths,
  getScanProgress,
  getSummary,
  getWatchStatus,
  listCategories,
  listItems,
  scan,
  skipItem,
  undoItem,
  type Candidate,
  type Category,
  type Item,
  type ScanProgress,
  type WatchStatus,
} from '../api'
import { basename, episodeLabel, posterThumb, relativeTime } from '../format'
import { confirm } from '../ui/confirm'
import { toast, toastError } from '../ui/toast'
import SearchDialog from './SearchDialog.vue'

const STATUS: Record<string, { label: string; tone: string }> = {
  pending_review: { label: '待確認', tone: 'warn' },
  planned: { label: '待執行', tone: 'info' },
  failed: { label: '失敗', tone: 'danger' },
  done: { label: '已完成', tone: 'ok' },
  skipped: { label: '已略過', tone: '' },
  undone: { label: '已還原', tone: '' },
}
const FILTERS = ['pending_review', 'planned', 'failed', 'done', 'skipped', 'undone']
const METHOD: Record<string, string> = { rule: '自動比對', ai: 'AI 判斷', manual: '手動指定' }

const items = ref<Item[]>([])
const summary = ref<Record<string, number>>({})
const categories = ref<Category[]>([])
const watchState = ref<WatchStatus | null>(null)
const progress = ref<ScanProgress | null>(null)
const roots = ref({ inbox: '', library: '' })
const filter = ref('')
const query = ref('')
const loading = ref(true)
const scanning = ref(false)
const working = ref(new Set<number>())
const searching = ref<Item | null>(null)
let poll: number | undefined
let searchTimer: number | undefined

const total = computed(() => Object.values(summary.value).reduce((a, b) => a + b, 0))

async function reload() {
  const [list, sum, ws] = await Promise.all([
    listItems(filter.value, query.value),
    getSummary(),
    getWatchStatus(),
  ])
  items.value = list
  summary.value = sum
  watchState.value = ws
}

async function refresh() {
  try {
    await reload()
  } catch (err) {
    toastError(err)
  }
}

onMounted(async () => {
  try {
    const [cats, paths, sum] = await Promise.all([listCategories(), getPaths(), getSummary()])
    categories.value = cats
    roots.value = { inbox: paths.inbox_path, library: paths.library_path }
    if (sum.pending_review) filter.value = 'pending_review'
    await reload()
  } catch (err) {
    toastError(err)
  } finally {
    loading.value = false
  }
  poll = window.setInterval(tick, 5000)
})

onUnmounted(() => {
  window.clearInterval(poll)
  window.clearTimeout(searchTimer)
})

async function tick() {
  if (document.hidden || scanning.value || working.value.size) return
  try {
    const p = await getScanProgress()
    const wasRunning = progress.value?.running
    progress.value = p
    if (p.running || wasRunning) await reload()
    else watchState.value = await getWatchStatus()
  } catch {
    // 忽略
  }
}

watch(filter, refresh)
watch(query, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(refresh, 300)
})

function rel(path: string, root: string): string {
  if (root && path.startsWith(root)) return path.slice(root.length).replace(/^[\\/]/, '')
  return path
}

function sourceDir(item: Item): string {
  const r = rel(item.source_path, roots.value.inbox)
  const parts = r.split(/[\\/]/)
  return parts.length > 1 ? parts.slice(0, -1).join('/') : ''
}

const catsFor = (item: Item) => categories.value.filter((c) => c.media_type === item.media_type)

async function act(item: Item, fn: () => Promise<Item>, ok?: string) {
  working.value.add(item.id)
  try {
    const updated = await fn()
    const i = items.value.findIndex((x) => x.id === item.id)
    if (i >= 0) items.value[i] = updated
    if (updated.status === 'failed' && updated.error) toast(updated.error, 'error')
    else if (ok) toast(ok)
    summary.value = await getSummary()
  } catch (err) {
    toastError(err)
  } finally {
    working.value.delete(item.id)
  }
}

async function doScan() {
  scanning.value = true
  progress.value = { running: true, done: 0, total: 0, current: '' }
  const timer = window.setInterval(async () => {
    try {
      progress.value = await getScanProgress()
    } catch {
      // 忽略
    }
  }, 800)
  try {
    const r = await scan()
    if (!r.created) toast('沒有發現新檔案', 'info')
    else toast(`發現 ${r.created} 個新檔案：${r.planned} 個可直接執行，${r.pending_review} 個需要確認`)
    filter.value = r.pending_review ? 'pending_review' : r.planned ? 'planned' : filter.value
    await reload()
  } catch (err) {
    toastError(err)
  } finally {
    window.clearInterval(timer)
    scanning.value = false
    progress.value = null
  }
}

async function doExecuteAll() {
  const n = summary.value.planned ?? 0
  if (!(await confirm(`執行全部 ${n} 個待執行項目？`, '執行'))) return
  scanning.value = true
  try {
    const r = await executeAll()
    toast(`完成 ${r.done}，略過 ${r.skipped}，失敗 ${r.failed}`, r.failed ? 'error' : 'ok')
    await reload()
  } catch (err) {
    toastError(err)
  } finally {
    scanning.value = false
  }
}

async function undo(item: Item) {
  const ok = await confirm('還原後整理出的檔案會被移除（移動模式則搬回原處），海報牆也不再顯示。', '還原', true)
  if (ok) await act(item, () => undoItem(item.id), '已還原')
}

function pick(item: Item, c: Candidate) {
  searching.value = null
  act(item, () => chooseItem(item.id, { tmdb_id: c.tmdb_id, media_type: c.media_type }), `已指定為「${c.title}」`)
}

function setCategory(item: Item, e: Event) {
  const id = Number((e.target as HTMLSelectElement).value)
  act(item, () => chooseItem(item.id, { category_id: id }), '已變更分類')
}

const canChoose = (s: string) => ['pending_review', 'planned', 'failed', 'undone', 'skipped'].includes(s)
</script>

<template>
  <section class="organize">
    <div class="head">
      <div>
        <h2>整理</h2>
        <p class="muted sub">
          掃描待整理目錄、確認辨識結果，再依命名樣板放進媒體庫。
        </p>
      </div>
      <span class="spacer"></span>
      <button type="button" class="btn" :disabled="scanning || !summary.planned" @click="doExecuteAll">
        執行全部待執行<span v-if="summary.planned" class="count">{{ summary.planned }}</span>
      </button>
      <button type="button" class="btn primary" :disabled="scanning || progress?.running" @click="doScan">
        <span v-if="scanning" class="spin"></span>
        掃描新檔案
      </button>
    </div>

    <div v-if="progress?.running" class="notice info progress">
      <span class="spin"></span>
      <span>
        正在辨識 {{ progress.done }} / {{ progress.total || '?' }}
        <span v-if="progress.current" class="muted break">· {{ progress.current }}</span>
      </span>
      <div class="bar"><div :style="{ width: progress.total ? (progress.done / progress.total) * 100 + '%' : '5%' }"></div></div>
    </div>

    <div v-if="watchState" class="watch">
      <span class="dot" :class="watchState.enabled ? (watchState.last_error ? 'bad' : 'on') : ''"></span>
      <span v-if="watchState.enabled">
        自動監控中
        <template v-if="watchState.last_run">· 上次檢查 {{ relativeTime(watchState.last_run) }}</template>
        <template v-if="watchState.waiting">· {{ watchState.waiting }} 個檔案等待下載完成</template>
      </span>
      <span v-else class="muted">
        自動監控未啟用，<a href="#/settings/library">前往設定</a>
      </span>
      <span v-if="watchState.last_error" class="danger-text">· {{ watchState.last_error }}</span>
      <span v-if="watchState.last_mail_error" class="danger-text">· 通知：{{ watchState.last_mail_error }}</span>
    </div>

    <div class="filters">
      <div class="chips" role="tablist">
        <button type="button" role="tab" :aria-selected="filter === ''" :class="{ on: filter === '' }" @click="filter = ''">
          全部 <span class="n">{{ total }}</span>
        </button>
        <button
          v-for="f in FILTERS"
          v-show="summary[f] || filter === f"
          :key="f"
          type="button"
          role="tab"
          :aria-selected="filter === f"
          :class="[{ on: filter === f }, STATUS[f].tone]"
          @click="filter = f"
        >
          {{ STATUS[f].label }} <span class="n">{{ summary[f] ?? 0 }}</span>
        </button>
      </div>
      <input v-model="query" type="search" class="input find" placeholder="搜尋檔名或片名" />
    </div>

    <div v-if="loading" class="list">
      <div v-for="n in 3" :key="n" class="item skeleton ph"></div>
    </div>

    <div v-else-if="!items.length" class="card empty">
      <template v-if="query">找不到符合「{{ query }}」的項目</template>
      <template v-else-if="!roots.inbox || !roots.library">
        尚未設定媒體庫目錄。<a href="#/settings/library">前往設定</a>
      </template>
      <template v-else-if="filter">這個分類沒有項目</template>
      <template v-else>還沒有任何項目，按「掃描新檔案」開始整理</template>
    </div>

    <TransitionGroup v-else name="list" tag="div" class="list">
      <article
        v-for="i in items"
        :key="i.id"
        class="item card"
        :class="{ busy: working.has(i.id) }"
      >
        <div class="top">
          <span class="badge" :class="STATUS[i.status]?.tone">{{ STATUS[i.status]?.label ?? i.status }}</span>
          <span class="badge">{{ i.media_type === 'tv' ? '影集' : '電影' }}</span>
          <span v-if="i.method" class="badge">{{ METHOD[i.method] ?? i.method }}</span>
          <span class="spacer"></span>
          <span v-if="working.has(i.id)" class="spin muted"></span>
        </div>

        <div class="main">
          <div class="file">
            <strong class="break">{{ basename(i.source_path) }}</strong>
            <span v-if="sourceDir(i)" class="muted dir break">{{ sourceDir(i) }}</span>
          </div>

          <div v-if="i.tmdb_id" class="match">
            <span class="arrow" aria-hidden="true">→</span>
            <div>
              <strong>{{ i.title }}</strong>
              <span v-if="i.year" class="muted"> ({{ i.year }})</span>
              <span v-if="episodeLabel(i.season, i.episode)" class="muted"> · {{ episodeLabel(i.season, i.episode) }}</span>
              <div v-if="i.target_path" class="muted target break">{{ rel(i.target_path, roots.library) }}</div>
            </div>
          </div>

          <p v-if="i.error" class="danger-text msg">{{ i.error }}</p>
          <p v-else-if="i.reason" class="muted msg">{{ i.reason }}</p>

          <div v-if="i.status === 'pending_review' && i.candidates.length" class="cands">
            <span class="hint">可能是：</span>
            <button
              v-for="c in i.candidates.slice(0, 4)"
              :key="c.tmdb_id"
              type="button"
              class="cand"
              :disabled="working.has(i.id)"
              :title="c.overview"
              @click="pick(i, c)"
            >
              <img v-if="c.poster_path" :src="posterThumb(c.poster_path)" alt="" loading="lazy" />
              <span>
                {{ c.title }}
                <small class="muted">{{ c.year ?? '' }}</small>
              </span>
            </button>
          </div>
        </div>

        <div class="actions">
          <select
            v-if="i.tmdb_id && canChoose(i.status) && catsFor(i).length > 1"
            class="input sm-select"
            :value="i.category_id ?? ''"
            :disabled="working.has(i.id)"
            aria-label="分類"
            @change="setCategory(i, $event)"
          >
            <option v-for="c in catsFor(i)" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <button
            v-if="canChoose(i.status)"
            type="button"
            class="btn sm"
            :class="{ primary: i.status === 'pending_review' }"
            :disabled="working.has(i.id)"
            @click="searching = i"
          >
            {{ i.tmdb_id ? '改選作品' : '搜尋作品' }}
          </button>
          <button
            v-if="i.status === 'planned' || (i.status === 'failed' && i.target_path)"
            type="button"
            class="btn sm primary"
            :disabled="working.has(i.id)"
            @click="act(i, () => executeItem(i.id), '已整理完成')"
          >
            {{ i.status === 'failed' ? '重試' : '執行' }}
          </button>
          <button
            v-if="i.status === 'done'"
            type="button"
            class="btn sm danger"
            :disabled="working.has(i.id)"
            @click="undo(i)"
          >
            還原
          </button>
          <button
            v-if="!['done', 'skipped'].includes(i.status)"
            type="button"
            class="btn sm ghost"
            :disabled="working.has(i.id)"
            @click="act(i, () => skipItem(i.id), '已略過')"
          >
            略過
          </button>
        </div>
      </article>
    </TransitionGroup>

    <SearchDialog v-if="searching" :item="searching" @close="searching = null" @pick="pick(searching!, $event)" />
  </section>
</template>

<style scoped>
.organize {
  max-width: 72rem;
  margin: 0 auto;
}

.head {
  display: flex;
  align-items: flex-end;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.head h2 {
  margin: 0;
}

.sub {
  margin: 0.25rem 0 0;
  font-size: 0.9rem;
}

.count {
  background: var(--surface-3);
  border-radius: 999px;
  padding: 0 0.45rem;
  font-size: 0.78rem;
}

.progress {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.progress .bar {
  flex-basis: 100%;
  height: 4px;
  background: var(--surface-3);
  border-radius: 4px;
  overflow: hidden;
}

.progress .bar div {
  height: 100%;
  background: var(--info);
  transition: width 0.3s;
}

.watch {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  font-size: 0.86rem;
  margin-bottom: 1rem;
}

.dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: var(--muted);
}

.dot.on {
  background: var(--ok);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 25%, transparent);
}

.dot.bad {
  background: var(--danger);
}

.filters {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.chips {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  flex: 1;
}

.chips button {
  all: unset;
  cursor: pointer;
  padding: 0.3rem 0.8rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 0.88rem;
  display: inline-flex;
  gap: 0.35rem;
  align-items: center;
}

.chips button:focus-visible {
  outline: 2px solid var(--accent);
}

.chips button.on {
  background: var(--text);
  color: var(--bg);
  border-color: var(--text);
}

.chips .n {
  opacity: 0.65;
  font-size: 0.8rem;
}

.chips .warn:not(.on) .n {
  color: var(--warn);
  opacity: 1;
  font-weight: 700;
}

.chips .danger:not(.on) .n {
  color: var(--danger);
  opacity: 1;
  font-weight: 700;
}

.find {
  width: 16rem;
  max-width: 100%;
}

.list {
  display: grid;
  gap: 0.6rem;
}

.item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'top top'
    'main actions';
  gap: 0.5rem 1rem;
  padding: 0.9rem 1.1rem;
  margin: 0;
  transition: opacity 0.2s;
}

.item + .item {
  margin-top: 0;
}

.item.busy {
  opacity: 0.6;
}

.item .top {
  grid-area: top;
  display: flex;
  gap: 0.35rem;
  align-items: center;
}

.main {
  grid-area: main;
  min-width: 0;
  display: grid;
  gap: 0.35rem;
}

.file {
  display: grid;
}

.dir {
  font-size: 0.8rem;
}

.match {
  display: flex;
  gap: 0.5rem;
  font-size: 0.92rem;
}

.arrow {
  color: var(--accent);
  font-weight: 700;
}

.target {
  font-size: 0.8rem;
  font-family: ui-monospace, Menlo, monospace;
}

.msg {
  margin: 0;
  font-size: 0.86rem;
}

.cands {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  align-items: center;
}

.cand {
  all: unset;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.6rem 0.25rem 0.25rem;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  border: 1px solid var(--border);
  font-size: 0.85rem;
}

.cand:hover:not(:disabled),
.cand:focus-visible {
  border-color: var(--accent);
}

.cand img {
  width: 1.6rem;
  height: 2.4rem;
  object-fit: cover;
  border-radius: 3px;
}

.actions {
  grid-area: actions;
  display: flex;
  gap: 0.4rem;
  align-items: flex-start;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.sm-select {
  width: auto;
  min-height: 1.85rem;
  padding: 0 0.5rem;
  font-size: 0.84rem;
}

.ph {
  height: 6rem;
  border-radius: var(--radius);
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
}

.list-enter-active,
.list-leave-active {
  transition: opacity 0.2s;
}

@media (max-width: 44rem) {
  .item {
    grid-template-columns: 1fr;
    grid-template-areas:
      'top'
      'main'
      'actions';
  }

  .actions {
    justify-content: flex-start;
  }

  .find {
    width: 100%;
  }
}
</style>
