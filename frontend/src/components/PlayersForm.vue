<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createPlayer,
  deletePlayer,
  listPlayers,
  regenerateToken,
  updatePlayer,
  type Player,
  type PlayerInput,
} from '../api'

const players = ref<Player[]>([])
const draft = reactive<PlayerInput>({
  name: '',
  kind: 'link',
  template: '',
  enabled: true,
})
const message = ref('')

const reload = async () => (players.value = await listPlayers())

async function run(action: () => Promise<void>, ok: string) {
  try {
    await action()
    message.value = ok
  } catch (err) {
    message.value = (err as Error).message
  }
}

onMounted(reload)

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

const remove = (p: Player) =>
  run(async () => {
    await deletePlayer(p.id)
    await reload()
  }, '播放器已刪除')

const renewToken = () =>
  run(async () => {
    await regenerateToken()
  }, '已重新產生權杖，舊的串流連結會失效')
</script>

<template>
  <section class="players">
    <h2>外部播放器</h2>
    <small>
      樣板可用 {url}（串流網址）、{url_encoded}（編碼後的串流網址）、{filename}。
      PotPlayer 安裝後已註冊 potplayer://；VLC 需另外安裝協定註冊工具才會有 vlc://。
    </small>
    <table>
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
          <td><input v-model="p.name" /></td>
          <td>
            <select v-model="p.kind">
              <option value="link">協定連結</option>
              <option value="m3u">m3u 清單</option>
            </select>
          </td>
          <td>
            <input v-model="p.template" class="wide" :disabled="p.kind === 'm3u'" />
          </td>
          <td><input v-model="p.enabled" type="checkbox" /></td>
          <td>
            <button type="button" @click="save(p)">更新</button>
            <button type="button" @click="remove(p)">刪除</button>
          </td>
        </tr>
        <tr>
          <td><input v-model="draft.name" placeholder="新播放器" /></td>
          <td>
            <select v-model="draft.kind">
              <option value="link">協定連結</option>
              <option value="m3u">m3u 清單</option>
            </select>
          </td>
          <td>
            <input
              v-model="draft.template"
              class="wide"
              placeholder="myplayer://{url_encoded}"
              :disabled="draft.kind === 'm3u'"
            />
          </td>
          <td><input v-model="draft.enabled" type="checkbox" /></td>
          <td><button type="button" @click="add">新增</button></td>
        </tr>
      </tbody>
    </table>
    <p>
      <button type="button" @click="renewToken">重新產生串流權杖</button>
      <span>{{ message }}</span>
    </p>
  </section>
</template>

<style scoped>
.players {
  max-width: 64rem;
  margin-top: 2rem;
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
</style>
