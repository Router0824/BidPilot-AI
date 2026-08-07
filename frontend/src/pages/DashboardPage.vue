<template>
  <div class="dashboard">
    <div class="hero-strip">
      <div>
        <span class="eyebrow">BID OPERATIONS</span>
        <h2>项目工作台</h2>
      </div>
      <button class="btn-primary" @click="showNewProject = true">新建项目</button>
    </div>

    <div class="filters toolbar">
      <select v-model="filterStatus">
        <option value="">全部状态</option>
        <option value="active">进行中</option>
        <option value="completed">已完成</option>
        <option value="cancelled">已取消</option>
      </select>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else class="project-grid">
      <div v-for="p in projects" :key="p.id" class="project-card" @click="openProject(p.id)">
        <div class="card-header">
          <h3>{{ p.name }}</h3>
          <span :class="['status', p.workflow_status]">{{ statusLabel(p.workflow_status) }}</span>
        </div>
        <div class="metric-line">
          <span><b>{{ p.document_count }}</b> 文件</span>
          <span><b>{{ p.requirement_count }}</b> 要求</span>
          <span class="risk-high"><b>{{ p.high_risk_count }}</b> 高风险</span>
        </div>
        <div class="card-body">
          <div class="info-row"><span>类型</span><span>{{ p.project_type }}</span></div>
          <div class="info-row"><span>负责人</span><span>{{ p.owner_name }}</span></div>
          <div class="info-row"><span>截止日期</span><span>{{ fmtDate(p.deadline) }}</span></div>
          <div class="info-row"><span>待确认</span><span>{{ p.pending_confirmation_count }}</span></div>
        </div>
      </div>
      <div v-if="projects.length === 0" class="empty">
        {{ filterStatus ? '当前状态下暂无项目' : '暂无项目，点击"新建项目"开始' }}
      </div>
    </div>

    <div v-if="showNewProject" class="modal-overlay" @click.self="showNewProject = false">
      <div class="modal">
        <h3>新建项目</h3>
        <div class="form-group">
          <label>项目名称 *</label>
          <input v-model="newProject.name" placeholder="例：某智能管理平台建设项目" />
        </div>
        <div class="form-group">
          <label>项目类型</label>
          <select v-model="newProject.project_type">
            <option value="software">软件类</option>
            <option value="ai">AI 类</option>
            <option value="digital">数字化平台</option>
            <option value="other">其他</option>
          </select>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea v-model="newProject.description" rows="2"></textarea>
        </div>
        <div class="form-group">
          <label>投标截止日期</label>
          <input type="datetime-local" v-model="newProject.deadline" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showNewProject = false">取消</button>
          <button class="btn-primary" @click="createProject" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const projects = ref([])
const loading = ref(false)
const filterStatus = ref('')
const showNewProject = ref(false)
const creating = ref(false)
const newProject = ref({ name: '', project_type: 'software', description: '', deadline: '' })

onMounted(loadProjects)
watch(filterStatus, loadProjects)

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await store.fetchProjects({ status: filterStatus.value })
  } finally {
    loading.value = false
  }
}

function statusLabel(s) {
  const map = { created: '已创建', files_uploaded: '已上传', parsing: '解析中', parsed: '已解析',
    extracting_requirements: '提取中', waiting_for_confirmation: '等待确认', facts_confirmed: '已确认',
    matrix_generated: '矩阵已生成', outline_generated: '大纲已生成', drafting: '生成中',
    draft_completed: '草稿完成', reviewing: '审查中', review_completed: '审查完成',
    ready_to_export: '待导出', exported: '已导出', failed: '失败', cancelled: '已取消', retrying: '重试中' }
  return map[s] || s
}

function fmtDate(d) { return d ? new Date(d).toLocaleDateString('zh-CN') : '-' }

async function createProject() {
  if (!newProject.value.name) return
  creating.value = true
  try {
    await store.createProject({...newProject.value})
    showNewProject.value = false
    newProject.value = { name: '', project_type: 'software', description: '', deadline: '' }
    await loadProjects()
  } finally {
    creating.value = false
  }
}

function openProject(id) {
  store.currentProject = projects.value.find(p => p.id === id)
  router.push(`/project/${id}`)
}
</script>

<style scoped>
.dashboard { max-width: 1260px; }
.hero-strip {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  padding: 26px 28px;
  border: 1px solid rgba(255,255,255,.86);
  border-radius: 8px;
  background:
    linear-gradient(120deg, rgba(255,255,255,.92), rgba(255,255,255,.66)),
    radial-gradient(circle at 82% 28%, rgba(37,99,235,.12), transparent 28%);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(24px) saturate(1.16);
  overflow: hidden;
}
.hero-strip::after {
  content: "";
  position: absolute;
  right: 26px;
  bottom: 18px;
  width: 96px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(17,24,39,.22));
  transform: none;
  pointer-events: none;
}
.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: .12em;
}
h2 { margin: 0; font-size: 28px; color: var(--ink); }
.btn-primary {
  padding: 10px 20px; background: #0f3460; color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.btn-secondary { padding: 10px 20px; background: #eee; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.filters { margin-bottom: 16px; }
.toolbar {
  display: inline-flex;
  padding: 6px;
  border: 1px solid rgba(255,255,255,.86);
  background: rgba(255,255,255,.68);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(17,24,39,.06);
  backdrop-filter: blur(18px);
}
.filters select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.project-card {
  position: relative;
  background: rgba(255,255,255,.82); border-radius: 8px; padding: 18px; cursor: pointer;
  border: 1px solid rgba(255,255,255,.86);
  box-shadow: var(--shadow-soft);
  transition: box-shadow 0.22s, transform .18s, border-color .18s, background .18s;
  backdrop-filter: blur(20px) saturate(1.12);
  overflow: hidden;
}
.project-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #111827, #9ca3af, transparent);
}
.project-card:hover { box-shadow: var(--shadow-lift); transform: translateY(-3px); border-color: rgba(17,24,39,.10); background: rgba(255,255,255,.94); }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.card-header h3 { margin: 0; font-size: 17px; color: var(--ink); line-height: 1.35; padding-right: 10px; }
.status {
  font-size: 11px; padding: 4px 9px; border-radius: 999px; background: rgba(17,24,39,.06); color: var(--ink); white-space: nowrap;
}
.metric-line {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 14px;
  padding: 10px 0;
  border-block: 1px solid rgba(17,24,39,.07);
  color: var(--ink-soft);
  font-size: 12px;
}
.metric-line b { display: block; color: var(--ink); font-size: 18px; line-height: 1.1; }
.info-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--ink-soft); padding: 4px 0; }
.risk-high { color: var(--red) !important; font-weight: 700; }
.empty { text-align: center; color: #999; padding: 60px 0; }
.loading { text-align: center; padding: 40px; color: #999; }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex;
  align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: white; border-radius: 12px; padding: 28px; width: 480px; max-width: 90vw;
}
.modal h3 { margin: 0 0 20px; font-size: 18px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 13px; color: #333; font-weight: 500; }
.form-group input, .form-group select, .form-group textarea {
  width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;
}
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
