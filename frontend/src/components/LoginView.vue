<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { login } from '../api'
import { auth } from '../auth'

const password = ref('')
const error = ref('')
const busy = ref(false)
const input = ref<HTMLInputElement | null>(null)

onMounted(() => input.value?.focus())

async function submit() {
  busy.value = true
  error.value = ''
  try {
    auth.value = await login(password.value)
  } catch (err) {
    error.value = (err as Error).message
    password.value = ''
    input.value?.focus()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login">
    <form class="card" @submit.prevent="submit">
      <div class="brand">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="4" width="5" height="16" rx="1" />
          <rect x="9.5" y="4" width="5" height="16" rx="1" />
          <rect x="16" y="4" width="5" height="16" rx="1" transform="rotate(8 18.5 12)" />
        </svg>
        <h1>Pinakes</h1>
      </div>
      <label class="field">
        <span>密碼</span>
        <input
          ref="input"
          v-model="password"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <p v-if="error" class="danger-text err">{{ error }}</p>
      <button type="submit" class="btn primary" :disabled="busy || !password">
        <span v-if="busy" class="spin"></span>
        登入
      </button>
      <p class="hint">忘記密碼可在伺服器執行 <code>python -m app.cli reset-password</code></p>
    </form>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1rem;
  background:
    radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 45%),
    var(--bg);
}

form {
  width: min(22rem, 100%);
  display: grid;
  gap: 1rem;
  padding: 2rem;
  box-shadow: var(--shadow);
}

.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
}

.brand svg {
  width: 2rem;
  height: 2rem;
  fill: var(--accent);
}

h1 {
  margin: 0;
  font-size: 1.6rem;
}

.err {
  margin: 0;
  font-size: 0.9rem;
}

.hint {
  text-align: center;
}
</style>
