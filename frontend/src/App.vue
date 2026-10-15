<script setup lang="ts">
import LibraryForm from './components/LibraryForm.vue'
import RulesForm from './components/RulesForm.vue'
import SettingsForm from './components/SettingsForm.vue'
</script>

<template>
  <main class="home">
    <h1>Pinakes</h1>
    <SettingsForm />
    <LibraryForm />
    <RulesForm />
  </main>
</template>

<style scoped>
.home {
  padding: 2rem;
}
</style>
