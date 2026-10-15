<script setup lang="ts">
import { ref } from 'vue'
import { listDirs, type DirListing } from '../api'

const model = defineModel<string>({ required: true })
defineProps<{ placeholder?: string }>()

const open = ref(false)
const listing = ref<DirListing | null>(null)
const error = ref('')
const busy = ref(false)

async function browse(path: string) {
  busy.value = true
  error.value = ''
  try {
    listing.value = await listDirs(path)
  } catch (err) {
    error.value = (err as Error).message
    if (!listing.value) listing.value = await listDirs('').catch(() => null)
  } finally {
    busy.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) browse(model.value)
}

function join(base: string, name: string) {
  return base.endsWith('/') ? base + name : `${base}/${name}`
}

function choose() {
  if (listing.value) model.value = listing.value.path
  open.value = false
}
</script>

<template>
  <div class="picker">
    <div class="line">
      <input v-model="model" class="input mono" :placeholder="placeholder" />
      <button type="button" class="btn" :aria-expanded="open" @click="toggle">瀏覽</button>
    </div>
    <div v-if="open" class="pop">
      <div class="crumb">
        <button
          type="button"
          class="btn sm ghost"
          :disabled="!listing?.parent || busy"
          aria-label="上一層"
          @click="browse(listing!.parent!)"
        >
          ↑ 上一層
        </button>
        <code class="break">{{ listing?.path ?? '…' }}</code>
      </div>
      <p v-if="error" class="danger-text err">{{ error }}</p>
      <ul>
        <li v-for="d in listing?.dirs ?? []" :key="d">
          <button type="button" @click="browse(join(listing!.path, d))">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
            {{ d }}
          </button>
        </li>
        <li v-if="listing && !listing.dirs.length" class="muted none">沒有子目錄</li>
      </ul>
      <div class="foot">
        <button type="button" class="btn sm ghost" @click="open = false">取消</button>
        <button type="button" class="btn sm primary" :disabled="!listing" @click="choose">
          選擇這個目錄
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.picker {
  position: relative;
}

.line {
  display: flex;
  gap: 0.4rem;
}

.pop {
  position: absolute;
  z-index: 15;
  left: 0;
  right: 0;
  top: calc(100% + 0.3rem);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow);
  padding: 0.5rem;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
}

.err {
  margin: 0.4rem 0;
  font-size: 0.85rem;
}

ul {
  list-style: none;
  margin: 0;
  padding: 0.3rem 0;
  max-height: 15rem;
  overflow-y: auto;
}

li button {
  all: unset;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.88rem;
}

li button:hover,
li button:focus-visible {
  background: var(--surface-2);
}

li svg {
  width: 1rem;
  height: 1rem;
  fill: var(--accent);
  flex: none;
}

.none {
  padding: 0.5rem;
  font-size: 0.85rem;
}

.foot {
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--border);
}
</style>
