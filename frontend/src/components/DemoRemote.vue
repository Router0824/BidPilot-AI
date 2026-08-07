<template>
  <aside class="demo-remote">
    <div class="remote-top">
      <div>
        <span>Demo Remote</span>
        <strong>{{ currentStep.no }} · {{ currentStep.title }}</strong>
      </div>
      <button class="icon-btn" @click="resetTimer" title="重置 90 秒计时">↻</button>
    </div>

    <div class="timer">
      <div class="timer-ring" :style="{ '--progress': `${progress}%` }">
        <div class="timer-value">
          <strong>{{ remaining }}</strong>
          <span>SEC</span>
        </div>
      </div>
      <p>{{ currentStep.caption }}</p>
    </div>

    <div class="step-dots">
      <span
        v-for="(step, index) in steps"
        :key="step.key"
        :class="{ active: index === currentIndex, done: index < currentIndex }"
      ></span>
    </div>

    <div class="remote-actions">
      <router-link :to="projectHome" class="remote-btn">项目详情</router-link>
      <router-link v-if="nextStep" :to="nextStep.to" class="remote-btn primary">{{ nextStep.label }}</router-link>
      <router-link :to="projectHome" class="remote-btn danger">退出</router-link>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const now = ref(Date.now())
let timer = null

const projectId = computed(() => route.params.id)
const projectHome = computed(() => `/project/${projectId.value}`)
const steps = computed(() => [
  {
    key: 'planner',
    no: '01',
    title: 'Agent 计划图',
    caption: '讲 Planner 为什么执行、为什么跳过。',
    match: () => route.name === 'Workflow' && route.query.step !== 'impact',
    to: `/project/${projectId.value}/workflow?demo=1&step=planner`,
    label: '看计划图',
  },
  {
    key: 'impact',
    no: '02',
    title: '增量预览',
    caption: '讲补遗影响范围和人工确认。',
    match: () => route.name === 'Workflow' && route.query.step === 'impact',
    to: `/project/${projectId.value}/workflow?demo=1&step=impact`,
    label: '看增量预览',
  },
  {
    key: 'chain',
    no: '03',
    title: '证据链',
    caption: '讲要求、页码、材料、章节的链路。',
    match: () => route.name === 'EvidenceMatrix',
    to: `/project/${projectId.value}/evidence?demo=1&step=chain`,
    label: '看证据链',
  },
  {
    key: 'fixer',
    no: '04',
    title: '审查修正',
    caption: '讲 Reviewer/Fixer 闭环和高风险拦截。',
    match: () => route.name === 'Reviews',
    to: `/project/${projectId.value}/reviews?demo=1&step=fixer`,
    label: '看审查修正',
  },
])

const currentIndex = computed(() => {
  const found = steps.value.findIndex(step => step.match())
  return found >= 0 ? found : 0
})
const currentStep = computed(() => steps.value[currentIndex.value])
const nextStep = computed(() => {
  const next = steps.value[currentIndex.value + 1]
  return next ? { to: next.to, label: next.label } : null
})
const startedAt = computed(() => Number(sessionStorage.getItem('bidpilot_demo_started_at') || now.value))
const elapsed = computed(() => Math.max(0, Math.floor((now.value - startedAt.value) / 1000)))
const remaining = computed(() => Math.max(0, 90 - elapsed.value))
const progress = computed(() => Math.min(100, Math.max(0, (elapsed.value / 90) * 100)))

onMounted(() => {
  ensureTimer()
  timer = window.setInterval(() => { now.value = Date.now() }, 1000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

watch(() => route.fullPath, ensureTimer)

function ensureTimer() {
  if (!sessionStorage.getItem('bidpilot_demo_started_at')) {
    sessionStorage.setItem('bidpilot_demo_started_at', String(Date.now()))
  }
  now.value = Date.now()
}

function resetTimer() {
  sessionStorage.setItem('bidpilot_demo_started_at', String(Date.now()))
  now.value = Date.now()
}
</script>

<style scoped>
.demo-remote {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 40;
  width: min(330px, calc(100vw - 44px));
  padding: 16px;
  border: 1px solid rgba(17,24,39,.14);
  border-radius: 24px;
  background: rgba(255,255,255,.94);
  box-shadow: 0 24px 70px rgba(15,23,42,.2);
  backdrop-filter: blur(24px) saturate(1.1);
}
.remote-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.remote-top span {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
}
.remote-top strong {
  display: block;
  color: #111827;
  font-size: 15px;
}
.icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #dbe3ee;
  border-radius: 50%;
  background: white;
  color: #111827;
  cursor: pointer;
  font-weight: 900;
}
.timer {
  display: grid;
  grid-template-columns: 82px 1fr;
  gap: 14px;
  align-items: center;
  margin-top: 14px;
}
.timer-ring {
  width: 82px;
  height: 82px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background:
    conic-gradient(#111827 var(--progress), #e2e8f0 0),
    #f8fafc;
  color: #111827;
  position: relative;
}
.timer-ring::before {
  content: "";
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: white;
}
.timer-value {
  position: relative;
  z-index: 1;
  display: flex;
  min-width: 48px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transform: translateY(1px);
}
.timer-value strong {
  color: #111827;
  font-variant-numeric: tabular-nums;
  font-size: 25px;
  font-weight: 900;
  line-height: 1;
}
.timer-value span {
  margin-top: 4px;
  color: #64748b;
  font-size: 9px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: .08em;
}
.timer p {
  margin: 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}
.step-dots {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin: 13px 0;
}
.step-dots span {
  height: 5px;
  border-radius: 999px;
  background: #e5e7eb;
}
.step-dots span.done {
  background: #94a3b8;
}
.step-dots span.active {
  background: #111827;
}
.remote-actions {
  display: grid;
  grid-template-columns: 1fr 1fr 64px;
  gap: 8px;
}
.remote-btn {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #dbe3ee;
  border-radius: 999px;
  background: white;
  color: #111827;
  text-decoration: none;
  font-size: 12px;
  font-weight: 900;
}
.remote-btn.primary {
  border-color: #111827;
  background: #111827;
  color: white;
}
.remote-btn.danger {
  color: #b91c1c;
}
@media (max-width: 760px) {
  .demo-remote {
    left: 14px;
    right: 14px;
    bottom: 14px;
    width: auto;
  }
}
</style>
