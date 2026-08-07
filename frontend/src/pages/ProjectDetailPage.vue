<template>
  <div class="project-detail">
    <div class="header command-header">
      <div>
        <span class="eyebrow">PROJECT DOSSIER</span>
        <h2>{{ project?.name }}</h2>
      </div>
      <span :class="['status-badge', project?.workflow_status]">{{ statusLabel(project?.workflow_status) }}</span>
    </div>

    <div class="info-cards">
      <div class="info-card"><span class="label">项目类型</span><span class="value">{{ project?.project_type }}</span></div>
      <div class="info-card"><span class="label">负责人</span><span class="value">{{ project?.owner_name }}</span></div>
      <div class="info-card"><span class="label">截止日期</span><span class="value">{{ fmtDate(project?.deadline) }}</span></div>
      <div class="info-card"><span class="label">文件数</span><span class="value">{{ project?.document_count }}</span></div>
      <div class="info-card"><span class="label">要求数</span><span class="value">{{ project?.requirement_count }}</span></div>
      <div class="info-card risk"><span class="label">高风险</span><span class="value">{{ project?.high_risk_count }}</span></div>
    </div>

    <section class="demo-launch">
      <div class="demo-launch-copy">
        <span class="eyebrow">DEMO MODE</span>
        <h3>90 秒演示路线</h3>
        <p>从 Agent 自主规划开始，依次展示补遗增量重跑、证据链覆盖矩阵、Reviewer/Fixer 闭环。</p>
      </div>
      <div class="demo-steps">
        <button
          v-for="step in demoSteps"
          :key="step.key"
          class="demo-step"
          @click="goDemo(step)"
        >
          <span>{{ step.no }}</span>
          <strong>{{ step.title }}</strong>
          <small>{{ step.caption }}</small>
        </button>
      </div>
      <div class="demo-controls">
        <button class="demo-start" @click="prepareDemo" :disabled="demoPreparing">
          {{ demoPreparing ? '预热中' : '预热演示数据' }}
        </button>
        <button class="demo-start light" @click="goDemo(demoSteps[0])">开始 90 秒演示</button>
      </div>
      <div v-if="demoPrepSteps.length" class="demo-prep-log">
        <span v-for="item in demoPrepSteps" :key="item.key" :class="item.status">
          {{ item.label }}：{{ item.message }}
        </span>
      </div>
    </section>

    <div class="section">
      <div class="section-header">
        <h3>文件中心</h3>
        <div>
          <input type="file" ref="fileInput" @change="handleUpload" style="display:none" multiple />
          <select v-model="uploadType" class="doc-type-select">
            <option value="tender_main">招标主文件</option>
            <option value="technical_spec">技术规范</option>
            <option value="scoring_table">评分表</option>
            <option value="addendum">补遗</option>
            <option value="qualification">资质材料</option>
            <option value="case_study">案例材料</option>
          </select>
          <button class="btn-primary" @click="$refs.fileInput.click()">上传文件</button>
        </div>
      </div>
      <div v-if="uploading" class="upload-hint">正在上传文件，大文件将自动分片...</div>
      <table v-if="documents.length" class="table">
        <thead><tr><th>文件名</th><th>类型</th><th>版本</th><th>大小</th><th>解析状态</th><th>页数</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="d in documents" :key="d.id">
            <td>{{ d.name }}</td>
            <td>{{ docTypeLabel(d.document_type) }}</td>
            <td>V{{ d.version }}</td>
            <td>{{ fmtSize(d.file_size) }}</td>
            <td><span :class="['parse-status', d.parse_status]">{{ d.parse_status }}</span></td>
            <td>{{ d.page_count }}</td>
            <td>
              <button v-if="d.parse_status === 'pending'" class="btn-sm" @click="parseDoc(d.id)" :disabled="busyAction === `parse:${d.id}`">
                {{ busyAction === `parse:${d.id}` ? '解析中' : '解析' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-hint">请上传招标文件、技术附件或补遗文件</div>
    </div>

    <div class="section">
      <div class="section-header">
        <h3>工作流控制</h3>
        <div class="actions">
          <button v-if="!wf?.has_active_workflow" class="btn-primary" @click="startWf" :disabled="busyAction === 'workflow:start'">
            {{ busyAction === 'workflow:start' ? '启动中' : '启动工作流' }}
          </button>
          <button v-if="wf?.workflow_status === 'waiting_confirmation'" class="btn-primary" @click="resumeWf" :disabled="busyAction === 'workflow:resume'">
            {{ busyAction === 'workflow:resume' ? '继续中' : '继续执行' }}
          </button>
          <button class="btn-secondary" @click="detectConflicts" :disabled="busyAction === 'conflicts'">
            {{ busyAction === 'conflicts' ? '识别中' : '识别补遗冲突' }}
          </button>
          <button class="btn-secondary" @click="mergeScoring" :disabled="busyAction === 'scoring:merge'">
            {{ busyAction === 'scoring:merge' ? '合并中' : '合并跨页评分' }}
          </button>
          <button v-if="wf?.has_active_workflow" class="btn-secondary" @click="cancelWf" :disabled="busyAction === 'workflow:cancel'">
            {{ busyAction === 'workflow:cancel' ? '取消中' : '取消' }}
          </button>
        </div>
      </div>
      <div v-if="wf?.has_active_workflow" class="wf-info">
        <p>当前节点：<strong>{{ wf.current_node }}</strong></p>
        <p>工作流状态：<strong>{{ statusLabel(wf.workflow_status) }}</strong></p>
      </div>
      <div v-if="wf?.node_runs?.length" class="node-list">
        <div v-for="n in wf.node_runs" :key="n.id" class="node-item">
          <span :class="['node-dot', n.status]"></span>
          <span class="node-name">{{ n.node_name }}</span>
          <span class="node-status">{{ n.status }}</span>
          <span v-if="n.token_usage" class="node-tokens">{{ n.token_usage }} tokens</span>
        </div>
      </div>
      <div v-if="addendumConflicts.length" class="conflict-list">
        <h4>补遗冲突</h4>
        <div v-for="c in addendumConflicts" :key="c.id" class="conflict-item">
          <span>{{ c.candidate_value?.fact_key }}</span>
          <span>{{ c.candidate_value?.old_value }}</span>
          <span>→</span>
          <strong>{{ c.candidate_value?.new_value }}</strong>
        </div>
      </div>
    </div>

    <div class="quick-actions">
      <router-link :to="`/project/${projectId}/facts`" class="action-card">事实确认</router-link>
      <router-link :to="`/project/${projectId}/requirements`" class="action-card">要求矩阵</router-link>
      <router-link :to="`/project/${projectId}/evidence`" class="action-card">响应证据图谱</router-link>
      <router-link :to="`/project/${projectId}/outline`" class="action-card">技术标大纲</router-link>
      <router-link :to="`/project/${projectId}/reviews`" class="action-card">审查中心</router-link>
      <router-link :to="`/project/${projectId}/workflow`" class="action-card">Agent 任务</router-link>
      <router-link :to="`/project/${projectId}/consultation`" class="action-card">咨询中心</router-link>
      <router-link :to="`/project/${projectId}/enterprise`" class="action-card">企业协作</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { pushMessage } from '../feedback'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const projectId = route.params.id
const project = ref(null)
const documents = ref([])
const wf = ref(null)
const uploadType = ref('tender_main')
const uploading = ref(false)
const addendumConflicts = ref([])
const busyAction = ref('')
const demoPreparing = ref(false)
const demoPrepSteps = ref([])
const demoSteps = [
  { no: '01', key: 'workflow', title: 'Agent 计划图', caption: 'Planner 为什么执行/跳过', path: 'workflow', step: 'planner' },
  { no: '02', key: 'impact', title: '增量预览', caption: '补遗影响范围和高风险确认', path: 'workflow', step: 'impact' },
  { no: '03', key: 'evidence', title: '证据链', caption: '要求覆盖矩阵和来源页码', path: 'evidence', step: 'chain' },
  { no: '04', key: 'review', title: '审查修正', caption: 'Reviewer/Fixer 闭环', path: 'reviews', step: 'fixer' },
]

onMounted(async () => {
  project.value = await store.fetchProject(projectId)
  documents.value = await store.fetchDocuments(projectId)
  try { wf.value = await store.fetchWorkflow(projectId) } catch (e) { /* no workflow yet */ }
  try { addendumConflicts.value = await store.listAddendumConflicts(projectId) } catch (e) {}
})

function statusLabel(s) {
  const map = { created: '已创建', files_uploaded: '已上传', parsing: '解析中', parsed: '已解析',
    extracting_requirements: '提取中', waiting_for_confirmation: '等待确认', facts_confirmed: '已确认',
    matrix_generated: '矩阵已生成', outline_generated: '大纲已生成', drafting: '生成中',
    draft_completed: '草稿完成', reviewing: '审查中', review_completed: '审查完成',
    ready_to_export: '待导出', exported: '已导出', failed: '失败', cancelled: '已取消', retrying: '重试中',
    succeeded: '已完成', running: '运行中', pending: '待执行' }
  return map[s] || s
}
function docTypeLabel(t) {
  const map = { tender_main: '招标主文件', technical_spec: '技术规范', scoring_table: '评分表',
    addendum: '补遗', clarification: '澄清文件', company_product: '企业产品资料',
    historical_bid: '历史标书', qualification: '资质材料', case_study: '案例材料' }
  return map[t] || t
}
function fmtDate(d) { return d ? new Date(d).toLocaleDateString('zh-CN') : '-' }
function fmtSize(s) { return s ? (s > 1024*1024 ? `${(s/1024/1024).toFixed(1)}MB` : `${(s/1024).toFixed(1)}KB`) : '-' }
function goDemo(step) {
  router.push(`/project/${projectId}/${step.path}?demo=1&step=${step.step}`)
}
function setPrep(key, label, status, message) {
  const next = { key, label, status, message }
  const index = demoPrepSteps.value.findIndex(item => item.key === key)
  if (index >= 0) demoPrepSteps.value[index] = next
  else demoPrepSteps.value.push(next)
}
async function prepareDemo() {
  demoPreparing.value = true
  demoPrepSteps.value = []
  try {
    setPrep('conflict', '补遗冲突', 'running', '识别中')
    try {
      const result = await store.detectAddendumConflicts(projectId)
      addendumConflicts.value = await store.listAddendumConflicts(projectId)
      setPrep('conflict', '补遗冲突', 'done', `${result.detected_conflicts || addendumConflicts.value.length || 0} 个冲突`)
    } catch (error) {
      setPrep('conflict', '补遗冲突', 'failed', error.response?.data?.detail || '未完成')
    }

    setPrep('impact', '增量预览', 'running', '计算中')
    try {
      if (!documents.value.length) documents.value = await store.fetchDocuments(projectId)
      const addendumIds = documents.value.filter(d => d.document_type === 'addendum').map(d => d.id)
      const preview = await store.previewWorkflowImpact(projectId, {
        change_type: 'addendum_uploaded',
        changed_document_ids: addendumIds,
      })
      setPrep('impact', '增量预览', 'done', `重跑 ${preview.affected_nodes?.length || 0} 个节点`)
    } catch (error) {
      setPrep('impact', '增量预览', 'failed', error.response?.data?.detail || '未完成')
    }

    setPrep('evidence', '证据矩阵', 'running', '重建中')
    try {
      const result = await store.rebuildCoverageMatrix(projectId)
      setPrep('evidence', '证据矩阵', 'done', `${result.links_created || result.links_updated || 0} 条链路`)
    } catch (error) {
      setPrep('evidence', '证据矩阵', 'failed', error.response?.data?.detail || '未完成')
    }

    setPrep('review', '审查修正', 'running', '审查中')
    try {
      const review = await store.runReview(projectId, 'full')
      const fixable = (review.findings || []).filter(f => f.auto_fix_allowed && f.status === 'open').slice(0, 2)
      let fixed = 0
      for (const finding of fixable) {
        await store.fixFinding(projectId, finding.id, true)
        fixed += 1
      }
      setPrep('review', '审查修正', 'done', `${review.total_findings || 0} 个问题，自动修正 ${fixed} 个`)
    } catch (error) {
      setPrep('review', '审查修正', 'failed', error.response?.data?.detail || '未完成')
    }
  } finally {
    demoPreparing.value = false
  }
}

async function handleUpload(e) {
  const files = e.target.files
  uploading.value = true
  try {
    for (const f of files) {
      await store.uploadDocument(projectId, f, uploadType.value)
    }
    documents.value = await store.fetchDocuments(projectId)
  } catch (error) {
    pushMessage('error', '上传失败', error.response?.data?.message || error.response?.data?.detail || error.message)
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}
async function parseDoc(docId) {
  busyAction.value = `parse:${docId}`
  try {
    await store.parseDocument(projectId, docId)
    documents.value = await store.fetchDocuments(projectId)
  } finally { busyAction.value = '' }
}
async function startWf() {
  const docIds = documents.value.map(d => d.id)
  busyAction.value = 'workflow:start'
  try {
    await store.startWorkflow(projectId, docIds)
    wf.value = await store.fetchWorkflow(projectId)
    project.value = await store.fetchProject(projectId)
  } finally { busyAction.value = '' }
}
async function resumeWf() {
  busyAction.value = 'workflow:resume'
  try {
    await store.resumeWorkflow(projectId)
    wf.value = await store.fetchWorkflow(projectId)
  } finally { busyAction.value = '' }
}
async function cancelWf() {
  busyAction.value = 'workflow:cancel'
  try {
    await store.cancelWorkflow(projectId)
    wf.value = await store.fetchWorkflow(projectId)
  } finally { busyAction.value = '' }
}
async function detectConflicts() {
  busyAction.value = 'conflicts'
  try {
    await store.detectAddendumConflicts(projectId)
    addendumConflicts.value = await store.listAddendumConflicts(projectId)
  } finally { busyAction.value = '' }
}
async function mergeScoring() {
  busyAction.value = 'scoring:merge'
  try {
    const result = await store.mergeCrossPageScoring(projectId)
    alert(`已合并 ${result.merged_items || 0} 个评分项`)
  } finally { busyAction.value = '' }
}
</script>

<style scoped>
.project-detail { max-width: 1280px; }
.header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.command-header {
  justify-content: space-between;
  align-items: flex-end;
  padding: 24px 26px;
  border: 1px solid rgba(255,255,255,.86);
  border-radius: 8px;
  background:
    linear-gradient(120deg, rgba(255,255,255,.92), rgba(255,255,255,.66)),
    radial-gradient(circle at 88% 20%, rgba(37,99,235,.12), transparent 30%);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(24px) saturate(1.16);
}
.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: .12em;
}
h2 { margin: 0; font-size: 28px; color: var(--ink); line-height: 1.25; }
.status-badge { font-size: 12px; padding: 6px 12px; border-radius: 999px; background: rgba(17,24,39,.06); color: var(--ink); border: 1px solid rgba(17,24,39,.08); }
.info-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.info-card {
  background: rgba(255,255,255,.82); border-radius: 8px; padding: 14px 16px; min-width: 120px;
  box-shadow: var(--shadow-soft);
  border: 1px solid rgba(255,255,255,.86);
  border-top: 3px solid rgba(17,24,39,.18);
  backdrop-filter: blur(18px);
}
.info-card.risk { border-top-color: var(--red); }
.info-card .label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.info-card .value { font-size: 20px; font-weight: 800; color: var(--ink); }
.info-card.risk .value { color: var(--red); }
.demo-launch {
  display: grid;
  grid-template-columns: minmax(240px, .9fr) minmax(0, 1.7fr) auto;
  gap: 14px;
  align-items: stretch;
  margin-bottom: 20px;
  padding: 18px;
  border: 1px solid rgba(17,24,39,.1);
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(17,24,39,.96), rgba(51,65,85,.92)),
    linear-gradient(120deg, rgba(255,255,255,.1), transparent);
  box-shadow: 0 24px 60px rgba(15,23,42,.16);
  color: white;
}
.demo-launch-copy h3 { margin: 0; color: white; font-size: 24px; }
.demo-launch-copy p { margin: 8px 0 0; color: rgba(255,255,255,.72); font-size: 13px; line-height: 1.6; }
.demo-launch .eyebrow { color: rgba(255,255,255,.64); }
.demo-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.demo-step {
  min-height: 98px;
  padding: 12px;
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 18px;
  background: rgba(255,255,255,.08);
  color: white;
  text-align: left;
  cursor: pointer;
}
.demo-step span { display: block; color: rgba(255,255,255,.52); font-size: 11px; font-weight: 900; }
.demo-step strong { display: block; margin-top: 8px; font-size: 14px; }
.demo-step small { display: block; margin-top: 4px; color: rgba(255,255,255,.62); line-height: 1.4; }
.demo-step:hover { background: rgba(255,255,255,.14); }
.demo-controls { display: flex; flex-direction: column; gap: 8px; align-self: center; }
.demo-start {
  align-self: center;
  min-height: 44px;
  padding: 0 18px;
  border: 0;
  border-radius: 999px;
  background: white;
  color: #111827;
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
  white-space: nowrap;
}
.demo-start:disabled { opacity: .62; cursor: not-allowed; }
.demo-start.light { background: rgba(255,255,255,.12); color: white; border: 1px solid rgba(255,255,255,.22); }
.demo-prep-log {
  grid-column: 1 / -1;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 4px;
}
.demo-prep-log span {
  padding: 6px 9px;
  border-radius: 999px;
  background: rgba(255,255,255,.1);
  color: rgba(255,255,255,.78);
  font-size: 12px;
  font-weight: 800;
}
.demo-prep-log .done { background: rgba(16,185,129,.18); color: #d1fae5; }
.demo-prep-log .running { background: rgba(59,130,246,.18); color: #dbeafe; }
.demo-prep-log .failed { background: rgba(239,68,68,.18); color: #fee2e2; }
.section { background: rgba(255,255,255,.82); border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: var(--shadow-soft); border: 1px solid rgba(255,255,255,.86); backdrop-filter: blur(20px); }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-header > div { display: flex; gap: 8px; align-items: center; }
.doc-type-select { padding: 9px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; background: white; }
h3 { margin: 0; font-size: 18px; color: var(--ink); }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 11px 12px; font-size: 13px; border-bottom: 1px solid #edf2ed; }
.table th { color: #666; font-weight: 500; background: #fafafa; }
.parse-status.completed { color: #27ae60; }
.parse-status.failed { color: #e74c3c; }
.parse-status.pending { color: #f39c12; }
.btn-sm { padding: 4px 12px; font-size: 12px; background: #0f3460; color: white; border: none; border-radius: 4px; cursor: pointer; }
.actions { display: flex; gap: 8px; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary { padding: 10px 20px; background: #eee; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.wf-info { margin-bottom: 12px; font-size: 14px; color: #555; }
.node-list { display: flex; flex-wrap: wrap; gap: 8px; }
.node-item { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 7px 10px; background: rgba(255,255,255,.64); border: 1px solid rgba(17,24,39,.08); border-radius: 999px; }
.node-dot { width: 8px; height: 8px; border-radius: 50%; }
.node-dot.succeeded { background: #27ae60; }
.node-dot.failed { background: #e74c3c; }
.node-dot.running { background: #3498db; animation: pulse 1s infinite; }
.node-dot.pending { background: #ccc; }
.node-dot.waiting_confirmation { background: #f39c12; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.node-status { color: #888; }
.node-tokens { color: #aaa; }
.empty-hint { color: #999; font-size: 14px; padding: 20px 0; text-align: center; }
.upload-hint { color: #666; font-size: 13px; margin-bottom: 12px; }
.conflict-list { margin-top: 14px; padding-top: 12px; border-top: 1px solid #eee; }
.conflict-list h4 { margin: 0 0 8px; font-size: 14px; color: #1a1a2e; }
.conflict-item { display: grid; grid-template-columns: 120px 1fr 24px 1fr; gap: 8px; padding: 8px 0; font-size: 13px; border-bottom: 1px solid #f5f5f5; }
.quick-actions { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.action-card {
  position: relative;
  background: rgba(255,255,255,.82); border-radius: 8px; padding: 20px 18px; text-align: left; text-decoration: none;
  color: var(--ink); font-weight: 800; font-size: 15px; box-shadow: var(--shadow-soft);
  transition: box-shadow 0.22s, transform .18s, background .18s, border-color .18s;
  border: 1px solid rgba(255,255,255,.86);
  backdrop-filter: blur(18px);
}
.action-card::after {
  content: "→";
  position: absolute;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}
.action-card:hover { box-shadow: var(--shadow-lift); transform: translateY(-3px); background: rgba(255,255,255,.96); border-color: rgba(17,24,39,.10); }
@media (max-width: 860px) {
  .demo-launch { grid-template-columns: 1fr; }
  .demo-steps { grid-template-columns: repeat(2, 1fr); }
  .section-header { align-items: flex-start; gap: 12px; flex-direction: column; }
  .section-header > div { flex-wrap: wrap; }
}
</style>
