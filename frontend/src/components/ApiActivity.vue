<template>
  <div class="api-activity" aria-live="polite">
    <div v-if="state.pending.length || state.progress.length" class="activity-panel">
      <div v-if="state.pending.length" class="pending-row">
        <span class="spinner"></span>
        <div>
          <strong>{{ state.pending[0].label }}</strong>
          <span>{{ elapsed(state.pending[0].startedAt) }}</span>
        </div>
      </div>
      <div v-if="state.progress.length" class="progress-feed">
        <div v-for="item in state.progress.slice(0, 4)" :key="item.id" class="progress-item">
          <span :class="['phase-dot', phaseClass(item.phase)]"></span>
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ item.detail || item.node_name || '' }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="toast-stack">
      <div v-for="m in state.messages" :key="m.id" :class="['toast', m.type]">
        <strong>{{ m.title }}</strong>
        <span v-if="m.detail">{{ m.detail }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { feedbackState } from '../feedback'

const now = ref(Date.now())
const state = computed(() => feedbackState)
let timer = null

onMounted(() => {
  timer = setInterval(() => { now.value = Date.now() }, 500)
})

onUnmounted(() => {
  clearInterval(timer)
})

function elapsed(startedAt) {
  const seconds = Math.max(0, Math.round((now.value - startedAt) / 1000))
  return seconds < 1 ? '刚刚' : `${seconds}s`
}

function phaseClass(phase = '') {
  if (phase.includes('error')) return 'error'
  if (phase.includes('done') || phase.includes('response')) return 'done'
  if (phase.includes('llm')) return 'llm'
  return 'running'
}
</script>

<style scoped>
.api-activity {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 2000;
  width: min(360px, calc(100vw - 32px));
  pointer-events: none;
  text-align: left;
}
.activity-panel {
  background:
    linear-gradient(180deg, rgba(24,32,51,.96), rgba(17,24,39,.96)),
    repeating-linear-gradient(90deg, rgba(255,255,255,.05) 0, rgba(255,255,255,.05) 1px, transparent 1px, transparent 24px);
  color: white;
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(14, 43, 79, 0.28);
  overflow: hidden;
  margin-bottom: 10px;
  backdrop-filter: blur(16px);
}
.pending-row, .progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
}
.pending-row {
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.pending-row strong, .progress-item strong {
  display: block;
  font-size: 13px;
  line-height: 1.3;
}
.pending-row span:not(.spinner), .progress-item span:not(.phase-dot) {
  display: block;
  font-size: 12px;
  color: rgba(255,255,255,0.68);
  margin-top: 2px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.24);
  border-top-color: #f0b35b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex: 0 0 auto;
}
.progress-feed {
  max-height: 190px;
  overflow: hidden;
}
.progress-item {
  padding-top: 8px;
  padding-bottom: 8px;
}
.phase-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #2d9cbd;
  flex: 0 0 auto;
}
.phase-dot.llm { background: #f0b35b; }
.phase-dot.done { background: #80ed99; }
.phase-dot.error { background: #ff8fab; }
.toast-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toast {
  background: rgba(255,255,255,.96);
  color: var(--ink);
  border: 1px solid rgba(184,199,191,.82);
  border-left: 4px solid var(--mint);
  border-radius: 8px;
  box-shadow: var(--shadow-lift);
  padding: 10px 12px;
  backdrop-filter: blur(10px);
}
.toast.error { border-left-color: var(--red); }
.toast strong {
  display: block;
  font-size: 13px;
}
.toast span {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
