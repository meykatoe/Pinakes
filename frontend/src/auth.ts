import { ref } from 'vue'
import { getAuthStatus, type AuthStatus } from './api'

export const auth = ref<AuthStatus | null>(null)

export async function refreshAuth() {
  auth.value = await getAuthStatus()
}

window.addEventListener('pinakes:unauthorized', () => {
  if (auth.value) auth.value = { ...auth.value, authenticated: false }
})
