<template>
  <section class="workbench" aria-label="项目待办">
    <header><h3>交付待办</h3><button @click="load" :disabled="loading">{{ loading ? '刷新中' : '刷新' }}</button></header>
    <p v-if="error" role="alert">{{ error }} <button @click="load">重试</button></p>
    <template v-if="summary">
      <div class="metrics">
        <div><span>距离截标</span><strong>{{ remaining }}</strong></div>
        <div><span>章节完成</span><strong>{{ summary.completed_sections }} / {{ summary.section_count }}</strong></div>
        <div><span>待补材料</span><strong>{{ summary.missing_materials }}</strong></div>
        <div><span>待确认</span><strong>{{ summary.pending_confirmations }}</strong></div>
      </div>
      <nav aria-label="待办分类">
        <button v-for="item in filters" :key="item.key" :aria-pressed="filter === item.key" @click="filter = item.key">{{ item.label }}</button>
      </nav>
      <ul v-if="tasks.length" class="tasks">
        <li v-for="task in tasks" :key="task.id">
          <span :class="['risk', task.risk]">{{ task.risk === 'high' ? '优先' : '待办' }}</span>
          <router-link :to="`/project/${projectId}/${task.target}`">{{ task.title }}</router-link>
        </li>
      </ul>
      <p v-else>此分类暂无待办。</p>
      <details class="delivery" @toggle="onDeliveryToggle">
        <summary>交付与 Word 导出 · {{ summary.tasks.length }} 项待处理</summary>
        <div class="delivery-form">
          <label>投标单位<input v-model="company" maxlength="255" /></label>
          <label>企业 Word 模板<input type="file" accept=".docx" @change="uploadTemplate" :disabled="busy" /></label>
          <span>{{ templateName || '使用默认模板' }}</span>
          <div class="download-actions">
            <button @click="downloadSample" :disabled="busy">下载模板范本</button>
            <button v-if="templateName" @click="resetTemplate" :disabled="busy">恢复默认模板</button>
          </div>
          <p v-if="templateInfo?.error" role="alert">{{ templateInfo.error }}</p>
          <p v-else-if="templateInfo">已识别：{{ templateInfo.fields?.map(fieldLabel).join('、') || '无替换字段' }}；{{ templateInfo.insertion === 'placeholder' ? '正文插入指定位置' : '正文追加到模板末尾' }}。</p>
          <div class="download-actions">
            <button @click="download('draft')" :disabled="busy">下载工作草稿</button>
            <button @click="download('final')" :disabled="busy || !summary.export_ready">下载正式稿</button>
          </div>
          <p v-if="!summary.export_ready">正式稿需完成待办、补齐引用并通过审查。</p>
        </div>
      </details>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
