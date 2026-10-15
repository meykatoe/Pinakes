<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  chooseItem,
  executeAll,
  executeItem,
  getWatchStatus,
  listItems,
  scan,
  skipItem,
  undoItem,
  type Item,
  type WatchStatus,
} from '../api'

const items = ref<Item[]>([])
const message = ref('')
const busy = ref(false)
const watch = ref<WatchStatus | null>(null)

const statusText: Record<string, string> = {
  pending_review: '待確認',
  planned: '待執行',
  done: '已完成',
  failed: '失敗',
  skipped: '已略過',
  undone: '已還原',
}

async function reload() {
  items.value = await listItems()
  watch.value = await getWatchStatus()
}

async function run(action: () => Promise<string | void>) {
  busy.value = true
  try {
    message.value = (await action()) ?? ''
    await reload()
  } catch (err) {
    message.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

onMounted(reload)

const doScan = () =>
  run(async () => {
    const r = await scan()
    return `新增 ${r.created} 項（待執行 ${r.planned}，待確認 ${r.pending_review}）`
  })

const doExecuteAll = () =>
  run(async () => {
    const r = await executeAll()
    return `完成 ${r.done}，略過 ${r.skipped}，失敗 ${r.failed}`
  })

const act = (fn: () => Promise<unknown>) => run(async () => void (await fn()))
</script>

<template>
  <section class="organize">
    <h2>整理</h2>
    <div class="bar">
      <button :disabled="busy" @click="doScan">掃描待整理目錄</button>
      <button :disabled="busy" @click="doExecuteAll">執行全部待執行項目</button>
      <span>{{ message }}</span>
    </div>

    <p v-if="watch">
      監控：{{ watch.enabled ? '已啟用' : '未啟用' }}，等待穩定 {{ watch.waiting }} 個檔案
      <span v-if="watch.last_error" class="warn">（{{ watch.last_error }}）</span>
    </p>

    <table>
      <thead>
        <tr>
          <th>狀態</th>
          <th>來源</th>
          <th>目標</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in items" :key="i.id">
          <td>{{ statusText[i.status] ?? i.status }}</td>
          <td class="path">{{ i.source_path }}</td>
          <td class="path">
            {{ i.target_path || '尚未確定' }}
            <div v-if="i.error" class="warn">{{ i.error }}</div>
            <div v-else-if="i.reason">{{ i.reason }}</div>
            <div v-if="i.status === 'pending_review'">
              <button
                v-for="c in i.candidates.slice(0, 5)"
                :key="c.tmdb_id"
                @click="act(() => chooseItem(i.id, c.tmdb_id))"
              >
                {{ c.title }} {{ c.year }}
              </button>
            </div>
          </td>
          <td>
            <button
              v-if="i.status === 'planned' || i.status === 'failed'"
              @click="act(() => executeItem(i.id))"
            >
              執行
            </button>
            <button v-if="i.status === 'done'" @click="act(() => undoItem(i.id))">
              還原
            </button>
            <button
              v-if="i.status !== 'done' && i.status !== 'skipped'"
              @click="act(() => skipItem(i.id))"
            >
              略過
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.organize {
  max-width: 72rem;
  margin-top: 2rem;
}

.bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
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
  vertical-align: top;
}

.path {
  word-break: break-all;
}
</style>
