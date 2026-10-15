<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createPlayer,
  deletePlayer,
  getTranscodeStatus,
  listPlayers,
  regenerateToken,
  updatePlayer,
  type Player,
  type PlayerInput,
} from '../api'
import { confirm } from '../ui/confirm'
import { toast, toastError } from '../ui/toast'

const players = ref<Player[]>([])
const original = ref<Record<number, string>>({})
const ffmpeg = ref<{ available: boolean; ffmpeg: string | null } | null>(null)
const draft = reactive<PlayerInput>({
  name: '',
  kind: 'link',
  template: '',
  enabled: true,
})

const snap = (p: Player) => JSON.stringify([p.name, p.kind, p.template, p.enabled])

async function reload() {
  players.value = await listPlayers()
  original.value = Object.fromEntries(players.value.map((p) => [p.id, snap(p)]))
}

async function run(action: () => Promise<void>, ok: string) {
  try {
    await action()
    toast(ok)
  } catch (err) {
    toastError(err)
  }
}

onMounted(() => {
  reload().catch(toastError)
  getTranscodeStatus()
    .then((r) => (ffmpeg.value = r))
    .catch(() => undefined)
})

const add = () =>
  run(async () => {
    await createPlayer({ ...draft })
    draft.name = ''
    draft.template = ''
    await reload()
  }, '播放器已新增')

const save = (p: Player) =>
  run(async () => {
    await updatePlayer(p.id, p)
    await reload()
  }, '播放器已更新')

async function remove(p: Player) {
  if (!(await confirm(`刪除播放器「${p.name}」？`, '刪除', true))) return
  await run(async () => {
    await deletePlayer(p.id)
    await reload()
  }, '播放器已刪除')
}

async function renewToken() {
  const ok = await confirm('重新產生後，先前複製或下載的串流連結都會失效。', '重新產生', true)
  if (!ok) return
  await run(async () => void (await regenerateToken()), '已重新產生串流權杖')
}
</script>

<template>
  <section class="card">
    <div class="card-head">
      <h2>內建播放器</h2>
      <span v-if="ffmpeg?.available" class="badge ok">可用</span>
      <span v-else-if="ffmpeg" class="badge danger">找不到 ffmpeg</span>
    </div>
    <p class="hint">
      瀏覽器能直接播放的檔案（H.264 MP4、WebM）會直接串流；其他格式會用 ffmpeg 即時轉封裝或轉碼。
      <template v-if="ffmpeg?.ffmpeg">目前使用 <code>{{ ffmpeg.ffmpeg }}</code></template>
      <template v-else-if="ffmpeg">請安裝 ffmpeg 或在上方指定路徑。</template>
    </p>
  </section>

  <section class="card">
    <div class="card-head"><h2>外部播放器</h2></div>
    <p class="hint intro">
      樣板可用 <code>{url}</code>（串流網址）、<code>{url_encoded}</code>（編碼後的網址）、<code>{filename}</code>。
      PotPlayer 安裝後會註冊 potplayer://；VLC 需額外安裝協定註冊工具；手機可用 m3u 清單。
    </p>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>名稱</th>
            <th>類型</th>
            <th>連結樣板</th>
            <th>啟用</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in players" :key="p.id">
            <td><input v-model="p.name" class="input" /></td>
            <td>
              <select v-model="p.kind" class="input">
                <option value="link">協定連結</option>
                <option value="m3u">m3u 清單</option>
              </select>
            </td>
            <td class="wide">
              <input
                v-model="p.template"
                class="input mono"
                :disabled="p.kind === 'm3u'"
                :placeholder="p.kind === 'm3u' ? '不需要樣板' : ''"
              />
            </td>
            <td><input v-model="p.enabled" type="checkbox" class="toggle" /></td>
            <td class="actions">
              <button type="button" class="btn sm" :disabled="snap(p) === original[p.id]" @click="save(p)">
                儲存
              </button>
              <button type="button" class="btn sm danger" @click="remove(p)">刪除</button>
            </td>
          </tr>
          <tr>
            <td><input v-model="draft.name" class="input" placeholder="新播放器" /></td>
            <td>
              <select v-model="draft.kind" class="input">
                <option value="link">協定連結</option>
                <option value="m3u">m3u 清單</option>
              </select>
            </td>
            <td class="wide">
              <input
                v-model="draft.template"
                class="input mono"
                placeholder="myplayer://{url_encoded}"
                :disabled="draft.kind === 'm3u'"
              />
            </td>
            <td><input v-model="draft.enabled" type="checkbox" class="toggle" /></td>
            <td class="actions">
              <button
                type="button"
                class="btn sm primary"
                :disabled="!draft.name.trim() || (draft.kind === 'link' && !draft.template.trim())"
                @click="add"
              >
                新增
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="row token">
      <button type="button" class="btn sm danger" @click="renewToken">重新產生串流權杖</button>
      <span class="hint">串流網址帶有權杖，外流時可重新產生讓舊連結失效</span>
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

.wide {
  min-width: 14rem;
  width: 45%;
}

td:nth-child(2) {
  width: 8rem;
}

.toggle {
  accent-color: var(--accent);
  width: 1rem;
  height: 1rem;
}

.token {
  margin-top: 1rem;
}
</style>
