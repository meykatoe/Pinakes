<script setup lang="ts">
import { onMounted, ref } from 'vue'

const status = ref('檢查中')

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    status.value = res.ok ? '後端正常' : '後端異常'
  } catch {
    status.value = '無法連線後端'
  }
})
</script>

<template>
  <main class="home">
    <h1>Pinakes</h1>
    <p>{{ status }}</p>
  </main>
</template>

<style scoped>
.home {
  padding: 2rem;
}
</style>
