<template>
  <div class="outline-page">
    <div class="header">
      <h2>技术标大纲</h2>
      <button class="btn-primary" @click="exportOutline">导出大纲</button>
    </div>

    <div class="layout">
      <div class="outline-panel">
        <h3>章节目录</h3>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else class="outline-tree">
          <div v-for="s in outline" :key="s.id" class="outline-node" :style="{ paddingLeft: (s.level - 1) * 24 + 'px' }">
            <div :class="['node-item', { active: selectedSection?.id === s.id }]" @click="selectSection(s)">
              <span class="node-title">{{ s.title }}</span>
              <span :class="['node-status', s.status]">{{ s.status === 'drafted' ? '已生成' : '待生成' }}</span>
            </div>
            <div v-for="child in s.children" :key="child.id" class="outline-node" :style="{ paddingLeft: (child.level - 1) * 24 + 'px' }">
              <div :class="['node-item', { active: selectedSection?.id === child.id }]" @click="selectSection(child)">
                <span class="node-title">{{ child.title }}</span>
                <span :class="['node-status', child.status]">{{ child.status === 'drafted' ? '已生成' : '待生成' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="editor-panel">
        <template v-if="selectedSection">
          <div class="editor-header">
            <h3>{{ selectedSection.title }}</h3>
            <button class="btn-primary" @click="generateDraft" :disabled="generating">
              {{ generating ? '生成中...' : '生成章节初稿' }}
            </button>
          </div>
          <div v-if="visibleAgentProgress.length" class="agent-progress">
            <div v-for="event in visibleAgentProgress.slice(0, 3)" :key="event.id" class="agent-progress-item">
              <span></span>
              <strong>{{ event.title }}</strong>
              <em>{{ event.detail || event.node_name }}</em>
            </div>
          </div>

          <div v-if="draftContent" class="draft-content">
            <div v-if="versions.length > 1" class="version-toolbar">
              <label>版本对比</label>
              <select v-model="leftVersionId">
                <option v-for="v in versions" :key="v.id" :value="v.id">{{ versionLabel(v) }}</option>
              </select>
              <select v-model="rightVersionId">
                <option v-for="v in versions" :key="v.id" :value="v.id">{{ versionLabel(v) }}</option>
              </select>
              <button class="btn-secondary" @click="compareMode = !compareMode">{{ compareMode ? '正文视图' : '对比视图' }}</button>
            </div>
            <div v-if="compareMode && versions.length > 1" class="diff-grid">
              <div class="diff-pane">
                <h4>旧版本</h4>
                <div v-for="(row, i) in diffRows" :key="`l-${i}`" :class="['diff-line', row.type]">{{ row.left }}</div>
              </div>
              <div class="diff-pane">
                <h4>新版本</h4>
                <div v-for="(row, i) in diffRows" :key="`r-${i}`" :class="['diff-line', row.type]">{{ row.right }}</div>
              </div>
            </div>
            <template v-else>
            <div class="draft-body" v-html="renderedContent"></div>

            <div v-if="citations.length" class="citations">
              <h4>引用来源</h4>
              <div v-for="(c, i) in citations" :key="i" class="citation-item">
                <span class="cite-source">{{ c.source }}</span>
                <span class="cite-page">第{{ c.page }}页</span>
                <span :class="['cite-status', c.status]">{{ c.status === 'verified' ? '已审核' : '未验证' }}</span>
                <span class="cite-snippet">{{ c.snippet }}</span>
              </div>
            </div>
            </template>
          </div>

          <div v-else-if="!generating" class="empty-editor">
            <p>选择左侧章节后点击"生成章节初稿"</p>
          </div>
        </template>
        <div v-else class="empty-editor"><p>请从左侧选择一个章节</p></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const outline = ref([])
const loading = ref(true)
const selectedSection = ref(null)
const draftContent = ref('')
const citations = ref([])
const generating = ref(false)
const versions = ref([])
const compareMode = ref(false)
const leftVersionId = ref('')
const rightVersionId = ref('')
const progressBySection = ref({})
const activeGenerationSectionId = ref('')
const clearTimers = new Map()
let source = null

onMounted(async () => {
  outline.value = await store.fetchOutline(projectId)
  loading.value = false
  source = new EventSource(store.workflowStreamUrl(projectId))
  source.addEventListener('agent.progress', (event) => {
    const payload = JSON.parse(event.data)
    if (!activeGenerationSectionId.value || payload.node_name !== 'generate_draft') return
    const sectionId = activeGenerationSectionId.value
    payload.id = `${payload.created_at}-${payload.phase}-${payload.node_name || ''}`
    const next = [payload, ...(progressBySection.value[sectionId] || [])].slice(0, 12)
    progressBySection.value = { ...progressBySection.value, [sectionId]: next }
    if (payload.phase?.includes('done') || payload.phase?.includes('error')) {
      scheduleProgressClear(sectionId)
    }
  })
  source.onerror = () => {
    source?.close()
    source = null
  }
})

onUnmounted(() => {
  source?.close()
  clearTimers.forEach(timer => clearTimeout(timer))
  clearTimers.clear()
})

const renderedContent = computed(() => {
  if (!draftContent.value) return ''
  return draftContent.value
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/### (.+)/g, '<h4>$1</h4>')
    .replace(/## (.+)/g, '<h3>$1</h3>')
    .replace(/【(.+?)】/g, '<span class="highlight">【$1】</span>')
})

const diffRows = computed(() => {
  const left = versions.value.find(v => v.id === leftVersionId.value)?.content || ''
  const right = versions.value.find(v => v.id === rightVersionId.value)?.content || ''
  return buildLineDiff(left, right)
})

const visibleAgentProgress = computed(() => {
  if (!selectedSection.value) return []
  return progressBySection.value[selectedSection.value.id] || []
})

async function selectSection(s) {
  selectedSection.value = s
  draftContent.value = ''
  citations.value = []
  versions.value = []
  compareMode.value = false
  if (s.status === 'drafted') {
    versions.value = await store.fetchDraftVersions(projectId, s.id)
    if (versions.value.length) {
      draftContent.value = versions.value[0].content
      citations.value = versions.value[0].citations || []
      rightVersionId.value = versions.value[0].id
      leftVersionId.value = versions.value[1]?.id || versions.value[0].id
    }
  }
}

async function generateDraft() {
  if (!selectedSection.value) return
  const sectionId = selectedSection.value.id
  const sectionRef = selectedSection.value
  activeGenerationSectionId.value = sectionId
  clearTimers.get(sectionId) && clearTimeout(clearTimers.get(sectionId))
  progressBySection.value = { ...progressBySection.value, [sectionId]: [] }
  generating.value = true
  try {
    const result = await store.generateDraft(projectId, sectionId)
    draftContent.value = ''
    citations.value = []
    versions.value = await store.fetchDraftVersions(projectId, sectionId)
    if (versions.value.length) {
      draftContent.value = versions.value[0].content
      citations.value = versions.value[0].citations || []
      rightVersionId.value = versions.value[0].id
      leftVersionId.value = versions.value[1]?.id || versions.value[0].id
    }
    sectionRef.status = 'drafted'
  } finally {
    generating.value = false
    scheduleProgressClear(sectionId)
    if (activeGenerationSectionId.value === sectionId) activeGenerationSectionId.value = ''
  }
}

async function exportOutline() {
  await store.exportData(projectId, 'outline', 'docx')
  alert('导出完成')
}

function versionLabel(v) {
  return `${new Date(v.created_at).toLocaleString('zh-CN')} · ${v.model_name || 'manual'}`
}

function buildLineDiff(leftText, rightText) {
  const left = leftText.split('\n')
  const right = rightText.split('\n')
  const dp = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0))
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      dp[i][j] = left[i] === right[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const rows = []
  let i = 0
  let j = 0
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      rows.push({ type: 'same', left: left[i], right: right[j] })
      i += 1
      j += 1
    } else if (j < right.length && (i === left.length || dp[i][j + 1] >= dp[i + 1]?.[j])) {
      rows.push({ type: 'added', left: '', right: right[j] })
      j += 1
    } else if (i < left.length) {
      rows.push({ type: 'removed', left: left[i], right: '' })
      i += 1
    }
  }
  return rows
}

