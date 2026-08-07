<template>
  <div class="knowledge-page">
    <div class="header">
      <h2>企业知识库</h2>
      <div class="header-actions">
        <button class="btn-secondary" @click="rebuildIndex" :disabled="indexing">{{ indexing ? '索引中...' : '重建索引' }}</button>
        <button class="btn-primary" @click="showAdd = true">添加知识</button>
      </div>
    </div>

    <div class="filters">
      <select v-model="filterType" @change="loadKnowledge">
        <option value="">全部类型</option>
        <option value="company_product">产品能力</option>
        <option value="case_study">案例</option>
        <option value="qualification">资质证书</option>
        <option value="technical_arch">技术架构</option>
        <option value="implementation">实施方案</option>
      </select>
      <input v-model="searchQuery" placeholder="搜索知识库..." @keyup.enter="searchKnowledge" />
      <button class="btn-secondary" @click="searchKnowledge">搜索</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else class="knowledge-grid">
      <div v-for="k in knowledge" :key="k.id" class="knowledge-card">
        <div class="card-header">
          <h4>{{ k.material_name }}</h4>
          <span class="type-tag">{{ k.material_type }}</span>
        </div>
        <p class="card-content">{{ k.content?.substring(0, 200) }}{{ k.content?.length > 200 ? '...' : '' }}</p>
        <div class="card-meta">
          <span>版本: {{ k.document_version || '-' }}</span>
          <span>页码: {{ k.source_page }}</span>
          <span>{{ k.has_embedding ? '已索引' : '未索引' }}</span>
          <span :class="['audit-tag', k.is_audited ? 'audited' : 'unaudited']">{{ k.is_audited ? '已审核' : '未审核' }}</span>
          <span v-if="k.is_expired" class="expired-tag">已过期</span>
        </div>
        <div class="card-actions">
          <button v-if="!k.is_audited" class="btn-sm" @click="audit(k.id)">审核通过</button>
        </div>
      </div>
      <div v-if="knowledge.length === 0" class="empty">暂无知识条目，请添加企业材料</div>
    </div>

    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>添加知识条目</h3>
        <div class="form-group">
          <label>材料名称 *</label>
          <input v-model="newKnowledge.material_name" placeholder="例：企业产品白皮书 V3" />
        </div>
        <div class="form-group">
          <label>材料类型</label>
          <select v-model="newKnowledge.material_type">
            <option value="company_product">产品能力</option>
            <option value="case_study">案例</option>
            <option value="qualification">资质证书</option>
            <option value="technical_arch">技术架构</option>
            <option value="implementation">实施方案</option>
          </select>
        </div>
        <div class="form-group">
          <label>产品线</label>
          <input v-model="newKnowledge.product_line" placeholder="所属产品线" />
        </div>
        <div class="form-group">
          <label>内容 *</label>
          <textarea v-model="newKnowledge.content" rows="6" placeholder="粘贴材料内容..."></textarea>
        </div>
        <div class="form-group">
          <label>页码</label>
          <input type="number" v-model="newKnowledge.source_page" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showAdd = false">取消</button>
          <button class="btn-primary" @click="addKnowledge" :disabled="adding">
            {{ adding ? '添加中...' : '添加' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const knowledge = ref([])
const loading = ref(true)
const filterType = ref('')
const searchQuery = ref('')
const showAdd = ref(false)
const adding = ref(false)
const indexing = ref(false)
const newKnowledge = ref({ material_name: '', material_type: 'company_product', product_line: '', content: '', source_page: 1 })

onMounted(loadKnowledge)

async function loadKnowledge() {
  loading.value = true
  knowledge.value = await store.fetchKnowledge(filterType.value || undefined)
  loading.value = false
}

async function addKnowledge() {
  if (!newKnowledge.value.material_name || !newKnowledge.value.content) return
  adding.value = true
  try {
    const params = new URLSearchParams(newKnowledge.value)
    await store.addKnowledge(params)
    showAdd.value = false
    newKnowledge.value = { material_name: '', material_type: 'company_product', product_line: '', content: '', source_page: 1 }
    await loadKnowledge()
  } finally { adding.value = false }
}

async function rebuildIndex() {
  indexing.value = true
  try {
    await store.rebuildKnowledgeIndex(filterType.value || undefined)
    await loadKnowledge()
  } finally { indexing.value = false }
}

async function searchKnowledge() {
  if (!searchQuery.value.trim()) {
    await loadKnowledge()
    return
  }
  knowledge.value = await store.searchKnowledge(searchQuery.value.trim())
}

async function audit(id) {
  await store.auditKnowledge(id)
  await loadKnowledge()
}
</script>

<style scoped>
.knowledge-page { max-width: 1200px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-actions { display: flex; gap: 8px; }
h2 { margin: 0; color: #1a1a2e; }
.btn-primary { padding: 10px 20px; background: #0f3460; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { padding: 10px 20px; background: #eee; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.filters { margin-bottom: 16px; display: flex; gap: 8px; }
.filters select, .filters input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.filters input { width: 260px; }
.knowledge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 16px; }
.knowledge-card { background: white; border-radius: 10px; padding: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.card-header h4 { margin: 0; font-size: 15px; color: #1a1a2e; }
.type-tag { font-size: 11px; padding: 2px 8px; background: #e8f4fd; color: #0f3460; border-radius: 10px; }
.card-content { font-size: 13px; color: #555; line-height: 1.6; margin: 0 0 10px; }
.card-meta { display: flex; gap: 12px; font-size: 12px; color: #999; }
.card-actions { margin-top: 12px; }
.btn-sm { padding: 5px 10px; font-size: 12px; background: #0f3460; color: white; border: none; border-radius: 4px; cursor: pointer; }
.audit-tag { font-size: 11px; padding: 1px 6px; border-radius: 8px; }
.audit-tag.audited { background: #d4edda; color: #155724; }
.audit-tag.unaudited { background: #fff3cd; color: #856404; }
.expired-tag { background: #f8d7da; color: #721c24; font-size: 11px; padding: 1px 6px; border-radius: 8px; }
.empty { text-align: center; padding: 60px 0; color: #999; grid-column: 1 / -1; }
.loading { text-align: center; padding: 40px; color: #999; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: white; border-radius: 12px; padding: 28px; width: 520px; max-width: 90vw; }
.modal h3 { margin: 0 0 20px; font-size: 18px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 4px; font-size: 13px; color: #333; font-weight: 500; }
.form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
