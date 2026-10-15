<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createRule,
  deleteRule,
  getNaming,
  listRules,
  previewPath,
  saveNaming,
  updateRule,
  type Naming,
  type Preview,
  type Rule,
  type RuleInput,
} from '../api'

const rules = ref<Rule[]>([])
const naming = reactive<Naming>({ movie_template: '', tv_template: '' })
const draft = reactive<RuleInput>({
  name: '',
  pattern: '',
  priority: 100,
  enabled: true,
  media_type: null,
})
const sample = ref('')
const preview = ref<Preview | null>(null)
const message = ref('')

async function run(action: () => Promise<void>, ok = '') {
  try {
    await action()
    message.value = ok
  } catch (err) {
    message.value = (err as Error).message
  }
}

const reload = async () => (rules.value = await listRules())

onMounted(async () => {
  Object.assign(naming, await getNaming())
  await reload()
})

const add = () =>
  run(async () => {
    await createRule({ ...draft })
    draft.name = ''
    draft.pattern = ''
    await reload()
  }, '規則已新增')

const save = (r: Rule) =>
  run(async () => {
    await updateRule(r.id, r)
    await reload()
  }, '規則已更新')

const remove = (r: Rule) =>
  run(async () => {
    await deleteRule(r.id)
    await reload()
  }, '規則已刪除')

const submitNaming = () =>
  run(async () => {
    Object.assign(naming, await saveNaming({ ...naming }))
  }, '樣板已儲存')

const test = () =>
  run(async () => {
    preview.value = await previewPath(sample.value)
  })
</script>

<template>
  <section class="rules">
    <h2>辨識規則與命名</h2>

    <form @submit.prevent="submitNaming">
      <label>
        電影樣板
        <input v-model="naming.movie_template" />
      </label>
      <label>
        影集樣板
        <input v-model="naming.tv_template" />
      </label>
      <small>
        可用欄位：title、original_title、year、season、episode、episode_title、
        resolution、source、codec、group、tmdb_id
      </small>
      <button type="submit">儲存樣板</button>
    </form>

    <h3>自訂正則</h3>
    <small>
      命名群組：title、year、season、episode、resolution、source、codec、group
    </small>
    <table>
      <thead>
        <tr>
          <th>名稱</th>
          <th>正則</th>
          <th>優先</th>
          <th>類型</th>
          <th>啟用</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rules" :key="r.id">
          <td><input v-model="r.name" /></td>
          <td><input v-model="r.pattern" class="wide" /></td>
          <td><input v-model.number="r.priority" type="number" class="num" /></td>
          <td>
            <select v-model="r.media_type">
              <option :value="null">自動</option>
              <option value="movie">電影</option>
              <option value="tv">影集</option>
            </select>
          </td>
          <td><input v-model="r.enabled" type="checkbox" /></td>
          <td>
            <button type="button" @click="save(r)">更新</button>
            <button type="button" @click="remove(r)">刪除</button>
          </td>
        </tr>
        <tr>
          <td><input v-model="draft.name" placeholder="新規則" /></td>
          <td>
            <input
              v-model="draft.pattern"
              class="wide"
              placeholder="^(?P<title>.+?) EP(?P<episode>\d+)"
            />
          </td>
          <td><input v-model.number="draft.priority" type="number" class="num" /></td>
          <td>
            <select v-model="draft.media_type">
              <option :value="null">自動</option>
              <option value="movie">電影</option>
              <option value="tv">影集</option>
            </select>
          </td>
          <td><input v-model="draft.enabled" type="checkbox" /></td>
          <td><button type="button" @click="add">新增</button></td>
        </tr>
      </tbody>
    </table>

    <h3>預覽</h3>
    <form class="row" @submit.prevent="test">
      <input v-model="sample" placeholder="貼上檔名或相對路徑" />
      <button type="submit">測試</button>
    </form>
    <div v-if="preview">
      <p>命中規則：{{ preview.rule ?? '內建解析' }}</p>
      <p v-if="preview.target">目標：{{ preview.target }}</p>
      <p v-if="preview.error" class="warn">{{ preview.error }}</p>
      <pre>{{ preview.parsed }}</pre>
    </div>

    <p>{{ message }}</p>
  </section>
</template>

<style scoped>
.rules {
  max-width: 64rem;
  margin-top: 2rem;
}

form {
  display: grid;
  gap: 0.75rem;
  max-width: 40rem;
}

.row {
  grid-template-columns: 1fr auto;
}

label {
  display: grid;
  gap: 0.25rem;
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

.wide {
  width: 100%;
}

.num {
  width: 4rem;
}
</style>
