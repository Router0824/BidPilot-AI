<template>
  <div class="outline-page">
    <div class="header">
      <h2>章节编写</h2>
      <router-link :to="`/project/${projectId}`">交付检查与 Word 导出</router-link>
    </div>

    <div class="layout">
      <div class="outline-panel">
        <h3>章节目录</h3>
        <form class="new-section" @submit.prevent="addSection">
          <input v-model="newTitle" placeholder="新章节名称" aria-label="新章节名称" maxlength="255" required />
          <button class="btn-secondary" :disabled="addingSection">添加章节</button>
        </form>
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
            <button class="btn-primary" @click="generateDraft" :disabled="generating || saving || protectedContent || dirty || sectionLoading">
              {{ generating ? '生成中...' : '生成章节初稿' }}
            </button>
          </div>
          <div class="editing-toolbar">
            <label><input type="checkbox" :checked="protectedContent" @change="toggleProtection" :disabled="saving || generating || sectionLoading" />保护人工内容</label>
            <button class="btn-secondary" @click="editing = !editing" :disabled="sectionLoading">{{ editing ? '预览正文' : '编辑正文' }}</button>
            <button class="btn-primary" @click="saveDraft" :disabled="saving || generating || sectionLoading || !dirty">{{ saving ? '保存中...' : '保存草稿' }}</button>
            <span role="status">{{ dirty ? '有未保存的修改' : saveMessage || '已同步' }}</span>
          </div>
          <p v-if="editorError" role="alert" class="editor-error">{{ editorError }}</p>
          <textarea v-if="editing" v-model="draftContent" class="content-editor" aria-label="章节正文" :disabled="sectionLoading || saving || generating" />
          <details v-if="editing" class="material-picker" @toggle="loadMaterials">
            <summary>引用企业材料 · 已选 {{ knowledgeIds.length }} 项</summary>
            <div v-for="id in knowledgeIds.filter(id => !materials.some(m => m.id === id))" :key="id">
              {{ citations.find(c => c.chunk_id === id)?.source || '未载入的引用' }}
              <button class="btn-secondary" @click="knowledgeIds = knowledgeIds.filter(value => value !== id)" :disabled="saving || generating">移除引用</button>
            </div>
            <label v-for="material in materials" :key="material.id">
              <input type="checkbox" :value="material.id" v-model="knowledgeIds" :disabled="!material.is_audited || material.is_expired || saving || generating || sectionLoading" />
              <span>{{ material.material_name }} · 第 {{ material.source_page || '?' }} 页 <small>{{ material.is_expired ? '已过期' : material.is_audited ? '已审核' : '待审核' }}</small></span>
            </label>
            <router-link :to="`/project/${projectId}/knowledge`">管理企业材料</router-link>
          </details>
          <div v-if="visibleAgentProgress.length" class="agent-progress">
            <div v-for="event in visibleAgentProgress.slice(0, 3)" :key="event.id" class="agent-progress-item">
              <span></span>
              <strong>{{ event.title }}</strong>
              <em>{{ event.detail || event.node_name }}</em>
            </div>
          </div>

          <div v-if="draftContent && !editing" class="draft-content">
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

          <div v-else-if="!generating && !editing" class="empty-editor">
            <p>选择左侧章节后点击"生成章节初稿"</p>
          </div>
        </template>
        <div v-else class="empty-editor"><p>请从左侧选择一个章节</p></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useAppStore } from '../stores/app'
import api from '../api'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const outline = ref([])
const loading = ref(true)
const selectedSection = ref(null)
const draftContent = ref('')
const citations = ref([])
const generating = ref(false)
const newTitle = ref(''), addingSection = ref(false)
const saving = ref(false), editing = ref(true), protectedContent = ref(false), sectionLoading = ref(false)
const savedContent = ref(''), currentVersionId = ref(null), saveMessage = ref(''), editorError = ref('')
const materials = ref([]), knowledgeIds = ref([]), savedKnowledgeIds = ref('[]')
const dirty = computed(() => draftContent.value !== savedContent.value || JSON.stringify(knowledgeIds.value) !== savedKnowledgeIds.value)
let selectionRequest = 0
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
  const all = outline.value.flatMap(s => [s, ...(s.children || [])])
  const initial = all.find(s => s.id === route.query.section) || all[0]
  if (initial) await selectSection(initial)
  window.addEventListener('beforeunload', beforeUnload)
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
  window.removeEventListener('beforeunload', beforeUnload)
  source?.close()
  clearTimers.forEach(timer => clearTimeout(timer))
  clearTimers.clear()
})

