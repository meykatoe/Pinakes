<script setup lang="ts">
import LibraryForm from './components/LibraryForm.vue'
import MatchPreview from './components/MatchPreview.vue'
import OrganizePanel from './components/OrganizePanel.vue'
import RulesForm from './components/RulesForm.vue'
import SettingsForm from './components/SettingsForm.vue'
</script>

<template>
  <main class="home">
    <h1>Pinakes</h1>
    <SettingsForm />
    <LibraryForm />
    <RulesForm />
    <MatchPreview />
    <OrganizePanel />
  </main>
</template>

<style scoped>
.home {
  padding: 2rem;
}
</style>
