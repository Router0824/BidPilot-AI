<template>
  <div class="enterprise-page">
    <div class="header">
      <h2>企业协作</h2>
      <button class="btn-primary" @click="loadAll">刷新</button>
    </div>

    <div v-if="errorMsg" class="toast error">{{ errorMsg }}</div>
    <div v-if="successMsg" class="toast success">{{ successMsg }}</div>

    <div class="grid">
      <!-- 在线协作者 -->
      <section class="panel wide presence-panel">
        <h3>在线协作者</h3>
        <div class="presence-list">
          <span v-for="u in onlineUsers" :key="u.user_id" class="presence-chip">{{ u.display_name }} · {{ roleLabel(u.role) }}</span>
          <span v-if="!onlineUsers.length" class="muted">暂无在线协作者</span>
        </div>
      </section>

      <!-- 项目成员 -->
      <section class="panel">
        <h3>项目成员</h3>
        <div class="inline-form">
          <select v-model="memberForm.userId">
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</option>
          </select>
          <select v-model="memberForm.role">
            <option value="project_admin">项目管理员</option>
            <option value="writer">编制人</option>
            <option value="reviewer">审核人</option>
          </select>
          <button class="btn-secondary" @click="saveMember">加入/更新</button>
        </div>
        <div class="list">
          <div v-for="m in members" :key="m.id" class="list-row">
            <strong>{{ m.user_name }}</strong>
            <span>{{ roleLabel(m.role) }}</span>
            <button class="btn-sm danger" @click="removeMember(m.user_id)">移除</button>
          </div>
          <div v-if="!members.length" class="muted">暂无成员</div>
        </div>
      </section>

      <!-- 行业模板 -->
      <section class="panel">
        <h3>行业模板</h3>
        <div class="template-grid">
          <button v-for="t in templates" :key="t.key" class="template-btn" @click="applyTemplate(t.key)">
            <strong>{{ t.name }}</strong>
            <span>{{ t.section_count }} 个章节</span>
          </button>
        </div>
      </section>

      <!-- 章节分配与审批 -->
      <section class="panel wide">
        <h3>章节分配</h3>
        <div class="section-table">
          <div v-for="s in flatSections" :key="s.id" class="section-row">
            <span :style="{ paddingLeft: (s.level - 1) * 18 + 'px' }">{{ s.title }}</span>
            <em>{{ s.owner_name || '未分配' }}</em>
            <select v-model="assignmentDraft[s.id]">
              <option value="">选择负责人</option>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
            <button class="btn-sm" @click="assign(s.id)">分配</button>
            <button class="btn-sm secondary" @click="lockSection(s.id)">🔒</button>
            <select v-model="reviewerDraft[s.id]" class="reviewer-select">
              <option value="">选择审核人</option>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</option>
            </select>
            <button class="btn-sm" @click="submitApproval(s.id)">提交审批</button>
          </div>
        </div>
        <div v-if="!flatSections.length" class="muted">暂无章节，请先生成大纲</div>
      </section>

      <!-- 审批队列 -->
      <section class="panel">
        <h3>审批队列</h3>
        <div class="list">
          <div v-for="a in approvals" :key="a.id" class="approval-row">
            <span>{{ sectionTitle(a.section_id) }}</span>
            <span class="reviewer">{{ a.reviewer_name || '未指定' }}</span>
            <strong :class="a.status">{{ approvalLabel(a.status) }}</strong>
            <div v-if="a.status === 'pending'" class="row-actions">
              <button class="btn-sm" @click="resolveApproval(a.id, 'approve')">通过</button>
              <button class="btn-sm danger" @click="resolveApproval(a.id, 'reject')">驳回</button>
            </div>
          </div>
          <div v-if="!approvals.length" class="muted">暂无审批</div>
        </div>
      </section>

      <!-- 补遗冲突 -->
      <section class="panel">
        <div class="section-header">
          <h3>补遗冲突</h3>
          <button class="btn-sm" @click="detectConflicts">检测</button>
        </div>
        <div class="list">
          <div v-for="c in conflicts" :key="c.id" class="conflict-row">
            <span class="conflict-key">{{ c.candidate_value?.fact_key }}</span>
            <span class="conflict-old">{{ c.candidate_value?.old_value }}</span>
            <span>→</span>
            <span class="conflict-new">{{ c.candidate_value?.new_value }}</span>
            <span class="conflict-status">{{ c.status }}</span>
          </div>
          <div v-if="!conflicts.length" class="muted">暂无补遗冲突</div>
        </div>
      </section>

      <!-- 商务标 / 资格标 -->
      <section class="panel">
        <h3>商务标 / 资格标</h3>
        <div class="doc-actions">
          <button class="btn-primary" @click="generateCommercial" :disabled="generatingCommercial">
            {{ generatingCommercial ? '生成中...' : '生成商务标' }}
          </button>
          <button class="btn-primary" @click="generateQualification" :disabled="generatingQualification">
            {{ generatingQualification ? '生成中...' : '生成资格标' }}
          </button>
        </div>
        <textarea v-if="specialDoc" v-model="specialDoc" rows="12" readonly></textarea>
      </section>

      <!-- 操作审计 -->
      <section class="panel wide">
        <h3>操作审计</h3>
        <div class="audit-list">
          <div v-for="log in audits" :key="log.id" class="audit-row">
            <span>{{ fmtTime(log.created_at) }}</span>
            <strong>{{ log.action }}</strong>
            <em>{{ log.resource_type }}</em>
            <code>{{ log.operator }}</code>
          </div>
          <div v-if="!audits.length" class="muted">暂无审计记录</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const users = [
  { id: 'user_admin_001', name: '系统管理员' },
  { id: 'user_bm_001', name: '投标经理' },
  { id: 'user_wr_001', name: '编制人员' },
  { id: 'user_rv_001', name: '审核人员' },
]

