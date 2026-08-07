<template>
  <div class="facts-page">
    <div class="header">
      <h2>项目事实确认</h2>
      <button class="btn-primary" @click="recalculate" :disabled="recalculating">{{ recalculating ? '量化中' : '重新量化置信度' }}</button>
    </div>
    <p class="desc">以下信息由系统从招标文件中提取，请确认或修改后进行确认。高风险字段必须人工确认后方可进入后续流程。</p>

    <div v-if="loading">加载中...</div>
    <div v-else class="facts-table">
      <div class="table-header">
        <span>事实字段</span><span>提取值</span><span>来源</span><span>置信度</span><span>风险</span><span>状态</span><span>操作</span>
      </div>
      <div v-for="f in facts" :key="f.id" :class="['fact-row', f.risk_level]">
        <span class="fact-key">{{ factKeyLabel(f.fact_key) }}</span>
        <span class="fact-value">
          <input v-if="editingId === f.id" v-model="editValue" class="edit-input" />
          <span v-else>{{ f.fact_value }}</span>
        </span>
        <span class="fact-source">{{ f.source_document_id?.slice(0,8) }} / P{{ f.source_page }}</span>
        <span class="fact-confidence" :title="f.confidence_detail?.explanation">
          <b :class="['confidence-dot', f.confidence_detail?.level]"></b>
          {{ confidencePercent(f) }}%
        </span>
        <span :class="['risk-tag', f.risk_level]">{{ riskLabel(f.risk_level) }}</span>
        <span :class="['status-tag', f.confirmation_status]">{{ confirmLabel(f.confirmation_status) }}</span>
        <span class="actions">
          <template v-if="editingId === f.id">
            <button class="btn-sm btn-approve" @click="saveEdit(f)">保存</button>
            <button class="btn-sm btn-edit" @click="cancelEdit">取消</button>
          </template>
          <template v-else-if="f.confirmation_status === 'pending'">
            <button class="btn-sm btn-approve" @click="approve(f)">确认</button>
            <button class="btn-sm btn-edit" @click="startEdit(f)">修改</button>
            <button class="btn-sm btn-reject" @click="reject(f)">拒绝</button>
          </template>
          <span v-else class="confirmed-by">已由 {{ f.confirmed_by || '用户' }} 确认</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { pushMessage } from '../feedback'
import { useAppStore } from '../stores/app'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const facts = ref([])
const loading = ref(true)
const editingId = ref(null)
const editValue = ref('')
const recalculating = ref(false)

onMounted(loadFacts)

async function loadFacts() {
  facts.value = await store.fetchFacts(projectId)
  loading.value = false
}

function factKeyLabel(k) {
  const map = { project_name: '项目名称', bidder: '招标人', budget: '预算', duration: '工期',
    deadline: '截止时间', deployment: '部署方式', warranty: '质保期' }
  return map[k] || k
}
function riskLabel(r) { return { high: '高', medium: '中', low: '低' }[r] || r }
function confirmLabel(s) { return { pending: '待确认', confirmed: '已确认', modified: '已修改', rejected: '已拒绝', uncertain: '不确定' }[s] || s }
function confidencePercent(f) { return Math.round(((f.confidence_detail?.score ?? f.confidence ?? 0) * 100)) }

async function approve(f) {
  await store.confirmFact(projectId, f.id, { action: 'approve', resource_version: f.version })
  facts.value = await store.fetchFacts(projectId)
}
function startEdit(f) { editingId.value = f.id; editValue.value = f.fact_value }
function cancelEdit() { editingId.value = null; editValue.value = '' }
async function reject(f) {
  await store.confirmFact(projectId, f.id, { action: 'reject', resource_version: f.version })
  facts.value = await store.fetchFacts(projectId)
}
async function saveEdit(f) {
  await store.confirmFact(projectId, f.id, { action: 'modify_and_approve', value: editValue.value, resource_version: f.version })
  editingId.value = null
  facts.value = await store.fetchFacts(projectId)
}

async function recalculate() {
  recalculating.value = true
  try {
    const result = await store.recalculateConfidence(projectId)
    pushMessage('success', '置信度量化完成', `事实 ${result.facts} 条，要求 ${result.requirements} 条`)
    await loadFacts()
  } finally {
    recalculating.value = false
  }
}
</script>

<style scoped>
.facts-page { max-width: 1200px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
h2 { margin: 0 0 8px; color: #1a1a2e; }
.desc { color: #666; font-size: 13px; margin-bottom: 20px; }
.facts-table { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.table-header, .fact-row {
  display: grid;
  grid-template-columns: 120px 1fr 140px 70px 60px 80px 200px;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
  font-size: 13px;
}
.table-header { background: #f8f9fa; font-weight: 500; color: #666; border-bottom: 2px solid #eee; }
.fact-row { border-bottom: 1px solid #f0f0f0; }
.fact-row.high { background: #fff5f5; }
.fact-key { font-weight: 500; color: #333; }
.fact-value { color: #555; }
.fact-source { color: #999; font-size: 12px; }
.fact-confidence { color: #4c5668; font-size: 12px; display: inline-flex; align-items: center; gap: 6px; font-weight: 700; }
.confidence-dot { width: 8px; height: 8px; border-radius: 50%; background: #d9822b; flex: 0 0 auto; }
.confidence-dot.high { background: #27ae60; }
.confidence-dot.medium { background: #d9822b; }
.confidence-dot.low { background: #c0392b; }
.risk-tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.risk-tag.high { background: #fde8e8; color: #c0392b; }
.risk-tag.medium { background: #fef3e2; color: #e67e22; }
.risk-tag.low { background: #e8f5e9; color: #27ae60; }
.status-tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.status-tag.pending { background: #fff3cd; color: #856404; }
.status-tag.confirmed { background: #d4edda; color: #155724; }
.status-tag.rejected { background: #f8d7da; color: #721c24; }
.actions { display: flex; gap: 6px; }
.btn-sm { padding: 4px 10px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; }
.btn-primary { padding: 9px 16px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; transition: transform .15s, box-shadow .15s, background .15s; }
.btn-primary:hover:not(:disabled) { background: #14508f; box-shadow: 0 8px 18px rgba(15,52,96,.18); transform: translateY(-1px); }
.btn-primary:active:not(:disabled), .btn-sm:active:not(:disabled) { transform: scale(.98); }
.btn-primary:disabled { opacity: .55; cursor: not-allowed; }
.btn-approve { background: #27ae60; color: white; }
.btn-edit { background: #3498db; color: white; }
.btn-reject { background: #e74c3c; color: white; }
.confirmed-by { font-size: 12px; color: #999; }
.edit-input { padding: 4px 8px; border: 1px solid #3498db; border-radius: 4px; font-size: 13px; width: 100%; }
</style>
