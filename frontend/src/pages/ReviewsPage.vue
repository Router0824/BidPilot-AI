<template>
  <div class="reviews-page">
    <DemoGuide
      v-if="demoMode"
      title="第 4 步：Reviewer/Fixer 闭环"
      body="先展示结构化审查问题，再演示低风险自动修正和高风险人工处理，强调系统不会无限循环或擅自改写关键承诺。"
      :next-to="`/project/${projectId}`"
      next-label="完成演示"
      :exit-to="`/project/${projectId}`"
    />

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

    <div v-if="findings.length" :class="['findings-section', { 'demo-focus': demoMode }]">
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
            <button class="btn-sm btn-fix" @click="fixFinding(f)" :disabled="fixingId === f.id">
              {{ f.auto_fix_allowed ? (fixingId === f.id ? '修正中' : '自动修正') : '请求人工处理' }}
            </button>
            <button class="btn-sm btn-resolve" @click="resolveFinding(f.id)">确认处理</button>
            <button class="btn-sm btn-ignore" @click="ignoreFinding(f.id)">忽略</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="fixAttempts.length" :class="['fix-section', { 'demo-focus': demoMode }]">
      <h3>Fixer 修改记录</h3>
      <div v-for="a in fixAttempts" :key="a.id" :class="['fix-card', a.status]">
        <div class="fix-header">
          <span>{{ typeLabel(a.issue_type) }}</span>
          <strong>{{ a.status === 'applied' ? '已自动修正' : a.status === 'manual_required' ? '等待人工处理' : '建议' }}</strong>
          <em>第 {{ a.attempt_no }} 次</em>
        </div>
        <p>{{ a.reason }}</p>
        <div class="diff-grid">
          <div>
            <h4>修改前</h4>
            <pre>{{ preview(a.before_content) }}</pre>
          </div>
          <div>
            <h4>修改后</h4>
            <pre>{{ preview(a.after_content) }}</pre>
          </div>
        </div>
        <div v-if="a.diff?.added?.length" class="diff-added">
          + {{ a.diff.added.join('\n+ ') }}
        </div>
      </div>
    </div>

    <div v-if="!reviews.length && !reviewing" class="empty">点击"开始审查"对当前标书进行全面审查</div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'
import DemoGuide from '../components/DemoGuide.vue'
import { scrollDemoFocus } from '../demoScroll'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const reviews = ref([])
const findings = ref([])
const fixAttempts = ref([])
const reviewing = ref(false)
const fixingId = ref('')
const demoMode = computed(() => route.query.demo === '1')

onMounted(async () => {
  reviews.value = await store.listReviews(projectId)
  fixAttempts.value = await store.listFixAttempts(projectId)
  if (demoMode.value && !reviews.value.length && !fixAttempts.value.length) {
    await prepareDemoReview()
  }
  if (demoMode.value) scrollDemoFocus()
})

function riskLabel(r) { return { high: '高风险', medium: '中风险', low: '低风险' }[r] || r }
function typeLabel(t) {
  return { uncovered_requirement: '未响应要求', fact_inconsistency: '事实不一致',
    unverified_citation: '未验证引用', overcommit: '过度承诺',
    missing_requirement: '缺失要求', partial_coverage: '部分覆盖',
    internal_conflict: '内部矛盾', unsupported_claim: '无依据表述',
    citation_missing: '引用不足', addendum_conflict: '补遗冲突',
    qualification_risk: '资格风险', schedule_conflict: '工期冲突',
    numeric_inconsistency: '数值不一致' }[t] || t
}
function preview(text) {
  const value = text || ''
  return value.length > 420 ? `${value.slice(0, 420)}...` : value
}

async function runReview() {
  reviewing.value = true
  try {
    const result = await store.runReview(projectId, 'full')
    findings.value = result.findings || []
    reviews.value = await store.listReviews(projectId)
    fixAttempts.value = await store.listFixAttempts(projectId)
    if (demoMode.value) scrollDemoFocus()
  } finally { reviewing.value = false }
}

async function prepareDemoReview() {
  reviewing.value = true
  try {
    const result = await store.runReview(projectId, 'full')
    findings.value = result.findings || []
    const fixable = findings.value.filter(f => f.auto_fix_allowed && f.status === 'open').slice(0, 2)
    for (const finding of fixable) {
      await store.fixFinding(projectId, finding.id, true)
      findings.value = findings.value.map(item => item.id === finding.id ? { ...item, status: 'resolved' } : item)
    }
    reviews.value = await store.listReviews(projectId)
    fixAttempts.value = await store.listFixAttempts(projectId)
    if (demoMode.value) scrollDemoFocus()
  } finally { reviewing.value = false }
}

watch(() => route.fullPath, () => {
  if (demoMode.value) scrollDemoFocus()
})

async function fixFinding(f) {
  fixingId.value = f.id
  try {
    await store.fixFinding(projectId, f.id, true)
    fixAttempts.value = await store.listFixAttempts(projectId)
    findings.value = findings.value.map(item => item.id === f.id && f.auto_fix_allowed ? {...item, status: 'resolved'} : item)
  } finally { fixingId.value = '' }
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
.demo-focus {
  position: relative;
  border-radius: 18px;
  box-shadow: 0 0 0 4px rgba(17,24,39,.08);
}
.demo-focus::before {
  content: "Demo Focus";
  position: absolute;
  right: 14px;
  top: -12px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #111827;
  color: white;
  font-size: 11px;
  font-weight: 900;
}
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
.btn-fix { background: #0f3460; color: white; }
.fix-section { margin-top: 24px; }
.fix-section h3 { margin: 0 0 12px; font-size: 16px; color: #1a1a2e; }
.fix-card { background: white; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #9aa4b2; }
.fix-card.applied { border-left-color: #27ae60; }
.fix-card.manual_required { border-left-color: #f39c12; }
.fix-header { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; font-size: 13px; }
.fix-header strong { color: #0f3460; }
.fix-header em { margin-left: auto; color: #888; font-style: normal; font-size: 12px; }
.fix-card p { margin: 0 0 10px; color: #555; font-size: 13px; }
.diff-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.diff-grid h4 { margin: 0 0 6px; font-size: 12px; color: #666; }
pre { margin: 0; min-height: 92px; max-height: 180px; overflow: auto; white-space: pre-wrap; background: #f8fafc; border: 1px solid #edf0f2; border-radius: 6px; padding: 10px; font-size: 12px; color: #344054; }
.diff-added { margin-top: 10px; white-space: pre-wrap; background: #effaf3; color: #176b35; border-radius: 6px; padding: 8px 10px; font-size: 12px; }
.empty { text-align: center; padding: 60px 0; color: #999; font-size: 14px; }
@media (max-width: 760px) {
  .diff-grid { grid-template-columns: 1fr; }
}
</style>