const members = ref([])
const templates = ref([])
const outline = ref([])
const approvals = ref([])
const audits = ref([])
const conflicts = ref([])
const specialDoc = ref('')
const assignmentDraft = ref({})
const reviewerDraft = ref({})
const memberForm = ref({ userId: 'user_wr_001', role: 'writer' })
const onlineUsers = ref([])
const generatingCommercial = ref(false)
const generatingQualification = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
let socket = null

const flatSections = computed(() => flatten(outline.value))

function showError(msg) { errorMsg.value = msg; setTimeout(() => errorMsg.value = '', 4000) }
function showSuccess(msg) { successMsg.value = msg; setTimeout(() => successMsg.value = '', 3000) }

onMounted(async () => {
  await loadAll()
  const wsUrl = store.collaborationWsUrl(projectId)
  socket = new WebSocket(wsUrl)
  socket.addEventListener('message', (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (payload.type === 'presence.changed') onlineUsers.value = payload.users || []
    } catch {}
  })
  socket.addEventListener('error', () => {
    onlineUsers.value = []
  })
})

onUnmounted(() => {
  socket?.close()
})

async function loadAll() {
  try {
    const [m, t, o, a, au, c] = await Promise.all([
      store.fetchEnterpriseMembers(projectId).catch(() => []),
      store.fetchIndustryTemplates(projectId).catch(() => []),
      store.fetchOutline(projectId).catch(() => []),
      store.fetchApprovals(projectId).catch(() => []),
      store.fetchAudits(projectId).catch(() => []),
      store.listAddendumConflicts(projectId).catch(() => []),
    ])
    members.value = m; templates.value = t; outline.value = o
    approvals.value = a; audits.value = au; conflicts.value = c
  } catch (e) {
    showError('加载数据失败: ' + (e.message || '未知错误'))
  }
}

function flatten(items) {
  const rows = []
  for (const item of items || []) {
    rows.push(item)
    rows.push(...flatten(item.children || []))
  }
  return rows
}

async function saveMember() {
  try {
    await store.saveEnterpriseMember(projectId, memberForm.value.userId, memberForm.value.role)
    members.value = await store.fetchEnterpriseMembers(projectId)
    showSuccess('成员已更新')
  } catch (e) { showError('操作失败: ' + (e.message || '未知错误')) }
}

async function removeMember(userId) {
  try {
    await store.saveEnterpriseMember(projectId, userId, 'removed')
    members.value = await store.fetchEnterpriseMembers(projectId)
    showSuccess('成员已移除')
  } catch (e) { showError('操作失败') }
}

async function applyTemplate(key) {
  try {
    await store.applyIndustryTemplate(projectId, key)
    outline.value = await store.fetchOutline(projectId)
    showSuccess(`模板「${key}」已应用`)
  } catch (e) { showError('应用模板失败') }
}

async function assign(sectionId) {
  const userId = assignmentDraft.value[sectionId]
  if (!userId) { showError('请选择负责人'); return }
  try {
    await store.assignSection(projectId, sectionId, userId)
    outline.value = await store.fetchOutline(projectId)
    audits.value = await store.fetchAudits(projectId)
    showSuccess('章节已分配')
  } catch (e) { showError('分配失败') }
}

async function lockSection(sectionId) {
  try {
    const result = await store.lockSection(projectId, sectionId)
    if (result.error) {
      showError(result.error === 'locked' ? `已被 ${result.locked_by} 锁定` : '权限不足')
    } else {
      showSuccess('已锁定 (5分钟)')
    }
  } catch (e) { showError('锁定失败') }
}

async function submitApproval(sectionId) {
  const reviewerId = reviewerDraft.value[sectionId] || 'user_rv_001'
  try {
    await store.submitSectionApproval(projectId, sectionId, reviewerId)
    approvals.value = await store.fetchApprovals(projectId)
    outline.value = await store.fetchOutline(projectId)
    showSuccess('已提交审批')
  } catch (e) { showError('提交审批失败') }
}

