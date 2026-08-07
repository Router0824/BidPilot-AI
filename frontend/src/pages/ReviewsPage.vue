<template>
  <div class="reviews-page">
    <div class="header">
      <h2>审查中心</h2>
      <button class="btn-primary" @click="runReview" :disabled="reviewing">{{ reviewing ? '审查中...' : '开始审查' }}</button>
    </div>

    <div v-if="reviews.length" class="reviews-list">
      <div v-for="r in reviews" :key="r.id" class="review-card">
        <div class="review-header">
          <span class="review-type">{{ r.review_type === 'full' ? '全面审查' : r.review_type }}</span>
          <span :class="['review-status', r.status]">{{ r.status === 'completed' ? '已完成' : r.status }}</span>
          <span class="review-time">{{ new Date(r.created_at).toLocaleString('zh-CN') }}</span>
        </div>
        <div class="review-summary">发现 {{ r.findings_count }} 个问题</div>
      </div>
    </div>

    <div v-if="findings.length" class="findings-section">
      <h3>最新审查发现</h3>
      <div class="findings-list">
        <div v-for="f in findings" :key="f.id" :class="['finding-item', f.risk_level]">
          <div class="finding-header">
            <span :class="['risk-badge', f.risk_level]">{{ riskLabel(f.risk_level) }}</span>
            <span class="finding-type">{{ typeLabel(f.finding_type) }}</span>
            <span :class="['finding-status', f.status]">{{ f.status === 'open' ? '待处理' : '已处理' }}</span>
          </div>
          <p class="finding-desc">{{ f.description }}</p>
          <p v-if="f.suggestion" class="finding-suggestion">建议：{{ f.suggestion }}</p>
          <div v-if="f.status === 'open'" class="finding-actions">
            <button class="btn-sm btn-resolve" @click="resolveFinding(f.id)">确认处理</button>
            <button class="btn-sm btn-ignore" @click="ignoreFinding(f.id)">忽略</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!reviews.length && !reviewing" class="empty">点击"开始审查"对当前标书进行全面审查</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const reviews = ref([])
const findings = ref([])
const reviewing = ref(false)

onMounted(async () => { reviews.value = await store.listReviews(projectId) })

function riskLabel(r) { return { high: '高风险', medium: '中风险', low: '低风险' }[r] || r }
function typeLabel(t) {
  return { uncovered_requirement: '未响应要求', fact_inconsistency: '事实不一致',
    unverified_citation: '未验证引用', overcommit: '过度承诺' }[t] || t
}

async function runReview() {
  reviewing.value = true
  try {
    const result = await store.runReview(projectId, 'full')
    findings.value = result.findings || []
    reviews.value = await store.listReviews(projectId)
  } finally { reviewing.value = false }
}

async function resolveFinding(id) {
  await store.updateFinding(projectId, id, 'resolved')
  findings.value = findings.value.map(f => f.id === id ? {...f, status: 'resolved'} : f)
}

async function ignoreFinding(id) {
  await store.updateFinding(projectId, id, 'ignored', '经评估无需处理')
  findings.value = findings.value.map(f => f.id === id ? {...f, status: 'ignored'} : f)
}
</script>

<style scoped>
.reviews-page { max-width: 1200px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h2 { margin: 0; color: #1a1a2e; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { opacity: 0.6; }
.reviews-list { margin-bottom: 24px; }
.review-card { background: white; border-radius: 8px; padding: 14px 20px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.review-header { display: flex; gap: 12px; align-items: center; font-size: 13px; }
.review-type { font-weight: 500; }
.review-status.completed { color: #27ae60; }
.review-time { margin-left: auto; color: #999; font-size: 12px; }
.review-summary { margin-top: 6px; font-size: 13px; color: #666; }
.findings-section h3 { margin: 0 0 12px; font-size: 16px; color: #1a1a2e; }
.findings-list { display: flex; flex-direction: column; gap: 10px; }
.finding-item { background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #ddd; }
.finding-item.high { border-left-color: #e74c3c; }
.finding-item.medium { border-left-color: #f39c12; }
.finding-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.risk-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.risk-badge.high { background: #fde8e8; color: #c0392b; }
.risk-badge.medium { background: #fef3e2; color: #e67e22; }
.finding-type { font-size: 13px; color: #555; }
.finding-status { font-size: 11px; padding: 2px 6px; border-radius: 8px; margin-left: auto; }
.finding-status.open { background: #fff3cd; color: #856404; }
.finding-status.resolved { background: #d4edda; color: #155724; }
.finding-desc { font-size: 13px; color: #333; margin: 0 0 4px; }
.finding-suggestion { font-size: 12px; color: #888; margin: 0 0 8px; }
.finding-actions { display: flex; gap: 8px; }
.btn-sm { padding: 4px 12px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; }
.btn-resolve { background: #27ae60; color: white; }
.btn-ignore { background: #eee; color: #666; }
.empty { text-align: center; padding: 60px 0; color: #999; font-size: 14px; }
</style>