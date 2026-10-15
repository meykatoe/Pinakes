<script setup lang="ts">
import type { MediaEntry } from '../api'

defineProps<{ entry: MediaEntry }>()
defineEmits<{ select: [entry: MediaEntry] }>()
</script>

<template>
  <button class="poster" type="button" :title="entry.title" @click="$emit('select', entry)">
    <div class="frame">
      <img v-if="entry.poster_url" :src="entry.poster_url" :alt="entry.title" loading="lazy" />
      <div v-else class="blank">{{ entry.title }}</div>
      <span v-if="entry.rating" class="rating">★ {{ entry.rating.toFixed(1) }}</span>
      <span v-if="entry.media_type === 'tv'" class="kind">{{ entry.file_count }} 集</span>
    </div>
    <div class="meta">
      <strong>{{ entry.title }}</strong>
      <span>{{ entry.year ?? '' }}</span>
    </div>
  </button>
</template>

<style scoped>
.poster {
  all: unset;
  box-sizing: border-box;
  display: grid;
  gap: 0.45rem;
  cursor: pointer;
  min-width: 0;
}

.frame {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: 0.55rem;
  overflow: hidden;
  background: var(--surface-2);
  box-shadow: 0 4px 14px rgb(0 0 0 / 0.25);
  transition: transform 0.2s, box-shadow 0.2s;
}

img,
.blank {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.blank {
  display: grid;
  place-items: center;
  padding: 0.75rem;
  text-align: center;
  font-weight: 600;
  color: var(--muted);
  background: linear-gradient(160deg, var(--surface-3), var(--surface-2));
}

.rating,
.kind {
  position: absolute;
  top: 0.4rem;
  padding: 0.05rem 0.4rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 700;
  background: rgb(0 0 0 / 0.65);
  color: #fff;
  backdrop-filter: blur(4px);
}

.rating {
  left: 0.4rem;
  color: #ffd166;
}

.kind {
  right: 0.4rem;
}

.poster:hover .frame,
.poster:focus-visible .frame {
  transform: translateY(-4px);
  box-shadow: 0 10px 24px rgb(0 0 0 / 0.4);
}

.poster:focus-visible .frame {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.meta {
  display: grid;
  font-size: 0.85rem;
  line-height: 1.35;
}

.meta strong {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-weight: 600;
}

.meta span {
  color: var(--muted);
  font-size: 0.8rem;
}
</style>
