<template>
  <div class="information-page">
    <div class="page-head">
      <h2>资讯中心</h2>
      <button class="btn-primary" @click="refreshAll" :disabled="refreshing">{{ refreshing ? '刷新中' : '刷新商机' }}</button>
    </div>

    <section class="monitor-band">
      <form class="monitor-form" @submit.prevent="createMonitor">
        <input v-model="form.name" placeholder="监控名称" required />
        <input v-model="form.source_url" placeholder="公告源 URL，可留空使用样例源" />
        <input v-model="form.keywords" placeholder="关键词，用逗号分隔" />
        <input v-model="form.regions" placeholder="地区，用逗号分隔" />
        <input v-model="form.industry" placeholder="行业" />
        <button class="btn-primary" :disabled="creating">{{ creating ? '创建中' : '创建监控' }}</button>
      </form>

      <div class="monitors">
        <button
          v-for="monitor in monitors"
          :key="monitor.id"
          :class="['monitor-item', { active: monitor.id === selectedMonitorId }]"
          @click="selectMonitor(monitor.id)"
        >
          <span>{{ monitor.name }}</span>
          <small>{{ monitor.keywords.join(' / ') || '全部关键词' }}</small>
          <b>{{ monitor.last_run_at ? '已运行' : '待运行' }}</b>
        </button>
      </div>
    </section>

    <section class="opportunity-table">
      <div class="table-head">
        <span>商机</span><span>地区</span><span>命中</span><span>价值</span><span>竞争</span><span>热度</span><span>操作</span>
      </div>
      <div v-if="!opportunities.length" class="empty">暂无商机</div>
      <div v-for="opp in opportunities" :key="opp.id" class="opp-row">
        <div class="title-cell">
          <strong>{{ opp.title }}</strong>
          <small>{{ opp.source }} · {{ opp.publish_date || '日期待核验' }}</small>
          <p>{{ opp.ai_analysis?.reason || opp.summary }}</p>
        </div>
        <span>{{ opp.region || '待识别' }}</span>
        <span class="keywords">{{ opp.matched_keywords?.join('、') || '-' }}</span>
        <span><b>{{ opp.value_score }}</b></span>
        <span><b>{{ opp.competition_score }}</b></span>
        <span><b :class="heatClass(opp.heat_score)">{{ opp.heat_score }}</b></span>
        <span class="row-actions">
          <button class="btn-sm" @click="openUrl(opp.url)" :disabled="!opp.url">原文</button>
        </span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { pushMessage } from '../feedback'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const monitors = ref([])
const opportunities = ref([])
const selectedMonitorId = ref('')
const creating = ref(false)
const refreshing = ref(false)
const form = reactive({ name: '重点项目监控', source_url: '', keywords: '平台,系统,建设,安全', regions: '', industry: '软件信息化' })

onMounted(load)

async function load() {
  monitors.value = await store.listOpportunityMonitors()
  selectedMonitorId.value = selectedMonitorId.value || monitors.value[0]?.id || ''
  await loadOpportunities()
}

async function loadOpportunities() {
  const params = selectedMonitorId.value ? { monitor_id: selectedMonitorId.value } : {}
  opportunities.value = await store.listOpportunities(params)
}

async function createMonitor() {
  creating.value = true
  try {
    const monitor = await store.createOpportunityMonitor({
      ...form,
      keywords: splitList(form.keywords),
      regions: splitList(form.regions),
    })
    monitors.value.unshift(monitor)
    selectedMonitorId.value = monitor.id
    const result = await store.runOpportunityMonitor(monitor.id)
    pushMessage('success', '商机监控完成', `新增 ${result.created} 条`)
    await loadOpportunities()
  } catch (err) {
    pushMessage('error', '创建监控失败', err.response?.data?.message || err.response?.data?.detail || err.message)
  } finally {
    creating.value = false
  }
}

async function refreshAll() {
  refreshing.value = true
  try {
    const result = selectedMonitorId.value
      ? await store.runOpportunityMonitor(selectedMonitorId.value)
      : await store.refreshOpportunities()
    pushMessage('success', '商机刷新完成', `新增 ${result.created || 0} 条`)
    monitors.value = await store.listOpportunityMonitors()
    await loadOpportunities()
  } catch (err) {
    pushMessage('error', '商机刷新失败', err.response?.data?.message || err.response?.data?.detail || err.message)
  } finally {
    refreshing.value = false
  }
}

