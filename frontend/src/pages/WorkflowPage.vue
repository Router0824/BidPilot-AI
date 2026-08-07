<template>
  <div class="wf-page">
    <DemoGuide
      v-if="demoMode"
      :title="demoStep === 'impact' ? '第 2 步：补遗增量重执行预览' : '第 1 步：Planner Agent 自主决策'"
      :body="demoStep === 'impact'
        ? '点击预览补遗影响，展示哪些节点会重跑、哪些历史结果被保留，以及高风险变更为什么需要人工确认。'
        : '先看 Planner 决策图，讲清楚 Agent 为什么选择这些节点、为什么跳过无关节点，以及当前风险等级。'"
      :next-to="demoStep === 'impact'
        ? `/project/${projectId}/evidence?demo=1&step=chain`
        : `/project/${projectId}/workflow?demo=1&step=impact`"
      :next-label="demoStep === 'impact' ? '进入证据链' : '看增量预览'"
      :exit-to="`/project/${projectId}`"
    />

    <section class="stage-hero">
      <div class="hero-copy">
        <span class="eyebrow">AGENT MISSION CONTROL</span>
        <h2>90 秒 Agent 决策主舞台</h2>
        <p>展示 Planner 为什么执行、为什么跳过、补遗影响范围，以及每个节点的实时执行轨迹。</p>
      </div>
      <div class="hero-status">
        <span :class="['stage-pulse', wf?.workflow_status || 'idle']"></span>
        <strong>{{ statusLabel(wf?.workflow_status || 'idle') }}</strong>
        <small>{{ wf?.current_node || '等待启动工作流' }}</small>
      </div>
    </section>

    <section class="command-grid">
      <div class="mission-card">
        <div class="card-title">
          <span>当前任务</span>
          <b>{{ wf?.definition_key || '未启动' }}</b>
        </div>
        <div class="mission-metrics">
          <div><span>节点</span><strong>{{ nodeRuns.length }}</strong></div>
          <div><span>完成</span><strong>{{ countNodeStatus('succeeded') }}</strong></div>
          <div><span>等待</span><strong>{{ countNodeStatus('waiting_confirmation') }}</strong></div>
          <div><span>Token</span><strong>{{ wf?.token_usage_total || 0 }}</strong></div>
        </div>
        <div class="runway">
          <span
            v-for="node in displayRunway"
            :key="node.node_id"
            :class="['runway-dot', nodeStatusFor(node.node_id)]"
            :title="node.node_id"
          ></span>
        </div>
        <div class="wf-actions">
          <button v-if="wf?.workflow_status === 'waiting_confirmation'" class="btn-primary" @click="resume">继续执行</button>
          <button v-if="wf?.workflow_status === 'failed'" class="btn-primary" @click="retryLast">重试失败节点</button>
          <button v-if="wf?.has_active_workflow" class="btn-secondary" @click="cancel">取消工作流</button>
        </div>
        <div v-if="!wf?.has_active_workflow" class="empty-stage">当前项目没有运行中的工作流，可从项目详情启动。</div>
      </div>

      <div class="live-feed-card">
        <div class="card-title">
          <span>实时进度</span>
          <b>{{ progressEvents.length }} events</b>
        </div>
        <div class="mini-feed">
          <div v-if="!progressEvents.length" class="empty-stage">等待 Agent 事件流</div>
          <div v-for="event in progressEvents.slice(0, 5)" :key="event.id" :class="['mini-event', phaseClass(event.phase)]">
            <span></span>
            <div>
              <strong>{{ event.title }}</strong>
              <small>{{ event.detail || event.node_name }}</small>
            </div>
            <em>{{ fmtTime(event.created_at) }}</em>
          </div>
        </div>
      </div>
    </section>

    <div v-if="wf?.planner_plan" :class="['planner-section', { 'demo-focus': demoMode && demoStep !== 'impact' }]">
      <div class="planner-header">
        <div>
          <h3>Planner Agent 决策</h3>
          <p>{{ wf.planner_plan.goal }}</p>
        </div>
        <div class="planner-badges">
          <span :class="['risk-pill', wf.planner_plan.risk_level]">{{ riskLabel(wf.planner_plan.risk_level) }}</span>
          <span v-if="wf.planner_plan.fallback_used" class="fallback-pill">Fallback</span>
        </div>
      </div>

      <div v-if="wf.planner_plan.human_confirmation_required" class="confirmation-callout">
        <strong>需要人工确认</strong>
        <span>{{ wf.planner_plan.confirmation_reason || 'Planner 判断存在高风险变更或待确认事项' }}</span>
      </div>

      <div class="agent-map">
        <div
          v-for="node in wf.planner_plan.selected_nodes"
          :key="node.node_id"
          :class="['map-node', nodeStatusFor(node.node_id), {gate: node.requires_human_confirmation}]"
        >
          <span class="priority">{{ node.priority }}</span>
          <div>
            <strong>{{ node.node_id }}</strong>
            <p>{{ node.reason }}</p>
          </div>
        </div>
      </div>

      <div class="plan-grid">
        <div class="plan-panel compact">
          <h4>本次执行</h4>
          <div v-for="node in wf.planner_plan.selected_nodes" :key="node.node_id" class="plan-node selected">
            <span class="priority">{{ node.priority }}</span>
            <div>
              <strong>
                {{ node.node_id }}
                <span v-if="node.requires_human_confirmation" class="human-gate">人审</span>
              </strong>
              <p>{{ node.reason }}</p>
            </div>
          </div>
        </div>
        <div class="plan-panel compact">
          <h4>本次跳过</h4>
          <div v-if="!wf.planner_plan.skipped_nodes?.length" class="empty-small">没有跳过节点</div>
          <div v-for="node in wf.planner_plan.skipped_nodes" :key="node.node_id" class="plan-node skipped">
            <span class="skip-mark">-</span>
            <div>
              <strong>{{ node.node_id }}</strong>
              <p>{{ node.reason }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="wf.planner_plan.dependencies?.length" class="dependency-strip">
        <span v-for="edge in wf.planner_plan.dependencies" :key="`${edge.from}-${edge.to}`">
          {{ edge.from }} → {{ edge.to }}
        </span>
      </div>

      <div v-if="wf.planner_plan.fallback_reason" class="fallback-reason">
        {{ wf.planner_plan.fallback_reason }}
      </div>
    </div>

    <div :class="['impact-section', { 'demo-focus': demoMode && demoStep === 'impact' }]">
      <div class="impact-header">
        <div>
          <h3>增量重执行预览</h3>
          <p>根据文件、补遗或人工确认变化计算受影响节点。</p>
        </div>
        <div class="impact-actions">
          <button class="btn-secondary" @click="previewAddendumImpact" :disabled="impactBusy">
            {{ impactBusy ? '计算中' : '预览补遗影响' }}
          </button>
          <button
            v-if="impactPreview?.affected_nodes?.length"
            class="btn-primary"
            @click="runIncremental"
            :disabled="impactBusy"
          >
            {{ impactPreview.confirmation_required ? '确认高风险并执行' : '执行增量重跑' }}
          </button>
        </div>
      </div>

      <div v-if="impactPreview" class="impact-body">
        <div v-if="impactPreview.confirmation_required" class="confirmation-callout">
          <strong>执行前需要确认</strong>
          <span>{{ impactPreview.confirmation_reason }}</span>
        </div>
        <div class="impact-scoreboard">
          <div><span>重跑</span><strong>{{ impactPreview.affected_nodes.length }}</strong></div>
          <div><span>保留</span><strong>{{ impactPreview.unaffected_nodes.length }}</strong></div>
          <div><span>风险</span><strong>{{ impactPreview.high_risk ? '高' : '低' }}</strong></div>
        </div>
        <div class="signal-row">
          <span v-for="signal in impactPreview.changed_signals" :key="signal">{{ signal }}</span>
        </div>
        <div class="impact-lanes">
          <div class="plan-panel">
            <h4>本次变更将重新执行</h4>
            <div v-if="!impactPreview.affected_nodes.length" class="empty-small">没有节点受影响</div>
            <div v-for="node in impactPreview.affected_nodes" :key="node.node_id" class="plan-node selected">
              <span class="priority">{{ node.priority }}</span>
              <div>
                <strong>
                  {{ node.node_id }}
                  <span :class="['mini-risk', node.risk_level]">{{ riskLabel(node.risk_level) }}</span>
                </strong>
                <p>{{ node.reason }}</p>
              </div>
            </div>
          </div>
          <div class="plan-panel">
            <h4>不会重新执行</h4>
            <div v-for="node in impactPreview.unaffected_nodes" :key="node.node_id" class="plan-node skipped">
              <span class="skip-mark">-</span>
              <div>
                <strong>{{ node.node_id }}</strong>
                <p>{{ node.reason }}；历史结果：{{ node.historical_result }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
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
            <span v-if="n.execution?.total_retry_delay_seconds">退避: {{ n.execution.total_retry_delay_seconds }}s</span>
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
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import { pushProgress } from '../feedback'
import DemoGuide from '../components/DemoGuide.vue'
import { scrollDemoFocus } from '../demoScroll'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const wf = ref(null)
const progressEvents = ref([])
const documents = ref([])
const impactPreview = ref(null)
const impactBusy = ref(false)
let source = null

const demoMode = computed(() => route.query.demo === '1')
const demoStep = computed(() => route.query.step || 'planner')
const nodeRuns = computed(() => wf.value?.node_runs || [])
const displayRunway = computed(() => {
  if (wf.value?.planner_plan?.selected_nodes?.length) return wf.value.planner_plan.selected_nodes
  return nodeRuns.value.map((node, index) => ({ node_id: node.node_name, priority: index + 1 }))
})

onMounted(async () => {
  try { wf.value = await store.fetchWorkflow(projectId) } catch(e) {}
  try { documents.value = await store.fetchDocuments(projectId) } catch(e) {}
  if (demoMode.value && demoStep.value === 'impact') {
    try { await previewAddendumImpact() } catch(e) {}
  }
  if (demoMode.value) scrollDemoFocus()
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

watch(() => route.fullPath, () => {
  if (demoMode.value) scrollDemoFocus()
})

function statusLabel(s) {
  const map = { succeeded: '已完成', running: '运行中', waiting_confirmation: '等待确认', failed: '失败',
    cancelled: '已取消', pending: '待执行', retrying: '重试中', idle: '待命' }
  return map[s] || s
}

function riskLabel(level) {
  const map = { high: '高风险', medium: '中风险', low: '低风险' }
  return map[level] || level
}

function countNodeStatus(status) {
  return nodeRuns.value.filter(node => node.status === status).length
}

function nodeStatusFor(nodeId) {
  const found = [...nodeRuns.value].reverse().find(node => node.node_name === nodeId)
  return found?.status || (wf.value?.current_node === nodeId ? 'running' : 'pending')
}

async function resume() { await store.resumeWorkflow(projectId); wf.value = await store.fetchWorkflow(projectId) }
async function cancel() { await store.cancelWorkflow(projectId); wf.value = await store.fetchWorkflow(projectId) }
async function previewAddendumImpact() {
  impactBusy.value = true
  try {
    if (!documents.value.length) documents.value = await store.fetchDocuments(projectId)
    const addendumIds = documents.value.filter(d => d.document_type === 'addendum').map(d => d.id)
    impactPreview.value = await store.previewWorkflowImpact(projectId, {
      change_type: 'addendum_uploaded',
      changed_document_ids: addendumIds,
    })
  } finally {
    impactBusy.value = false
  }
}
async function runIncremental() {
  if (!impactPreview.value) return
  impactBusy.value = true
  try {
    await store.startIncrementalRerun(projectId, {
      preview_id: impactPreview.value.id,
      change_type: impactPreview.value.change_type,
      changed_document_ids: impactPreview.value.changed_resources?.map(item => item.document_id) || [],
      confirm_high_risk: Boolean(impactPreview.value.confirmation_required),
    })
    wf.value = await store.fetchWorkflow(projectId)
  } finally {
    impactBusy.value = false
  }
}
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
.wf-page { max-width: 1480px; }
.stage-hero { display: flex; justify-content: space-between; gap: 22px; align-items: stretch; margin-bottom: 18px; }
.hero-copy {
  position: relative;
  flex: 1;
  min-height: 196px;
  padding: 32px;
  border-radius: 28px;
  color: white;
  background:
    linear-gradient(135deg, rgba(8,13,23,.96) 0%, rgba(18,28,44,.96) 55%, rgba(57,74,99,.94) 100%),
    linear-gradient(90deg, rgba(255,255,255,.08), transparent);
  box-shadow: 0 28px 70px rgba(15, 23, 42, .24);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  overflow: hidden;
}
.hero-copy::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(0,0,0,.18), transparent 58%);
  pointer-events: none;
}
.hero-copy > * {
  position: relative;
  z-index: 1;
}
.eyebrow { font-size: 12px; font-weight: 900; color: rgba(255,255,255,.82); margin-bottom: 12px; }
.hero-copy h2 {
  margin: 0;
  color: #fff;
  font-size: 44px;
  font-weight: 900;
  line-height: 1.06;
  text-shadow: 0 2px 18px rgba(0,0,0,.36);
}
.hero-copy p { margin: 12px 0 0; max-width: 720px; color: rgba(255,255,255,.86); font-size: 15px; font-weight: 600; line-height: 1.75; text-shadow: 0 1px 12px rgba(0,0,0,.28); }
.hero-status { width: 240px; border: 1px solid rgba(226,232,240,.95); border-radius: 28px; background: rgba(255,255,255,.9); backdrop-filter: blur(22px); padding: 24px; box-shadow: 0 20px 50px rgba(15,23,42,.12); display: flex; flex-direction: column; justify-content: center; gap: 8px; }
.stage-pulse { width: 16px; height: 16px; border-radius: 50%; background: #94a3b8; box-shadow: 0 0 0 8px rgba(148,163,184,.12); }
.stage-pulse.running, .stage-pulse.retrying { background: #0ea5e9; box-shadow: 0 0 0 8px rgba(14,165,233,.14); animation: pulse 1.2s infinite; }
.stage-pulse.succeeded { background: #10b981; box-shadow: 0 0 0 8px rgba(16,185,129,.14); }
.stage-pulse.failed { background: #ef4444; box-shadow: 0 0 0 8px rgba(239,68,68,.13); }
.stage-pulse.waiting_confirmation { background: #f59e0b; box-shadow: 0 0 0 8px rgba(245,158,11,.16); }
.hero-status strong { font-size: 26px; color: #111827; }
.hero-status small { color: #64748b; line-height: 1.5; }
.command-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(320px, .8fr); gap: 16px; margin-bottom: 16px; }
.mission-card, .live-feed-card, .planner-section, .impact-section { background: rgba(255,255,255,.86); border: 1px solid rgba(226,232,240,.9); border-radius: 24px; padding: 18px; box-shadow: 0 18px 45px rgba(15,23,42,.08); }
.demo-focus {
  position: relative;
  border-color: rgba(17,24,39,.3) !important;
  box-shadow: 0 0 0 4px rgba(17,24,39,.08), 0 26px 70px rgba(15,23,42,.16) !important;
}
.demo-focus::before {
  content: "Demo Focus";
  position: absolute;
  right: 18px;
  top: -12px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #111827;
  color: white;
  font-size: 11px;
  font-weight: 900;
}
.card-title { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px; }
.card-title span { font-size: 12px; color: #64748b; font-weight: 800; }
.card-title b { color: #0f172a; font-size: 13px; }
.mission-metrics, .impact-scoreboard { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.mission-metrics div, .impact-scoreboard div { border-radius: 18px; background: #f8fafc; border: 1px solid #e5e7eb; padding: 13px; }
.mission-metrics span, .impact-scoreboard span { display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }
.mission-metrics strong, .impact-scoreboard strong { color: #111827; font-size: 24px; }
.runway { display: flex; align-items: center; gap: 8px; min-height: 42px; margin: 14px 0 4px; padding: 12px; border-radius: 18px; background: linear-gradient(90deg, #f8fafc, #eef2f7); overflow: auto; }
.runway-dot { flex: 0 0 13px; width: 13px; height: 13px; border-radius: 50%; background: #cbd5e1; box-shadow: 0 0 0 5px rgba(203,213,225,.18); }
.runway-dot.succeeded { background: #10b981; }
.runway-dot.running, .runway-dot.retrying { background: #0ea5e9; animation: pulse 1.2s infinite; }
.runway-dot.failed { background: #ef4444; }
.runway-dot.waiting_confirmation { background: #f59e0b; }
.wf-actions { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.btn-primary, .btn-secondary { padding: 10px 16px; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 800; transition: transform .18s ease, box-shadow .18s ease; }
.btn-primary { background: #111827; color: white; border: none; box-shadow: 0 12px 26px rgba(15,23,42,.18); }
.btn-secondary { background: white; color: #111827; border: 1px solid #dbe3ee; }
.btn-primary:hover, .btn-secondary:hover { transform: translateY(-1px); }
.empty-stage { color: #94a3b8; font-size: 13px; padding: 12px 0 2px; }
.mini-feed { display: flex; flex-direction: column; gap: 10px; }
.mini-event { display: grid; grid-template-columns: 10px 1fr auto; gap: 10px; align-items: center; padding: 10px; border-radius: 16px; background: #f8fafc; }
.mini-event > span { width: 8px; height: 8px; border-radius: 50%; background: #0ea5e9; }
.mini-event.done > span { background: #10b981; }
.mini-event.error > span { background: #ef4444; }
.mini-event strong { display: block; color: #111827; font-size: 13px; }
.mini-event small { color: #64748b; }
.mini-event em { color: #94a3b8; font-style: normal; font-size: 11px; }
.planner-section, .impact-section { margin-bottom: 18px; }
.impact-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 12px; }
.impact-header h3 { margin: 0 0 4px; font-size: 18px; color: #111827; }
.impact-header p { margin: 0; font-size: 13px; color: #666; }
.impact-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.impact-body { display: flex; flex-direction: column; gap: 12px; }
.signal-row { display: flex; gap: 8px; flex-wrap: wrap; }
.signal-row span { background: #eef7f4; color: #176b51; border: 1px solid #d6ede5; padding: 5px 8px; border-radius: 999px; font-size: 12px; }
.planner-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 14px; }
.planner-header h3 { margin: 0 0 4px; font-size: 18px; color: #111827; }
.planner-header p { margin: 0; font-size: 13px; color: #666; }
.planner-badges { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.risk-pill, .fallback-pill { font-size: 12px; padding: 4px 10px; border-radius: 999px; white-space: nowrap; }
.risk-pill.high { background: #fde2e2; color: #9f1d1d; }
.risk-pill.medium { background: #fff4cc; color: #835b00; }
.risk-pill.low { background: #dcf7e6; color: #146c36; }
.fallback-pill { background: #eef1f5; color: #475569; }
.confirmation-callout { display: flex; gap: 10px; align-items: center; background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; padding: 12px 14px; border-radius: 16px; margin-bottom: 14px; font-size: 13px; }
.agent-map { display: flex; gap: 10px; overflow: auto; padding: 4px 2px 16px; }
.map-node { min-width: 220px; display: grid; grid-template-columns: 30px 1fr; gap: 10px; border: 1px solid #e5e7eb; border-radius: 18px; padding: 12px; background: #f8fafc; position: relative; }
.map-node::after { content: ""; position: absolute; right: -10px; top: 50%; width: 10px; height: 1px; background: #cbd5e1; }
.map-node:last-child::after { display: none; }
.map-node.succeeded { border-color: #bbf7d0; background: #f0fdf4; }
.map-node.running, .map-node.retrying { border-color: #bae6fd; background: #f0f9ff; }
.map-node.failed { border-color: #fecaca; background: #fff1f2; }
.map-node.waiting_confirmation, .map-node.gate { border-color: #fed7aa; background: #fff7ed; }
.map-node strong { color: #111827; font-size: 13px; }
.map-node p { margin: 4px 0 0; color: #64748b; font-size: 12px; line-height: 1.5; }
.plan-grid, .impact-lanes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.plan-panel { border: 1px solid #edf0f2; border-radius: 18px; padding: 14px; background: rgba(248,250,252,.62); }
.plan-panel.compact { max-height: 330px; overflow: auto; }
.plan-panel h4 { margin: 0 0 10px; font-size: 14px; color: #333; }
.plan-node { display: grid; grid-template-columns: 28px 1fr; gap: 10px; padding: 10px 0; border-top: 1px solid #f1f3f5; }
.plan-node:first-of-type { border-top: 0; }
.plan-node strong { display: block; font-size: 13px; color: #233044; }
.human-gate { display: inline-flex; margin-left: 6px; padding: 1px 6px; border-radius: 999px; background: #fff4cc; color: #835b00; font-size: 11px; font-weight: 700; vertical-align: middle; }
.mini-risk { display: inline-flex; margin-left: 6px; padding: 1px 6px; border-radius: 999px; font-size: 11px; font-weight: 700; vertical-align: middle; }
.mini-risk.high { background: #fde2e2; color: #9f1d1d; }
.mini-risk.medium { background: #fff4cc; color: #835b00; }
.mini-risk.low { background: #dcf7e6; color: #146c36; }
.plan-node p { margin: 3px 0 0; font-size: 12px; color: #6b7280; line-height: 1.5; }
.priority, .skip-mark { width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.priority { background: #e7f2ff; color: #0f4c81; }
.skip-mark { background: #f1f3f5; color: #7b8494; }
.empty-small { color: #999; font-size: 13px; padding: 8px 0; }
.dependency-strip { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.dependency-strip span { background: #f6f8fb; color: #475569; border: 1px solid #e6ebf1; padding: 6px 9px; border-radius: 6px; font-size: 12px; }
.fallback-reason { margin-top: 12px; color: #9f1d1d; background: #fff5f5; border-radius: 6px; padding: 8px 10px; font-size: 12px; }
.node-section h3 { margin: 0 0 12px; font-size: 18px; color: #111827; }
.node-list { display: flex; flex-direction: column; gap: 10px; }
.node-card { background: white; border-radius: 18px; padding: 14px 16px; box-shadow: 0 10px 28px rgba(15,23,42,.06); border-left: 4px solid #ddd; }
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
.thinking-section h3 { margin: 0 0 12px; font-size: 18px; color: #111827; }
.thinking-list { background: white; border-radius: 18px; box-shadow: 0 10px 28px rgba(15,23,42,.06); overflow: hidden; }
.thinking-item { display: grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 12px 14px; border-left: 4px solid #3498db; border-bottom: 1px solid #f3f4f6; }
.thinking-item.done { border-left-color: #27ae60; }
.thinking-item.llm { border-left-color: #8e44ad; }
.thinking-item.error { border-left-color: #e74c3c; background: #fff7f7; }
.thinking-time { font-size: 12px; color: #999; }
.thinking-item strong { display: block; font-size: 14px; color: #333; }
.thinking-item p { margin: 3px 0 0; font-size: 12px; color: #777; }
@media (max-width: 780px) {
  .stage-hero, .command-grid, .plan-grid, .impact-lanes { grid-template-columns: 1fr; flex-direction: column; }
  .hero-status { width: auto; }
  .hero-copy h2 { font-size: 32px; }
  .mission-metrics, .impact-scoreboard { grid-template-columns: repeat(2, 1fr); }
  .planner-header, .impact-header { flex-direction: column; }
}
</style>
