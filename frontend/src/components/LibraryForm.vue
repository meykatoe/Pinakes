<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createCategory,
  deleteCategory,
  getPaths,
  listCategories,
  savePaths,
  updateCategory,
  type Category,
  type CategoryInput,
  type Paths,
} from '../api'
import { confirm } from '../ui/confirm'
import DirPicker from './DirPicker.vue'
import { toast, toastError } from '../ui/toast'

const paths = reactive({ inbox_path: '', library_path: '' })
const saved = ref<Paths | null>(null)
const categories = ref<Category[]>([])
const original = ref<Record<number, string>>({})
const draft = reactive<CategoryInput>({ name: '', media_type: 'movie', subdir: '' })
const savingPaths = ref(false)

function applyPaths(data: Paths) {
  saved.value = data
  paths.inbox_path = data.inbox_path
  paths.library_path = data.library_path
}

const snap = (c: Category) => JSON.stringify([c.name, c.media_type, c.subdir])

async function reload() {
  categories.value = await listCategories()
  original.value = Object.fromEntries(categories.value.map((c) => [c.id, snap(c)]))
}

onMounted(async () => {
  try {
    applyPaths(await getPaths())
    await reload()
  } catch (err) {
    toastError(err)
  }
})

async function run(action: () => Promise<void>, ok: string) {
  try {
    await action()
    toast(ok)
  } catch (err) {
    toastError(err)
  }
}

async function submitPaths() {
  savingPaths.value = true
  await run(async () => applyPaths(await savePaths({ ...paths })), '目錄已儲存')
  savingPaths.value = false
}

const add = () =>
  run(async () => {
    await createCategory({ ...draft })
    draft.name = ''
    draft.subdir = ''
    await reload()
  }, '分類已新增')

const save = (c: Category) =>
  run(async () => {
    await updateCategory(c.id, c)
    await reload()
  }, '分類已更新')

async function remove(c: Category) {
  if (!(await confirm(`刪除分類「${c.name}」？已整理的檔案不會被移動。`, '刪除', true))) return
  await run(async () => {
    await deleteCategory(c.id)
    await reload()
  }, '分類已刪除')
}
</script>

<template>
  <section class="card">
    <div class="card-head"><h2>媒體庫目錄</h2></div>
    <form class="form-grid" @submit.prevent="submitPaths">
      <div class="field">
        <span>待整理目錄</span>
        <DirPicker v-model="paths.inbox_path" placeholder="/downloads" />
        <p class="hint">下載完成的檔案所在，Pinakes 只會讀取這裡</p>
      </div>
      <div class="field">
        <span>已整理目錄</span>
        <DirPicker v-model="paths.library_path" placeholder="/media" />
        <p class="hint">整理後的檔案會依分類放到這裡</p>
      </div>
      <p v-if="saved?.same_device === false" class="notice full">
        兩個目錄不在同一磁碟，無法使用硬連結，請改用移動或複製模式。
      </p>
      <div class="full row">
        <button
          type="submit"
          class="btn primary"
          :disabled="savingPaths ||
            (paths.inbox_path === saved?.inbox_path && paths.library_path === saved?.library_path)"
        >
          儲存目錄
        </button>
      </div>
    </form>
  </section>

  <section class="card">
    <div class="card-head"><h2>分類</h2></div>
    <p class="hint intro">每個分類對應已整理目錄下的一個子目錄，海報牆也會依分類分列。</p>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>名稱</th>
            <th>類型</th>
            <th>子目錄</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in categories" :key="c.id">
            <td><input v-model="c.name" class="input" /></td>
            <td>
              <select v-model="c.media_type" class="input" :disabled="c.builtin">
                <option value="movie">電影</option>
                <option value="tv">影集</option>
              </select>
            </td>
            <td><input v-model="c.subdir" class="input mono" /></td>
            <td class="actions">
              <button
                type="button"
                class="btn sm"
                :disabled="snap(c) === original[c.id]"
                @click="save(c)"
              >
                儲存
              </button>
              <button
                type="button"
                class="btn sm danger"
                :disabled="c.builtin"
                :title="c.builtin ? '內建分類不可刪除' : ''"
                @click="remove(c)"
              >
                刪除
              </button>
            </td>
          </tr>
          <tr class="new">
            <td><input v-model="draft.name" class="input" placeholder="例如：動畫" /></td>
            <td>
              <select v-model="draft.media_type" class="input">
                <option value="movie">電影</option>
                <option value="tv">影集</option>
              </select>
            </td>
            <td><input v-model="draft.subdir" class="input mono" placeholder="子目錄" /></td>
            <td class="actions">
              <button
                type="button"
                class="btn sm primary"
                :disabled="!draft.name.trim() || !draft.subdir.trim()"
                @click="add"
              >
                新增
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.card {
  margin-bottom: 1rem;
}

.card + .card {
  margin-top: 0;
}

.intro {
  margin: -0.5rem 0 0.75rem;
}

td:nth-child(2) {
  width: 7rem;
}
</style>
