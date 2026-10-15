<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { changePassword, logout } from '../api'
import { auth } from '../auth'
import { confirm } from '../ui/confirm'
import { toast, toastError } from '../ui/toast'

const form = reactive({ current: '', next: '', again: '' })
const busy = ref(false)
const enabled = computed(() => auth.value?.enabled ?? false)
const mismatch = computed(() => form.again !== '' && form.next !== form.again)

async function submit() {
  busy.value = true
  try {
    auth.value = await changePassword(form.current, form.next)
    toast(enabled.value ? '密碼已更新' : '已停用密碼')
    form.current = form.next = form.again = ''
  } catch (err) {
    toastError(err)
  } finally {
    busy.value = false
  }
}

async function disable() {
  if (!form.current) {
    toast('請先輸入目前密碼', 'error')
    return
  }
  const ok = await confirm('停用後任何能連到這台伺服器的人都能操作 Pinakes。', '停用', true)
  if (!ok) return
  form.next = form.again = ''
  await submit()
}

async function doLogout() {
  await logout().catch(() => undefined)
  if (auth.value) auth.value = { ...auth.value, authenticated: false }
}
</script>

<template>
  <section class="card">
    <div class="card-head">
      <h2>登入密碼</h2>
      <span v-if="enabled" class="badge ok">已啟用</span>
      <span v-else class="badge warn">未設定</span>
    </div>
    <p v-if="!enabled" class="notice intro">
      目前不需登入即可使用。若 Pinakes 可從區網或網際網路連到，強烈建議設定密碼。
    </p>
    <form class="form-grid" @submit.prevent="submit">
      <input type="text" autocomplete="username" value="pinakes" hidden />
      <label v-if="enabled" class="field full">
        <span>目前密碼</span>
        <input v-model="form.current" class="input" type="password" autocomplete="current-password" />
      </label>
      <label class="field">
        <span>{{ enabled ? '新密碼' : '密碼' }}</span>
        <input
          v-model="form.next"
          class="input"
          type="password"
          autocomplete="new-password"
          minlength="6"
          placeholder="至少 6 個字元"
        />
      </label>
      <label class="field">
        <span>再次輸入</span>
        <input v-model="form.again" class="input" type="password" autocomplete="new-password" />
        <p v-if="mismatch" class="hint danger-text">兩次輸入不一致</p>
      </label>
      <div class="full row">
        <button
          type="submit"
          class="btn primary"
          :disabled="busy || form.next.length < 6 || form.next !== form.again || (enabled && !form.current)"
        >
          {{ enabled ? '更新密碼' : '設定密碼' }}
        </button>
        <template v-if="enabled">
          <button type="button" class="btn danger" :disabled="busy" @click="disable">停用密碼</button>
          <span class="spacer"></span>
          <button type="button" class="btn ghost" @click="doLogout">登出</button>
        </template>
      </div>
    </form>
  </section>
</template>

<style scoped>
.intro {
  margin: -0.25rem 0 1rem;
}
</style>