const props = defineProps({ projectId: { type: String, required: true } })
const summary = ref(null), error = ref(''), loading = ref(false), filter = ref('all')
const busy = ref(false), company = ref(''), templateName = ref('')
const templateInfo = ref(null)
function fieldLabel(value) { return { '{{project_name}}': '项目名称', '{{company_name}}': '投标单位', '{{content}}': '正文位置' }[value] || value }
const filters = [{ key: 'all', label: '全部待办' }, { key: 'material', label: '补件' }, { key: 'section', label: '章节' }, { key: 'requirement', label: '要求' }, { key: 'confirmation', label: '确认' }, { key: 'review', label: '审查' }, { key: 'citation', label: '引用' }]
const tasks = computed(() => (summary.value?.tasks || []).filter(t => filter.value === 'all' || t.kind === filter.value))
const remaining = computed(() => {
  const h = summary.value?.remaining_hours
  return h == null ? '未设置' : h < 0 ? `已逾期 ${Math.ceil(-h / 24)} 天` : h < 24 ? `${Math.ceil(h)} 小时` : `${Math.ceil(h / 24)} 天`
})
async function load() {
  loading.value = true; error.value = ''
  try { summary.value = (await api.get(`/projects/${props.projectId}/workbench`)).data.data }
  catch (e) { error.value = e.response?.data?.detail || '待办加载失败' }
  finally { loading.value = false }
}
async function onDeliveryToggle(event) {
  if (!event.target.open) return
  try {
    const { data } = await api.get(`/projects/${props.projectId}/delivery/profile`)
    company.value ||= data.data.company_name
    templateName.value = data.data.template_name
    templateInfo.value = data.data.template_info
    await load()
  } catch { /* Request feedback displays failure. */ }
}
async function uploadTemplate(event) {
  const file = event.target.files[0]
  if (!file) return
  busy.value = true
  try {
    const body = new FormData(); body.append('file', file)
    const { data } = await api.post(`/projects/${props.projectId}/delivery/template`, body)
    templateName.value = data.data.template_name
    templateInfo.value = data.data.template_info
  } catch { /* Request feedback displays failure. */ }
  finally { busy.value = false; event.target.value = '' }
}
async function download(mode) {
  busy.value = true; error.value = ''
  try {
    const { data } = await api.post(`/projects/${props.projectId}/delivery/download`, { company_name: company.value, mode }, { responseType: 'blob' })
    const url = URL.createObjectURL(data), link = document.createElement('a')
    link.href = url; link.download = `${mode === 'draft' ? '工作草稿' : '技术标'}.docx`
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch (e) {
    try { error.value = JSON.parse(await e.response.data.text()).detail }
    catch { error.value = '导出失败，请稍后重试' }
  } finally { busy.value = false }
}
async function downloadSample() {
  busy.value = true
  try {
    const { data } = await api.get(`/projects/${props.projectId}/delivery/template/sample`, { responseType: 'blob' })
    const url = URL.createObjectURL(data), link = document.createElement('a')
    link.href = url; link.download = '企业投标模板.docx'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch { error.value = '模板下载失败，请重试' }
  finally { busy.value = false }
}
async function resetTemplate() {
  if (!window.confirm('恢复默认模板？已下载的文档不会受到影响。')) return
  busy.value = true
  try {
    await api.delete(`/projects/${props.projectId}/delivery/template`)
    templateName.value = ''; templateInfo.value = null
  } catch { error.value = '模板重置失败，请重试' }
  finally { busy.value = false }
}
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.workbench { padding: 20px 0; margin-bottom: 20px; border-block: 1px solid #dce1e7; color: #20252d; }
header { display: flex; justify-content: space-between; align-items: center; }
h3 { margin: 0; font-size: 20px; }
button { padding: 8px 12px; border: 1px solid #dce1e7; background: white; color: #25313e; border-radius: 6px; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
button[aria-pressed=true] { background: #20252d; color: white; }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 22px 0; }
.metrics span, .metrics strong { display: block; }
.metrics span { color: #626b76; font-size: 13px; }
.metrics strong { font-size: 23px; margin-top: 6px; font-variant-numeric: tabular-nums; }
nav, .download-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.tasks { list-style: none; padding: 0; max-height: 350px; overflow: auto; }
.tasks li { display: flex; gap: 12px; align-items: baseline; padding: 12px 0; border-bottom: 1px solid #e5e7eb; }
.tasks a { color: #245b91; overflow-wrap: anywhere; text-decoration: none; line-height: 1.6; }
.risk { color: #586473; font-size: 12px; flex-shrink: 0; }
.risk.high { color: #ad3035; }
.delivery { margin-top: 18px; }
summary { cursor: pointer; font-weight: 600; padding: 12px 0; }
.delivery-form { display: grid; gap: 12px; padding: 12px 0; }
label { display: grid; gap: 6px; font-size: 13px; }
input { padding: 10px; max-width: 100%; box-sizing: border-box; border: 1px solid #ccd2da; border-radius: 6px; }
p { font-size: 13px; line-height: 1.6; color: #606976; }
@media(max-width: 600px) { .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
