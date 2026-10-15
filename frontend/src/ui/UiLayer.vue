<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { answer, pending } from './confirm'
import { dismiss, toasts } from './toast'

const okBtn = ref<HTMLButtonElement | null>(null)

watch(
  () => pending.current,
  async (v) => {
    if (v) {
      await nextTick()
      okBtn.value?.focus()
    }
  },
)

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    answer(false)
  }
}
</script>

<template>
  <div class="toasts" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="t.kind"
        role="status"
        @click="dismiss(t.id)"
      >
        {{ t.text }}
      </div>
    </TransitionGroup>
  </div>

  <div v-if="pending.current" class="confirm-overlay" @click.self="answer(false)" @keydown="onKey">
    <div class="confirm card" role="alertdialog" aria-modal="true">
      <p>{{ pending.current.text }}</p>
      <div class="row end">
        <button type="button" class="btn" @click="answer(false)">取消</button>
        <button
          ref="okBtn"
          type="button"
          class="btn"
          :class="pending.current.danger ? 'danger' : 'primary'"
          @click="answer(true)"
        >
          {{ pending.current.ok }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 100;
  display: grid;
  gap: 0.5rem;
  max-width: min(26rem, calc(100vw - 2rem));
}

.toast {
  padding: 0.7rem 1rem;
  border-radius: var(--radius-sm);
  background: var(--surface-3);
  border-left: 4px solid var(--ok);
  box-shadow: var(--shadow);
  font-size: 0.9rem;
  cursor: pointer;
  word-break: break-word;
}

.toast.error {
  border-left-color: var(--danger);
}

.toast.info {
  border-left-color: var(--info);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(0.5rem);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.2s;
}

.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 0.55);
  padding: 1rem;
}

.confirm {
  width: min(26rem, 100%);
  box-shadow: var(--shadow);
}

.confirm p {
  margin: 0 0 1.25rem;
  white-space: pre-line;
}

.end {
  justify-content: flex-end;
}
</style>