async function selectMonitor(id) {
  selectedMonitorId.value = id
  await loadOpportunities()
}

function splitList(value) {
  return String(value || '').split(/[,，\s]+/).map(item => item.trim()).filter(Boolean)
}

function heatClass(score) {
  if (score >= 75) return 'hot'
  if (score >= 55) return 'warm'
  return 'cool'
}

function openUrl(url) {
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<style scoped>
.information-page { max-width: 1500px; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { margin: 0; color: #1a1a2e; }
.btn-primary { padding: 10px 18px; background: #0f3460; color: #fff; border: 0; border-radius: 6px; cursor: pointer; font-weight: 600; transition: transform .15s, box-shadow .15s, background .15s; }
.btn-primary:hover:not(:disabled) { background: #14508f; box-shadow: 0 8px 18px rgba(15,52,96,.18); transform: translateY(-1px); }
.btn-primary:active:not(:disabled) { transform: translateY(0); box-shadow: none; }
.btn-primary:disabled { opacity: .55; cursor: not-allowed; }
.monitor-band { display: grid; grid-template-columns: 1fr 360px; gap: 16px; margin-bottom: 16px; }
.monitor-form, .monitors, .opportunity-table { background: #fff; border: 1px solid #e9edf3; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
.monitor-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; padding: 16px; }
.monitor-form input { border: 1px solid #d8e0ea; border-radius: 6px; padding: 10px 12px; font-size: 14px; min-width: 0; }
.monitor-form input:focus { outline: none; border-color: #3aa0e6; box-shadow: 0 0 0 3px rgba(58,160,230,.12); }
.monitor-form .btn-primary { grid-column: span 2; justify-self: start; }
.monitors { padding: 10px; display: grid; gap: 8px; max-height: 230px; overflow: auto; }
.monitor-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 10px; text-align: left; padding: 10px 12px; border: 1px solid transparent; border-radius: 6px; background: #fff; cursor: pointer; transition: background .15s, border .15s, transform .15s; }
.monitor-item:hover { background: #f5f9ff; }
.monitor-item:active { transform: scale(.99); }
.monitor-item.active { border-color: #8fc7ff; background: #eaf5ff; }
.monitor-item span { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.monitor-item small { color: #69758a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.monitor-item b { grid-row: span 2; color: #0f3460; font-size: 12px; align-self: center; }
.opportunity-table { overflow: hidden; }
.table-head, .opp-row { display: grid; grid-template-columns: minmax(300px, 1fr) 90px 150px 70px 70px 70px 80px; gap: 10px; align-items: center; padding: 12px 16px; }
.table-head { background: #f8f9fa; color: #69758a; font-size: 13px; font-weight: 700; border-bottom: 1px solid #e9edf3; }
.opp-row { border-bottom: 1px solid #f0f2f5; font-size: 13px; }
.opp-row:hover { background: #fbfdff; }
.title-cell strong { display: block; color: #20283a; margin-bottom: 4px; }
.title-cell small { display: block; color: #8a94a6; margin-bottom: 5px; }
.title-cell p { margin: 0; color: #69758a; line-height: 1.45; }
.keywords { color: #0f3460; }
.hot { color: #c0392b; }
.warm { color: #d9822b; }
.cool { color: #2c7a4b; }
.btn-sm { padding: 6px 10px; border: 1px solid #cfd8e3; background: #fff; color: #0f3460; border-radius: 5px; cursor: pointer; }
.btn-sm:hover:not(:disabled) { background: #eef6ff; border-color: #8fc7ff; }
.btn-sm:active:not(:disabled) { transform: scale(.98); }
.btn-sm:disabled { opacity: .45; cursor: not-allowed; }
.empty { padding: 60px; text-align: center; color: #9aa3ad; }
@media (max-width: 1100px) {
  .monitor-band { grid-template-columns: 1fr; }
  .table-head { display: none; }
  .opp-row { grid-template-columns: 1fr 1fr; }
  .title-cell { grid-column: span 2; }
}
</style>
