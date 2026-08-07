<template>
  <div class="evidence-page">
    <DemoGuide
      v-if="demoMode"
      title="第 3 步：响应证据链"
      body="点击左侧任意招标要求，右侧会展示来源页码、原文片段、投标章节、企业材料、生成内容和审查问题。"
      :next-to="`/project/${projectId}/reviews?demo=1&step=fixer`"
      next-label="进入审查修正"
      :exit-to="`/project/${projectId}`"
    />

    <section class="evidence-hero">
      <div>
        <span class="eyebrow">TRACEABILITY GRAPH</span>
        <h2>响应证据图谱主舞台</h2>
        <p>招标原文、结构化要求、投标章节、企业材料和审查结果的可追溯链路</p>
      </div>
      <div class="hero-score">
        <span>覆盖率</span>
        <strong>{{ coverageRate }}%</strong>
        <small>{{ riskOpen }} 个高风险待处理</small>
      </div>
    </section>

    <div class="header">
      <div class="stage-note">
        <strong>要求覆盖矩阵</strong>
        <span>点击任意要求查看完整证据链</span>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="rebuild" :disabled="busy">{{ busy ? '重建中' : '重建链路' }}</button>
        <button class="btn-primary" @click="load">{{ busy ? '刷新中' : '刷新' }}</button>
      </div>
    </div>

    <div class="metrics">
      <div><span>要求</span><strong>{{ matrix.length }}</strong></div>
      <div><span>强制</span><strong>{{ countBy('mandatory', true) }}</strong></div>
      <div><span>已覆盖</span><strong>{{ statusCount('covered') }}</strong></div>
      <div><span>部分覆盖</span><strong>{{ statusCount('partially_covered') }}</strong></div>
      <div><span>缺失</span><strong>{{ statusCount('missing') }}</strong></div>
      <div><span>冲突</span><strong>{{ statusCount('conflicted') }}</strong></div>
    </div>

    <div class="evidence-stage">
      <div class="matrix-shell">
        <table class="matrix-table">
          <thead>
            <tr>
              <th>招标要求</th>
              <th>原文页码</th>
              <th>原文片段</th>
              <th>类型</th>
              <th>分值</th>
              <th>风险</th>
              <th>投标章节</th>
              <th>企业材料</th>
              <th>覆盖</th>
              <th>审查问题</th>
              <th>置信度</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in matrix" :key="row.link_id" @click="selectRow(row)" :class="{active: selected?.link_id === row.link_id}">
              <td class="req-cell">{{ trim(row.requirement_text, 120) }}</td>
              <td>P{{ row.source_page || '-' }}</td>
              <td class="quote-cell">{{ trim(row.source_quote, 90) }}</td>
              <td>{{ typeLabel(row.requirement_type) }}</td>
              <td>{{ row.score_weight ?? '-' }}</td>
              <td><span :class="['risk-tag', row.risk_level]">{{ riskLabel(row.risk_level) }}</span></td>
              <td>{{ row.target_section_title || '-' }}</td>
              <td>{{ row.knowledge_evidence_names?.join('、') || '-' }}</td>
              <td><span :class="['coverage-tag', row.coverage_status]">{{ coverageLabel(row.coverage_status) }}</span></td>
              <td>{{ row.review_issue_ids?.length || 0 }}</td>
              <td>{{ percent(row.confidence) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <aside :class="['chain-panel', { 'demo-focus': demoMode }]">
        <template v-if="chain">
          <div class="chain-header">
            <div>
              <span>Evidence Chain</span>
              <h3>证据链详情</h3>
            </div>
            <button class="btn-icon" @click="chain = null">×</button>
          </div>

          <div class="chain-path">
            <span>原文</span><i></i><span>要求</span><i></i><span>章节</span><i></i><span>审查</span>
          </div>

          <section>
            <h4>招标原文</h4>
            <p class="source-line">{{ chain.source_document?.name || '-' }} · P{{ chain.source?.page || '-' }}</p>
            <blockquote>{{ chain.source?.quote || '未定位到原文片段' }}</blockquote>
          </section>

          <section>
            <h4>结构化要求</h4>
            <p>{{ chain.row.requirement_text }}</p>
            <div class="chips">
              <span>{{ typeLabel(chain.row.requirement_type) }}</span>
              <span>{{ riskLabel(chain.row.risk_level) }}</span>
              <span>{{ coverageLabel(chain.row.coverage_status) }}</span>
            </div>
          </section>

          <section>
            <h4>投标响应章节</h4>
            <p>{{ chain.target_section?.title || '尚未绑定章节' }}</p>
          </section>

          <section>
            <h4>企业知识材料</h4>
            <div v-if="!chain.knowledge_evidence?.length" class="empty-small">尚未引用企业材料</div>
            <div v-for="item in chain.knowledge_evidence" :key="item.id" class="material-card">
              <strong>{{ item.material_name }}</strong>
              <span>P{{ item.source_page || '-' }} · {{ item.material_type }}</span>
              <p>{{ trim(item.content, 180) }}</p>
            </div>
          </section>

          <section>
            <h4>生成内容</h4>
            <p v-if="chain.generated_content" class="generated">{{ trim(chain.generated_content.content, 500) }}</p>
            <div v-else class="empty-small">尚未生成对应章节内容</div>
          </section>

          <section>
            <h4>审查结果</h4>
            <div v-if="!chain.review_issues?.length" class="empty-small">暂无打开的审查问题</div>
            <div v-for="issue in chain.review_issues" :key="issue.id" class="issue-card">
              <strong>{{ issue.issue_type }}</strong>
              <p>{{ issue.description }}</p>
              <span>{{ issue.suggestion }}</span>
            </div>
          </section>
        </template>
        <div v-else class="chain-empty">
          <span>选择一条要求</span>
          <strong>查看从招标原文到投标响应的完整链路</strong>
          <p>这里会展示页码、原文片段、企业材料、生成内容和 Reviewer 问题。</p>
        </div>
      </aside>
    </div>
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
const matrix = ref([])
const selected = ref(null)
const chain = ref(null)
const busy = ref(false)
const demoMode = computed(() => route.query.demo === '1')
const coverageRate = computed(() => {
  if (!matrix.value.length) return 0
  return Math.round((statusCount('covered') / matrix.value.length) * 100)
})
const riskOpen = computed(() => matrix.value.filter(row => row.risk_level === 'high' && row.coverage_status !== 'covered').length)

onMounted(load)

async function load() {
  busy.value = true
  try {
    matrix.value = await store.fetchCoverageMatrix(projectId)
    if (demoMode.value && !matrix.value.length) {
      await store.rebuildCoverageMatrix(projectId)
      matrix.value = await store.fetchCoverageMatrix(projectId)
    }
    if (demoMode.value && matrix.value.length && !chain.value) {
      await selectRow(matrix.value[0])
    }
    if (demoMode.value) scrollDemoFocus()
  } finally { busy.value = false }
}

async function rebuild() {
  busy.value = true
  try {
    await store.rebuildCoverageMatrix(projectId)
    matrix.value = await store.fetchCoverageMatrix(projectId)
  } finally { busy.value = false }
}

async function selectRow(row) {
  selected.value = row
  chain.value = await store.fetchEvidenceChain(projectId, row.requirement_id)
  if (demoMode.value) scrollDemoFocus()
}

watch(() => route.fullPath, () => {
  if (demoMode.value) scrollDemoFocus()
})

function trim(value, len) {
  const text = value || ''
  return text.length > len ? `${text.slice(0, len)}...` : text
}
function percent(value) { return Math.round((value || 0) * 100) }
function countBy(key, value) { return matrix.value.filter(row => row[key] === value).length }
function statusCount(status) { return matrix.value.filter(row => row.coverage_status === status).length }
function typeLabel(t) { return { qualification: '资格', technical: '技术', commercial: '商务', scoring: '评分', delivery: '交付', format: '格式' }[t] || t }
function riskLabel(r) { return { high: '高', medium: '中', low: '低' }[r] || r }
function coverageLabel(s) {
  return { covered: '已覆盖', partially_covered: '部分覆盖', missing: '缺失', conflicted: '冲突', pending_confirmation: '待确认' }[s] || s
}
</script>

<style scoped>
.evidence-page { max-width: 1500px; position: relative; }
.evidence-hero { display: flex; justify-content: space-between; gap: 20px; align-items: stretch; min-height: 180px; padding: 30px; margin-bottom: 16px; border-radius: 28px; color: white; background: linear-gradient(135deg, #0f172a 0%, #334155 58%, #94a3b8 100%); box-shadow: 0 28px 70px rgba(15, 23, 42, .2); }
.eyebrow { display: block; margin-bottom: 12px; font-size: 12px; font-weight: 900; opacity: .72; }
h2 { margin: 0; font-size: 40px; line-height: 1.08; color: white; }
.evidence-hero p { margin: 12px 0 0; max-width: 720px; color: rgba(255,255,255,.75); font-size: 15px; line-height: 1.7; }
.hero-score { min-width: 190px; border: 1px solid rgba(255,255,255,.22); border-radius: 24px; padding: 20px; background: rgba(255,255,255,.12); backdrop-filter: blur(18px); display: flex; flex-direction: column; justify-content: center; }
.hero-score span { color: rgba(255,255,255,.7); font-size: 12px; font-weight: 800; }
.hero-score strong { margin-top: 4px; font-size: 44px; line-height: 1; }
.hero-score small { margin-top: 8px; color: rgba(255,255,255,.74); }
.header { display: flex; justify-content: space-between; gap: 18px; align-items: center; margin-bottom: 14px; }
.stage-note { display: flex; flex-direction: column; gap: 4px; }
.stage-note strong { color: #111827; font-size: 16px; }
.stage-note span { color: #64748b; font-size: 13px; }
.header-actions { display: flex; gap: 10px; }
.btn-primary, .btn-secondary { padding: 10px 16px; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 800; }
.btn-primary { background: #111827; color: white; border: none; box-shadow: 0 12px 26px rgba(15,23,42,.18); }
.btn-secondary { background: white; color: #111827; border: 1px solid #dbe3ee; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 10px; margin-bottom: 14px; }
.metrics div { background: rgba(255,255,255,.88); border-radius: 18px; border: 1px solid #edf0f2; padding: 14px; box-shadow: 0 12px 28px rgba(15,23,42,.05); }
.metrics span { display: block; font-size: 12px; color: #667085; margin-bottom: 4px; }
.metrics strong { font-size: 24px; color: #111827; }
.evidence-stage { display: grid; grid-template-columns: minmax(0, 1fr) 390px; gap: 16px; align-items: start; }
.matrix-shell { background: rgba(255,255,255,.9); border: 1px solid rgba(226,232,240,.95); border-radius: 24px; box-shadow: 0 18px 45px rgba(15,23,42,.08); overflow: auto; max-height: calc(100vh - 312px); }
.matrix-table { width: 100%; border-collapse: collapse; min-width: 1300px; }
.matrix-table th, .matrix-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #edf0f2; font-size: 12px; vertical-align: top; }
.matrix-table th { position: sticky; top: 0; z-index: 1; background: rgba(248,250,252,.96); color: #475569; font-weight: 800; backdrop-filter: blur(12px); }
.matrix-table tr { cursor: pointer; }
.matrix-table tr:hover, .matrix-table tr.active { background: #f1f7ff; }
.req-cell { min-width: 260px; color: #243044; font-weight: 600; }
.quote-cell { min-width: 220px; color: #667085; }
.risk-tag, .coverage-tag { display: inline-flex; padding: 2px 8px; border-radius: 999px; font-size: 11px; white-space: nowrap; }
.risk-tag.high { background: #fde2e2; color: #9f1d1d; }
.risk-tag.medium { background: #fff4cc; color: #835b00; }
.risk-tag.low { background: #dcf7e6; color: #146c36; }
.coverage-tag.covered { background: #dcf7e6; color: #146c36; }
.coverage-tag.partially_covered { background: #e7f2ff; color: #0f4c81; }
.coverage-tag.missing { background: #fde2e2; color: #9f1d1d; }
.coverage-tag.conflicted { background: #fff4cc; color: #835b00; }
.coverage-tag.pending_confirmation { background: #f3e8ff; color: #6b21a8; }
.chain-panel { position: sticky; top: 88px; max-height: calc(100vh - 112px); overflow: auto; background: rgba(255,255,255,.92); border: 1px solid #dfe6ee; border-radius: 24px; box-shadow: 0 18px 48px rgba(15,23,42,.12); padding: 18px; }
.demo-focus {
  border-color: rgba(17,24,39,.3);
  box-shadow: 0 0 0 4px rgba(17,24,39,.08), 0 26px 70px rgba(15,23,42,.16);
}
.demo-focus::before {
  content: "Demo Focus";
  display: inline-flex;
  margin-bottom: 10px;
  padding: 5px 10px;
  border-radius: 999px;
  background: #111827;
  color: white;
  font-size: 11px;
  font-weight: 900;
}
.chain-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.chain-header span { display: block; margin-bottom: 3px; color: #94a3b8; font-size: 11px; font-weight: 900; text-transform: uppercase; }
.chain-header h3 { margin: 0; font-size: 20px; color: #111827; }
.btn-icon { width: 32px; height: 32px; border-radius: 50%; border: 1px solid #d0d7de; background: white; cursor: pointer; font-size: 18px; }
.chain-path { display: flex; align-items: center; gap: 8px; padding: 10px; margin-bottom: 12px; border-radius: 16px; background: #f8fafc; color: #475569; font-size: 12px; font-weight: 800; }
.chain-path i { flex: 1; height: 1px; background: #cbd5e1; }
section { border-top: 1px solid #edf0f2; padding-top: 12px; margin-top: 12px; }
section h4 { margin: 0 0 8px; color: #344054; font-size: 14px; }
section p { margin: 0; color: #475467; font-size: 13px; line-height: 1.6; }
blockquote { margin: 0; padding: 12px 14px; background: #f8fafc; border-left: 3px solid #111827; border-radius: 12px; color: #344054; font-size: 13px; line-height: 1.6; }
.source-line { margin-bottom: 8px; color: #667085; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.chips span { background: #eef2f7; color: #344054; padding: 4px 8px; border-radius: 999px; font-size: 12px; }
.material-card, .issue-card { border: 1px solid #edf0f2; border-radius: 14px; padding: 10px; margin-bottom: 8px; background: #fff; }
.material-card strong, .issue-card strong { display: block; font-size: 13px; color: #243044; }
.material-card span, .issue-card span { display: block; margin-top: 4px; font-size: 12px; color: #667085; }
.generated { white-space: pre-wrap; background: #fafafa; padding: 10px; border-radius: 12px; }
.empty-small { color: #98a2b3; font-size: 13px; }
.chain-empty { min-height: 420px; display: flex; flex-direction: column; justify-content: center; gap: 10px; color: #64748b; }
.chain-empty span { color: #94a3b8; font-size: 12px; font-weight: 900; }
.chain-empty strong { color: #111827; font-size: 22px; line-height: 1.25; }
.chain-empty p { margin: 0; line-height: 1.7; }
@media (max-width: 900px) {
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .header, .evidence-hero { flex-direction: column; }
  .evidence-stage { grid-template-columns: 1fr; }
  .chain-panel { position: static; max-height: none; }
  h2 { font-size: 32px; }
}
</style>
