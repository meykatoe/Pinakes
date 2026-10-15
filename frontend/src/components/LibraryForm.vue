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

const paths = reactive({ inbox_path: '', library_path: '' })
const sameDevice = ref<boolean | null>(null)
const categories = ref<Category[]>([])
const draft = reactive<CategoryInput>({ name: '', media_type: 'movie', subdir: '' })
const message = ref('')

function applyPaths(data: Paths) {
  paths.inbox_path = data.inbox_path
  paths.library_path = data.library_path
  sameDevice.value = data.same_device
}

async function run(action: () => Promise<void>, ok = '') {
  try {
    await action()
    message.value = ok
  } catch (err) {
    message.value = (err as Error).message
  }
}

async function reload() {
  categories.value = await listCategories()
}

onMounted(async () => {
  applyPaths(await getPaths())
  await reload()
})

const submitPaths = () =>
  run(async () => applyPaths(await savePaths({ ...paths })), '路徑已儲存')

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

const remove = (c: Category) =>
  run(async () => {
    await deleteCategory(c.id)
    await reload()
  }, '分類已刪除')
</script>

<template>
  <section class="library">
    <h2>媒體庫</h2>

    <form @submit.prevent="submitPaths">
      <label>
        待整理目錄
        <input v-model="paths.inbox_path" placeholder="/mnt/d/downloads" />
      </label>
      <label>
        已整理目錄
        <input v-model="paths.library_path" placeholder="/mnt/d/media" />
      </label>
      <p v-if="sameDevice === false" class="warn">
        兩個目錄不在同一磁碟，無法使用硬連結。
      </p>
      <button type="submit">儲存路徑</button>
    </form>

    <h3>分類</h3>
    <table>
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
          <td><input v-model="c.name" /></td>
          <td>
            <select v-model="c.media_type" :disabled="c.builtin">
              <option value="movie">電影</option>
              <option value="tv">影集</option>
            </select>
          </td>
          <td><input v-model="c.subdir" /></td>
          <td>
            <button type="button" @click="save(c)">更新</button>
            <button type="button" :disabled="c.builtin" @click="remove(c)">
              刪除
            </button>
          </td>
        </tr>
        <tr>
          <td><input v-model="draft.name" placeholder="新分類" /></td>
          <td>
            <select v-model="draft.media_type">
              <option value="movie">電影</option>
              <option value="tv">影集</option>
            </select>
          </td>
          <td><input v-model="draft.subdir" placeholder="子目錄" /></td>
          <td><button type="button" @click="add">新增</button></td>
        </tr>
      </tbody>
    </table>

    <p>{{ message }}</p>
  </section>
</template>

<style scoped>
.library {
  max-width: 48rem;
  margin-top: 2rem;
}

form {
  display: grid;
  gap: 0.75rem;
  max-width: 32rem;
}

label {
  display: grid;
  gap: 0.25rem;
}

.warn {
  color: #b45309;
  margin: 0;
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
