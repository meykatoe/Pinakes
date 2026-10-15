<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
import { confirm } from '../ui/confirm'
import { toast, toastError } from '../ui/toast'

const rules = ref<Rule[]>([])
const original = ref<Record<number, string>>({})
const naming = reactive<Naming>({ movie_template: '', tv_template: '' })
const savedNaming = ref<Naming | null>(null)
const draft = reactive<RuleInput>({
  name: '',
  pattern: '',
  priority: 100,
  enabled: true,
  media_type: null,
})
const sample = ref('')
const preview = ref<Preview | null>(null)

const FIELDS = [
  ['title', '片名'],
  ['original_title', '原文片名'],
  ['year', '年份'],
  ['season', '季'],
  ['episode', '集'],
  ['episode_title', '集標題'],
  ['resolution', '解析度'],
  ['source', '來源'],
  ['codec', '編碼'],
  ['group', '發布組'],
  ['tmdb_id', 'TMDB ID'],
]
const PARSED_LABELS: Record<string, string> = {
  ...Object.fromEntries(FIELDS),
  ext: '副檔名',
  media_type: '類型',
}

const snap = (r: Rule) => JSON.stringify([r.name, r.pattern, r.priority, r.enabled, r.media_type])

async function reload() {
  rules.value = await listRules()
  original.value = Object.fromEntries(rules.value.map((r) => [r.id, snap(r)]))
}

onMounted(async () => {
  try {
    const data = await getNaming()
    Object.assign(naming, data)
    savedNaming.value = data
    await reload()
  } catch (err) {
    toastError(err)
  }
})

async function run(action: () => Promise<void>, ok = '') {
  try {
    await action()
    if (ok) toast(ok)
  } catch (err) {
    toastError(err)
  }
}

const namingDirty = computed(
  () =>
    savedNaming.value !== null &&
    (naming.movie_template !== savedNaming.value.movie_template ||
      naming.tv_template !== savedNaming.value.tv_template),
)

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

async function remove(r: Rule) {
  if (!(await confirm(`刪除規則「${r.name}」？`, '刪除', true))) return
  await run(async () => {
    await deleteRule(r.id)
    await reload()
  }, '規則已刪除')
}

const submitNaming = () =>
  run(async () => {
    const data = await saveNaming({ ...naming })
    Object.assign(naming, data)
    savedNaming.value = data
  }, '樣板已儲存')

type TplKey = 'movie_template' | 'tv_template'
const focused = ref<TplKey>('movie_template')
const inputs: Record<TplKey, HTMLInputElement | null> = {
  movie_template: null,
  tv_template: null,
}

function insert(field: string) {
  const key = focused.value
  const el = inputs[key]
  const text = `{${field}}`
  const pos = el?.selectionStart ?? naming[key].length
  const end = el?.selectionEnd ?? pos
  naming[key] = naming[key].slice(0, pos) + text + naming[key].slice(end)
  requestAnimationFrame(() => {
    el?.focus()
    el?.setSelectionRange(pos + text.length, pos + text.length)
  })
}

const test = () =>
  run(async () => {
    preview.value = await previewPath(sample.value)
  })

const parsedRows = computed(() =>
  Object.entries(preview.value?.parsed ?? {}).filter(([, v]) => v !== null && v !== ''),
)
</script>