const renderedContent = computed(() => {
  if (!draftContent.value) return ''
  return draftContent.value
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
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
  if (generating.value || saving.value) return
  if (dirty.value && !window.confirm('当前修改尚未保存，确定放弃修改？')) return
  const request = ++selectionRequest
  sectionLoading.value = true
  selectedSection.value = s
  draftContent.value = ''
  savedContent.value = ''
  knowledgeIds.value = []; savedKnowledgeIds.value = '[]'
  currentVersionId.value = null
  protectedContent.value = false
  editorError.value = ''; saveMessage.value = ''
  citations.value = []
  versions.value = []
  compareMode.value = false
  try {
    const [response, history] = await Promise.all([
      api.get(`/projects/${projectId}/outline/sections/${s.id}/editor`),
      store.fetchDraftVersions(projectId, s.id),
    ])
    if (request !== selectionRequest) return
    const data = response.data.data
    draftContent.value = data.content || ''; savedContent.value = draftContent.value
    currentVersionId.value = data.version_id; protectedContent.value = data.protected
    citations.value = data.citations || []; versions.value = history
    knowledgeIds.value = [...new Set(citations.value.map(c => c.chunk_id).filter(Boolean))]
    savedKnowledgeIds.value = JSON.stringify(knowledgeIds.value)
    rightVersionId.value = data.version_id
    leftVersionId.value = history.find(v => v.id !== data.version_id)?.id || data.version_id
  } catch (e) { editorError.value = e.response?.data?.detail || '章节加载失败，请重新选择章节' }
  finally { if (request === selectionRequest) sectionLoading.value = false }
}

async function saveDraft() {
  saving.value = true; editorError.value = ''
  try {
    const { data } = await api.put(`/projects/${projectId}/outline/sections/${selectedSection.value.id}/editor`,
      { content: draftContent.value, expected_version_id: currentVersionId.value, knowledge_ids: knowledgeIds.value })
    currentVersionId.value = data.data.version_id; protectedContent.value = true
    savedContent.value = draftContent.value; saveMessage.value = '已保存并保护'
    savedKnowledgeIds.value = JSON.stringify(knowledgeIds.value)
    selectedSection.value.status = 'drafted'
    versions.value = await store.fetchDraftVersions(projectId, selectedSection.value.id)
    citations.value = versions.value.find(v => v.id === currentVersionId.value)?.citations || []
    rightVersionId.value = currentVersionId.value; leftVersionId.value = versions.value[1]?.id || currentVersionId.value
  } catch (e) { editorError.value = e.response?.data?.detail || '保存失败，正文仍保留在编辑器中' }
  finally { saving.value = false }
}
async function addSection() {
  if (!newTitle.value.trim()) return
  addingSection.value = true
  try {
    await api.post(`/projects/${projectId}/outline/sections`, { title: newTitle.value.trim(), level: 1 })
    outline.value = await store.fetchOutline(projectId)
    newTitle.value = ''
  } catch { /* Request feedback displays failure. */ }
  finally { addingSection.value = false }
}
async function loadMaterials(event) {
  if (!event.target.open) return
  try { materials.value = await store.fetchKnowledge() }
  catch { editorError.value = '材料加载失败，请重新打开引用列表' }
}
async function toggleProtection(event) {
  const next = event.target.checked
  if (!next && !window.confirm('解除保护后，生成和自动修正可以更新本章。确定解除？')) { event.target.checked = true; return }
  saving.value = true
  try {
    await api.put(`/projects/${projectId}/outline/sections/${selectedSection.value.id}/protection`, { protected: next })
    protectedContent.value = next
  } catch { event.target.checked = protectedContent.value }
  finally { saving.value = false }
}
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(() => !dirty.value || window.confirm('当前修改尚未保存，确定离开？'))
watch(() => route.query.section, id => {
  const section = outline.value.flatMap(s => [s, ...(s.children || [])]).find(s => s.id === id)
  if (section) selectSection(section)
})

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
    if (result.skipped) { editorError.value = result.reason; return }
    draftContent.value = ''
    citations.value = []
    versions.value = await store.fetchDraftVersions(projectId, sectionId)
    if (versions.value.length) {
      draftContent.value = versions.value[0].content
      savedContent.value = draftContent.value
      currentVersionId.value = versions.value[0].id
      citations.value = versions.value[0].citations || []
      knowledgeIds.value = [...new Set(citations.value.map(c => c.chunk_id).filter(Boolean))]
      savedKnowledgeIds.value = JSON.stringify(knowledgeIds.value)
      rightVersionId.value = versions.value[0].id
      leftVersionId.value = versions.value[1]?.id || versions.value[0].id
    }
    sectionRef.status = 'drafted'
  } catch (e) {
    editorError.value = e.response?.data?.detail || '生成失败'
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
  if (left.length * right.length > 1000000) {
    return Array.from({ length: Math.max(left.length, right.length) }, (_, i) => ({
      type: left[i] === right[i] ? 'same' : 'changed', left: left[i] || '', right: right[i] || '',
    }))
  }
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
.new-section { display: flex; gap: 6px; margin-bottom: 12px; }
.new-section input { width: 0; flex: 1; min-width: 0; padding: 8px; border: 1px solid #ccd3dc; border-radius: 6px; }
.new-section button { flex-shrink: 0; }
.editing-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; }
.editing-toolbar label { display: flex; align-items: center; gap: 6px; }
.content-editor { width: 100%; box-sizing: border-box; min-height: 55vh; resize: vertical; padding: 18px; border: 1px solid #ccd3dc; border-radius: 6px; font: inherit; font-size: 15px; line-height: 1.9; color: #252b33; background: #fff; }
.editor-error { color: #b42318; font-size: 13px; }
.material-picker { padding: 14px 0; font-size: 13px; }
.material-picker summary { cursor: pointer; margin-bottom: 10px; }
.material-picker label { display: flex; gap: 8px; align-items: baseline; padding: 8px 0; }
.material-picker small { color: #637080; }
.editor-panel { min-width: 0; }
.version-toolbar { flex-wrap: wrap; }
.draft-body { overflow-wrap: anywhere; }
@media (max-width: 800px) { .layout { grid-template-columns: minmax(0, 1fr) !important; } .outline-tree { max-height: 220px !important; } .editor-header { flex-wrap: wrap; gap: 12px; } .diff-grid { grid-template-columns: minmax(0, 1fr) !important; } }
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
.diff-line.changed { background: #fff5db; color: #624500; }
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