async function resolveApproval(id, action) {
  try {
    await store.resolveApproval(projectId, id, action)
    approvals.value = await store.fetchApprovals(projectId)
    outline.value = await store.fetchOutline(projectId)
    showSuccess(action === 'approve' ? '已通过' : '已驳回')
  } catch (e) { showError('操作失败') }
}

async function detectConflicts() {
  try {
    const result = await store.detectAddendumConflicts(projectId)
    conflicts.value = await store.listAddendumConflicts(projectId)
    showSuccess(`检测到 ${result.detected_conflicts || 0} 个冲突`)
  } catch (e) { showError('冲突检测失败') }
}

async function generateCommercial() {
  generatingCommercial.value = true
  try {
    const result = await store.generateCommercialBid(projectId)
    specialDoc.value = result.content
    audits.value = await store.fetchAudits(projectId)
    showSuccess('商务标生成完成')
  } catch (e) { showError('生成失败') }
  finally { generatingCommercial.value = false }
}

async function generateQualification() {
  generatingQualification.value = true
  try {
    const result = await store.generateQualificationBid(projectId)
    specialDoc.value = result.content
    audits.value = await store.fetchAudits(projectId)
    showSuccess('资格标生成完成')
  } catch (e) { showError('生成失败') }
  finally { generatingQualification.value = false }
}

function roleLabel(role) {
  return { project_admin: '项目管理员', writer: '编制人', reviewer: '审核人' }[role] || role
}
function approvalLabel(status) {
  return { pending: '待审批', approved: '已通过', rejected: '已驳回' }[status] || status
}
function sectionTitle(id) {
  return flatSections.value.find(s => s.id === id)?.title || id.slice(0, 8)
}
function fmtTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : ''
}
</script>

<style scoped>
.enterprise-page { max-width: 1400px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
h2 { margin: 0; color: #1a1a2e; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.presence-panel { padding-top: 14px; padding-bottom: 14px; }
.presence-list { display: flex; gap: 8px; flex-wrap: wrap; }
.presence-chip { background: #e8f4fd; color: #0f3460; padding: 5px 10px; border-radius: 999px; font-size: 12px; }
.muted { color: #999; font-size: 13px; }
.panel { background: white; border-radius: 10px; padding: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.panel.wide { grid-column: 1 / -1; }
.panel h3 { margin: 0 0 14px; font-size: 16px; color: #1a1a2e; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.section-header h3 { margin: 0; }
.inline-form, .doc-actions { display: flex; gap: 8px; margin-bottom: 12px; }
select, textarea { border: 1px solid #ddd; border-radius: 6px; padding: 8px 10px; font-size: 13px; }
textarea { width: 100%; line-height: 1.6; resize: vertical; }
.btn-primary, .btn-secondary, .btn-sm { border: none; border-radius: 6px; cursor: pointer; }
.btn-primary { padding: 10px 16px; background: #0f3460; color: white; font-size: 14px; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 8px 12px; background: #eef2f7; color: #1f2937; }
.btn-sm { padding: 5px 10px; background: #0f3460; color: white; font-size: 12px; }
.btn-sm.secondary { background: #64748b; }
.btn-sm.danger { background: #dc2626; }
.list { display: flex; flex-direction: column; gap: 8px; }
.list-row, .approval-row, .audit-row, .section-row, .conflict-row { display: grid; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.list-row { grid-template-columns: 1fr 110px 60px; }
.approval-row { grid-template-columns: 1fr 80px 70px 130px; }
.section-row { grid-template-columns: 1fr 100px 150px 50px 40px 140px 70px; }
.conflict-row { grid-template-columns: 120px 1fr 20px 1fr 80px; }
.audit-row { grid-template-columns: 180px 160px 140px 1fr; }
.section-row em, .audit-row em, .conflict-row em { color: #667085; font-style: normal; }
.template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.template-btn { padding: 14px; border: 1px solid #dcecff; background: #f8fbff; border-radius: 8px; text-align: left; cursor: pointer; }
.template-btn strong, .template-btn span { display: block; }
.template-btn span { margin-top: 4px; color: #667085; font-size: 12px; }
.approved { color: #16a34a; }
.rejected { color: #dc2626; }
.pending { color: #d97706; }
.row-actions { display: flex; gap: 6px; }
.audit-list { max-height: 280px; overflow: auto; }
code { background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }
.reviewer { color: #999; font-size: 12px; }
.reviewer-select { width: 130px; }
.conflict-old { color: #dc2626; text-decoration: line-through; }
.conflict-new { color: #16a34a; font-weight: 500; }
.conflict-key { font-weight: 500; }
.conflict-status { font-size: 11px; padding: 2px 6px; border-radius: 8px; background: #f0f0f0; }
.toast { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; animation: fadeIn 0.3s; }
.toast.error { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.toast.success { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
</style>
