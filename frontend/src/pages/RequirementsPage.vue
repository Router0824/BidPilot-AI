<template>
  <div class="req-page">
    <div class="header">
      <h2>要求与风险矩阵</h2>
      <div class="header-actions">
        <button class="btn-secondary" @click="recalculate" :disabled="recalculating">{{ recalculating ? '量化中' : '重新量化置信度' }}</button>
        <button class="btn-primary" @click="exportReq">导出</button>
      </div>
    </div>

    <div class="filters">
      <select v-model="filterRisk" @change="loadReqs"><option value="">全部风险</option><option value="high">高风险</option><option value="medium">中风险</option><option value="low">低风险</option></select>
      <select v-model="filterType" @change="loadReqs"><option value="">全部类型</option><option value="qualification">资格</option><option value="technical">技术</option><option value="commercial">商务</option><option value="scoring">评分</option><option value="delivery">交付</option><option value="format">格式</option></select>
      <select v-model="filterStatus" @change="loadReqs"><option value="">全部状态</option><option value="pending">待确认</option><option value="confirmed">已确认</option><option value="responded">已响应</option><option value="missing">缺失</option></select>
      <span class="summary">共 {{ requirements.length }} 条要求</span>
    </div>

    <div class="table-container">
      <table class="table">
        <thead>
          <tr><th style="width:40%">要求内容</th><th>类型</th><th>硬性</th><th>风险</th><th>来源</th><th>置信度</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in requirements" :key="r.id" :class="['req-row', r.risk_level]">
            <td class="req-text">{{ r.requirement_text?.substring(0, 150) }}{{ r.requirement_text?.length > 150 ? '...' : '' }}</td>
            <td>{{ typeLabel(r.requirement_type) }}</td>
            <td>{{ r.mandatory ? '是' : '否' }}</td>
            <td><span :class="['risk-tag', r.risk_level]">{{ riskLabel(r.risk_level) }}</span></td>
            <td class="source">P{{ r.source_page }}</td>
            <td>
              <span class="confidence-chip" :title="r.confidence_detail?.explanation">
                <b :class="['confidence-dot', r.confidence_detail?.level]"></b>
                {{ confidencePercent(r) }}%
              </span>
            </td>
            <td><span :class="['status-tag', r.status]">{{ statusLabel(r.status) }}</span></td>
            <td>
              <button v-if="r.status === 'pending'" class="btn-sm btn-approve" @click="confirmReq(r.id)" :disabled="confirmingId === r.id">
                {{ confirmingId === r.id ? '确认中' : '确认' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
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
const requirements = ref([])
const filterRisk = ref('')
const filterType = ref('')
const filterStatus = ref('')
const confirmingId = ref('')
const recalculating = ref(false)

onMounted(loadReqs)

async function loadReqs() {
  const filters = {}
  if (filterRisk.value) filters.risk_level = filterRisk.value
  if (filterType.value) filters.req_type = filterType.value
  if (filterStatus.value) filters.status = filterStatus.value
  requirements.value = await store.fetchRequirements(projectId, filters)
}

function typeLabel(t) { return { qualification: '资格', technical: '技术', commercial: '商务', scoring: '评分', delivery: '交付', format: '格式' }[t] || t }
function riskLabel(r) { return { high: '高', medium: '中', low: '低' }[r] || r }
function statusLabel(s) { return { pending: '待确认', confirmed: '已确认', responded: '已响应', missing: '缺失' }[s] || s }
function confidencePercent(r) { return Math.round(((r.confidence_detail?.score ?? r.confidence ?? 0) * 100)) }

async function confirmReq(id) {
  confirmingId.value = id
  try {
    await store.confirmRequirement(projectId, id)
    await loadReqs()
  } finally {
    confirmingId.value = ''
  }
}

async function exportReq() {
  await store.exportData(projectId, 'requirements', 'markdown')
  alert('导出完成')
}

async function recalculate() {
  recalculating.value = true
  try {
    const result = await store.recalculateConfidence(projectId)
    pushMessage('success', '置信度量化完成', `事实 ${result.facts} 条，要求 ${result.requirements} 条`)
    await loadReqs()
  } finally {
    recalculating.value = false
  }
}
</script>

<style scoped>
.req-page { max-width: 1400px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-actions { display: flex; gap: 10px; }
h2 { margin: 0; color: #1a1a2e; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-secondary { padding: 10px 16px; background: #fff; color: #0f3460; border: 1px solid #b9cce3; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; }
.btn-primary, .btn-secondary, .btn-sm { transition: transform .15s, box-shadow .15s, background .15s; }
.btn-primary:hover:not(:disabled), .btn-secondary:hover:not(:disabled) { box-shadow: 0 8px 18px rgba(15,52,96,.16); transform: translateY(-1px); }
.btn-secondary:hover:not(:disabled) { background: #eef6ff; }
.btn-primary:active:not(:disabled), .btn-secondary:active:not(:disabled), .btn-sm:active:not(:disabled) { transform: scale(.98); box-shadow: none; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: .55; cursor: not-allowed; }
.filters { display: flex; gap: 10px; margin-bottom: 16px; align-items: center; }
.filters select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.summary { margin-left: auto; font-size: 13px; color: #666; }
.table-container { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 10px 12px; font-size: 13px; border-bottom: 1px solid #f0f0f0; }
.table th { background: #f8f9fa; color: #666; font-weight: 500; position: sticky; top: 0; }
.req-row.high { background: #fff5f5; }
.req-text { max-width: 400px; word-break: break-all; }
.source { color: #999; font-size: 12px; white-space: nowrap; }
.confidence-chip { display: inline-flex; align-items: center; gap: 6px; color: #4c5668; font-weight: 700; white-space: nowrap; }
.confidence-dot { width: 8px; height: 8px; border-radius: 50%; background: #d9822b; }
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
.status-tag.responded { background: #cce5ff; color: #004085; }
.btn-sm { padding: 4px 10px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; }
.btn-approve { background: #27ae60; color: white; }
</style>
