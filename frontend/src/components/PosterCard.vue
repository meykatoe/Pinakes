<script setup lang="ts">
import type { MediaEntry } from '../api'

defineProps<{ entry: MediaEntry }>()
defineEmits<{ select: [entry: MediaEntry] }>()
</script>

<template>
  <button class="card" type="button" @click="$emit('select', entry)">
    <img v-if="entry.poster_url" :src="entry.poster_url" :alt="entry.title" loading="lazy" />
    <div v-else class="blank">{{ entry.title }}</div>
    <div class="meta">
      <strong>{{ entry.title }}</strong>
      <span>
        {{ entry.year ?? '' }}
        <template v-if="entry.rating"> · ★ {{ entry.rating }}</template>
      </span>
    </div>
  </button>
</template>

<style scoped>
.card {
  all: unset;
  box-sizing: border-box;
  flex: 0 0 9.5rem;
  cursor: pointer;
  display: grid;
  gap: 0.4rem;
}

img,
.blank {
  width: 100%;
  aspect-ratio: 2 / 3;
  border-radius: 0.5rem;
  object-fit: cover;
  background: color-mix(in srgb, currentColor 12%, transparent);
  transition: transform 0.15s;
}

.blank {
  display: grid;
  place-items: center;
  padding: 0.5rem;
  text-align: center;
  box-sizing: border-box;
}

.card:hover img,
.card:hover .blank,
.card:focus-visible img,
.card:focus-visible .blank {
  transform: scale(1.04);
}

.card:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}

.meta {
  display: grid;
  font-size: 0.85rem;
}

.meta strong {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.meta span {
  opacity: 0.7;
}
</style>