<template>
  <section class="card">
    <div class="card-head"><h2>命名樣板</h2></div>
    <p class="hint intro">
      決定整理後的資料夾與檔名，用 / 分隔資料夾。數字可加格式，例如 {season:02} 會補零成 01。
    </p>
    <form class="grid" @submit.prevent="submitNaming">
      <label class="field">
        <span>電影</span>
        <input
          :ref="(el) => (inputs.movie_template = el as HTMLInputElement)"
          v-model="naming.movie_template"
          class="input mono"
          @focus="focused = 'movie_template'"
        />
      </label>
      <label class="field">
        <span>影集</span>
        <input
          :ref="(el) => (inputs.tv_template = el as HTMLInputElement)"
          v-model="naming.tv_template"
          class="input mono"
          @focus="focused = 'tv_template'"
        />
      </label>
      <div class="chips">
        <span class="hint">插入到{{ focused === 'tv_template' ? '影集' : '電影' }}樣板：</span>
        <button
          v-for="[key, label] in FIELDS"
          :key="key"
          type="button"
          class="btn sm ghost chip"
          @mousedown.prevent
          @click="insert(key)"
        >
          {{ label }}
        </button>
      </div>
      <div class="row">
        <button type="submit" class="btn primary" :disabled="!namingDirty">儲存樣板</button>
      </div>
    </form>
  </section>

  <section class="card">
    <div class="card-head"><h2>自訂辨識規則</h2></div>
    <p class="hint intro">
      內建解析辨識不出時，可加入正則表達式，用命名群組擷取欄位，例如
      <code>(?P&lt;title&gt;...)</code>。可用群組：title、year、season、episode、resolution、source、codec、group。
      數字越小越先比對，命中第一條即停止。
    </p>
    <div class="table-wrap">
      <table class="table">
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
            <td><input v-model="r.name" class="input" /></td>
            <td class="wide"><input v-model="r.pattern" class="input mono" /></td>
            <td><input v-model.number="r.priority" type="number" class="input num" /></td>
            <td>
              <select v-model="r.media_type" class="input">
                <option :value="null">自動</option>
                <option value="movie">電影</option>
                <option value="tv">影集</option>
              </select>
            </td>
            <td><input v-model="r.enabled" type="checkbox" class="toggle" /></td>
            <td class="actions">
              <button type="button" class="btn sm" :disabled="snap(r) === original[r.id]" @click="save(r)">
                儲存
              </button>
              <button type="button" class="btn sm danger" @click="remove(r)">刪除</button>
            </td>
          </tr>
          <tr>
            <td><input v-model="draft.name" class="input" placeholder="新規則" /></td>
            <td class="wide">
              <input
                v-model="draft.pattern"
                class="input mono"
                placeholder="^(?P<title>.+?) EP(?P<episode>\d+)"
              />
            </td>
            <td><input v-model.number="draft.priority" type="number" class="input num" /></td>
            <td>
              <select v-model="draft.media_type" class="input">
                <option :value="null">自動</option>
                <option value="movie">電影</option>
                <option value="tv">影集</option>
              </select>
            </td>
            <td><input v-model="draft.enabled" type="checkbox" class="toggle" /></td>
            <td class="actions">
              <button
                type="button"
                class="btn sm primary"
                :disabled="!draft.name.trim() || !draft.pattern.trim()"
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

  <section class="card">
    <div class="card-head"><h2>解析預覽</h2></div>
    <p class="hint intro">只做本地解析，不連線 TMDB，可快速確認規則與樣板。</p>
    <form class="row" @submit.prevent="test">
      <input
        v-model="sample"
        class="input mono grow"
        placeholder="Show.Name.S01E02.1080p.WEB-DL.mkv"
      />
      <button type="submit" class="btn" :disabled="!sample.trim()">解析</button>
    </form>
    <div v-if="preview" class="result">
      <p>
        <span class="muted">命中規則：</span>{{ preview.rule ?? '內建解析' }}
      </p>
      <p v-if="preview.target">
        <span class="muted">整理後：</span><code class="break">{{ preview.target }}</code>
      </p>
      <p v-if="preview.error" class="danger-text">{{ preview.error }}</p>
      <dl class="parsed">
        <template v-for="[k, v] in parsedRows" :key="k">
          <dt>{{ PARSED_LABELS[k] ?? k }}</dt>
          <dd>{{ k === 'media_type' ? (v === 'tv' ? '影集' : '電影') : v }}</dd>
        </template>
      </dl>
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
  margin: -0.5rem 0 1rem;
}

.grid {
  display: grid;
  gap: 0.9rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
}

.chip {
  border: 1px dashed var(--border);
}

.wide {
  min-width: 16rem;
  width: 45%;
}

.num {
  width: 4.5rem;
}

.toggle {
  accent-color: var(--accent);
  width: 1rem;
  height: 1rem;
}

.grow {
  flex: 1;
  min-width: 12rem;
}

.result {
  margin-top: 1rem;
}

.result p {
  margin: 0.3rem 0;
}

.parsed {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.25rem 1rem;
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
}

.parsed dt {
  color: var(--muted);
}

.parsed dd {
  margin: 0;
}
</style>
