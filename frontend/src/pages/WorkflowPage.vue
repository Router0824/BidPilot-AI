<template>
  <div class="wf-page">
    <h2>Agent 任务中心</h2>

    <div v-if="wf?.has_active_workflow" class="status-card">
      <div class="status-row">
        <span>工作流状态</span>
        <span :class="['badge', wf.workflow_status]">{{ statusLabel(wf.workflow_status) }}</span>
      </div>
      <div class="status-row">
        <span>当前节点</span>
        <span class="current-node">{{ wf.current_node }}</span>
      </div>
      <div class="status-row">
        <span>定义版本</span>
        <span>{{ wf.definition_key }} v{{ wf.definition_version }}</span>
      </div>
      <div class="status-row">
        <span>Token 消耗</span>
        <span>{{ wf.token_usage_total || 0 }} tokens</span>
      </div>
      <div class="status-row">
        <span>估算成本</span>
        <span>{{ wf.estimated_cost ? `¥/ $ ${wf.estimated_cost}` : '-' }}</span>
      </div>
      <div class="wf-actions">
        <button v-if="wf.workflow_status === 'waiting_confirmation'" class="btn-primary" @click="resume">继续执行</button>
        <button v-if="wf.workflow_status === 'failed'" class="btn-primary" @click="retryLast">重试失败节点</button>
        <button class="btn-secondary" @click="cancel">取消工作流</button>
      </div>
    </div>

    <div v-else class="no-wf">
      <p>当前项目没有正在运行的工作流</p>
    </div>

    <div v-if="wf?.node_runs?.length" class="node-section">
      <h3>节点执行记录</h3>
      <div class="node-list">
        <div v-for="n in wf.node_runs" :key="n.id" :class="['node-card', n.status]">
          <div class="node-header">
            <span :class="['node-dot', n.status]"></span>
            <span class="node-name">{{ n.node_name }}</span>
            <span class="node-agent">{{ n.agent_name }}</span>
            <span :class="['node-status-badge', n.status]">{{ n.status }}</span>
          </div>
          <div class="node-details">
            <span v-if="n.model_name">模型: {{ n.model_name }}</span>
            <span v-if="n.token_usage">Token: {{ n.token_usage }}</span>
            <span v-if="n.latency_ms">耗时: {{ n.latency_ms }}ms</span>
            <span v-if="n.retry_count > 0">重试: {{ n.retry_count }}次</span>
          </div>
          <div v-if="n.error_message" class="node-error">{{ n.error_message }}</div>
        </div>
      </div>
    </div>

    <div v-if="progressEvents.length" class="thinking-section">
      <h3>Agent 进度流</h3>
      <div class="thinking-list">
        <div v-for="event in progressEvents" :key="event.id" :class="['thinking-item', phaseClass(event.phase)]">
          <span class="thinking-time">{{ fmtTime(event.created_at) }}</span>
          <div>
            <strong>{{ event.title }}</strong>
            <p>{{ event.detail || event.node_name }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { pushProgress } from '../feedback'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const wf = ref(null)
const progressEvents = ref([])
let source = null

onMounted(async () => {
  try { wf.value = await store.fetchWorkflow(projectId) } catch(e) {}
  source = new EventSource(store.workflowStreamUrl(projectId))
  source.addEventListener('workflow.status.changed', (event) => {
    wf.value = JSON.parse(event.data)
  })
  source.addEventListener('agent.progress', (event) => {
    const payload = JSON.parse(event.data)
    payload.id = `${payload.created_at}-${payload.phase}-${payload.node_name || ''}`
    progressEvents.value.unshift(payload)
    progressEvents.value = progressEvents.value.slice(0, 40)
    pushProgress(payload)
  })
  source.onerror = () => {
    source?.close()
    source = null
  }
})

onUnmounted(() => {
  source?.close()
})

function statusLabel(s) {
  const map = { succeeded: '已完成', running: '运行中', waiting_confirmation: '等待确认', failed: '失败',
    cancelled: '已取消', pending: '待执行', retrying: '重试中' }
  return map[s] || s
}

async function resume() { await store.resumeWorkflow(projectId); wf.value = await store.fetchWorkflow(projectId) }
async function cancel() { await store.cancelWorkflow(projectId); wf.value = await store.fetchWorkflow(projectId) }
async function retryLast() {
  const lastNode = wf.value?.node_runs?.slice(-1)[0]
  if (lastNode) {
    await store.startWorkflow(projectId, [])
    wf.value = await store.fetchWorkflow(projectId)
  }
}

function fmtTime(value) {
  return value ? new Date(value).toLocaleTimeString('zh-CN') : ''
}

function phaseClass(phase = '') {
  if (phase.includes('error')) return 'error'
  if (phase.includes('done') || phase.includes('response')) return 'done'
  if (phase.includes('llm')) return 'llm'
  return 'running'
}
</script>

<style scoped>
.wf-page { max-width: 1000px; }
h2 { margin: 0 0 20px; color: #1a1a2e; }
.status-card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.status-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 14px; color: #555; }
.badge { font-size: 12px; padding: 3px 10px; border-radius: 10px; }
.badge.running { background: #cce5ff; color: #004085; }
.badge.waiting_confirmation { background: #fff3cd; color: #856404; }
.badge.succeeded { background: #d4edda; color: #155724; }
.badge.failed { background: #f8d7da; color: #721c24; }
.current-node { font-weight: 600; color: #0f3460; }
.wf-actions { display: flex; gap: 10px; margin-top: 12px; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary { padding: 10px 20px; background: #eee; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.no-wf { text-align: center; padding: 60px; color: #999; }
.node-section h3 { margin: 0 0 12px; font-size: 16px; color: #1a1a2e; }
.node-list { display: flex; flex-direction: column; gap: 10px; }
.node-card { background: white; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #ddd; }
.node-card.succeeded { border-left-color: #27ae60; }
.node-card.failed { border-left-color: #e74c3c; }
.node-card.running { border-left-color: #3498db; }
.node-card.waiting_confirmation { border-left-color: #f39c12; }
.node-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.node-dot { width: 10px; height: 10px; border-radius: 50%; }
.node-dot.succeeded { background: #27ae60; }
.node-dot.failed { background: #e74c3c; }
.node-dot.running { background: #3498db; animation: pulse 1s infinite; }
.node-dot.pending { background: #ccc; }
.node-dot.waiting_confirmation { background: #f39c12; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.node-name { font-weight: 500; font-size: 14px; color: #333; }
.node-agent { font-size: 12px; color: #999; }
.node-status-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: auto; }
.node-status-badge.succeeded { background: #d4edda; color: #155724; }
.node-status-badge.failed { background: #f8d7da; color: #721c24; }
.node-status-badge.running { background: #cce5ff; color: #004085; }
.node-details { display: flex; gap: 16px; font-size: 12px; color: #888; }
.node-error { margin-top: 6px; font-size: 12px; color: #e74c3c; padding: 6px; background: #fff5f5; border-radius: 4px; }
.thinking-section { margin-top: 20px; }
.thinking-section h3 { margin: 0 0 12px; font-size: 16px; color: #1a1a2e; }
.thinking-list { background: white; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }
.thinking-item { display: grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 12px 14px; border-left: 4px solid #3498db; border-bottom: 1px solid #f3f4f6; }
.thinking-item.done { border-left-color: #27ae60; }
.thinking-item.llm { border-left-color: #8e44ad; }
.thinking-item.error { border-left-color: #e74c3c; background: #fff7f7; }
.thinking-time { font-size: 12px; color: #999; }
.thinking-item strong { display: block; font-size: 14px; color: #333; }
.thinking-item p { margin: 3px 0 0; font-size: 12px; color: #777; }
</style>