function scheduleProgressClear(sectionId) {
  if (clearTimers.has(sectionId)) clearTimeout(clearTimers.get(sectionId))
  const timer = setTimeout(() => {
    const next = { ...progressBySection.value }
    delete next[sectionId]
    progressBySection.value = next
    clearTimers.delete(sectionId)
  }, 5000)
  clearTimers.set(sectionId, timer)
}
</script>

<style scoped>
.outline-page { max-width: 1400px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { margin: 0; color: #1a1a2e; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 8px 12px; background: #eee; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; }
.outline-panel { background: white; border-radius: 10px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.outline-panel h3 { margin: 0 0 12px; font-size: 15px; color: #1a1a2e; }
.outline-tree { max-height: 70vh; overflow-y: auto; }
.node-item {
  padding: 8px 12px; border-radius: 6px; cursor: pointer; display: flex;
  justify-content: space-between; align-items: center; font-size: 13px; transition: background 0.15s;
  border: 1px solid transparent;
}
.node-item:hover { background: #f5f6fa; }
.node-item.active { background: #e8f4fd; border-color: #3498db; color: #0f3460; }
.node-title { flex: 1; }
.node-status { font-size: 11px; padding: 2px 6px; border-radius: 8px; }
.node-status.drafted { background: #d4edda; color: #155724; }
.node-status.pending { background: #f0f0f0; color: #999; }
.editor-panel { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.editor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.editor-header h3 { margin: 0; font-size: 16px; color: #1a1a2e; }
.agent-progress { margin-bottom: 14px; background: #f8fbff; border: 1px solid #dcecff; border-radius: 8px; overflow: hidden; }
.agent-progress-item { display: grid; grid-template-columns: 10px minmax(120px, 180px) 1fr; gap: 8px; align-items: center; padding: 8px 10px; font-size: 12px; border-bottom: 1px solid #eaf3ff; }
.agent-progress-item:last-child { border-bottom: none; }
.agent-progress-item span { width: 7px; height: 7px; border-radius: 50%; background: #3498db; }
.agent-progress-item strong { color: #1a1a2e; }
.agent-progress-item em { color: #667085; font-style: normal; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-content { max-height: 65vh; overflow-y: auto; }
.version-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; font-size: 13px; }
.version-toolbar select { min-width: 180px; padding: 7px 8px; border: 1px solid #ddd; border-radius: 6px; font-size: 12px; }
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.diff-pane { border: 1px solid #eee; border-radius: 8px; overflow: hidden; background: #fff; }
.diff-pane h4 { margin: 0; padding: 10px 12px; background: #fafafa; font-size: 13px; color: #555; }
.diff-line { min-height: 20px; padding: 4px 10px; white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; border-top: 1px solid #f5f5f5; }
.diff-line.added { background: #eaf7ee; color: #17633a; }
.diff-line.removed { background: #fdecec; color: #8a1f1f; }
.diff-line.same { color: #444; }
.draft-body { line-height: 1.8; font-size: 14px; color: #333; }
.draft-body :deep(.highlight) { background: #fff3cd; padding: 1px 2px; border-radius: 2px; }
.draft-body :deep(h3) { font-size: 18px; margin: 16px 0 8px; color: #1a1a2e; }
.draft-body :deep(h4) { font-size: 15px; margin: 12px 0 6px; color: #333; }
.citations { margin-top: 24px; border-top: 1px solid #eee; padding-top: 16px; }
.citations h4 { margin: 0 0 12px; font-size: 14px; color: #666; }
.citation-item { padding: 8px 0; border-bottom: 1px solid #f5f5f5; font-size: 12px; display: flex; gap: 10px; align-items: center; }
.cite-source { font-weight: 500; color: #333; }
.cite-page { color: #999; }
.cite-status { padding: 1px 6px; border-radius: 8px; font-size: 11px; }
.cite-status.verified { background: #d4edda; color: #155724; }
.cite-status.unverified { background: #fff3cd; color: #856404; }
.cite-snippet { color: #999; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-editor { display: flex; align-items: center; justify-content: center; min-height: 300px; color: #999; font-size: 14px; }
.loading { text-align: center; padding: 40px; color: #999; }
</style>
