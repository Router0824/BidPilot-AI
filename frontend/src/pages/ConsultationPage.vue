<template>
  <div class="consultation-page">
    <div class="page-head">
      <div>
        <h2>咨询中心</h2>
        <span class="role-pill">{{ roleLabel(store.user?.role) }}</span>
      </div>
      <button class="btn-primary" @click="newSession" :disabled="loading">新建会话</button>
    </div>

    <div class="workspace">
      <aside class="sessions">
        <button
          v-for="session in sessions"
          :key="session.id"
          :class="['session-item', { active: session.id === activeSessionId }]"
          @click="selectSession(session.id)"
        >
          <span>{{ session.title }}</span>
          <small>{{ formatTime(session.updated_at) }}</small>
        </button>
      </aside>

      <section class="chat-panel">
        <div class="messages" ref="messageBox">
          <div v-if="!messages.length && !loading" class="empty-state">暂无对话</div>
          <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
            <div class="bubble">
              <div class="message-text">{{ msg.content }}</div>
              <div v-if="msg.meta?.confidence" class="confidence-line">
                可信度 {{ Math.round(msg.meta.confidence * 100) }}% · 引用 {{ msg.meta.used_context || 0 }} 条
              </div>
              <div v-if="msg.citations?.length" class="citations">
                <div v-for="(citation, idx) in msg.citations" :key="idx" class="citation">
                  <b>{{ citation.type === 'document' ? '文件' : '知识库' }}</b>
                  <span>{{ citation.source }}{{ citation.page ? ` · P${citation.page}` : '' }}</span>
                  <p>{{ citation.snippet }}</p>
                </div>
              </div>
            </div>
          </div>
          <div v-if="asking" class="message assistant">
            <div class="bubble thinking">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <form class="composer" @submit.prevent="ask">
          <textarea v-model="question" :disabled="asking || !activeSessionId" rows="3" placeholder="询问政策、流程、评分规则、响应策略..." />
          <button class="btn-primary" :disabled="asking || !question.trim() || !activeSessionId">
            {{ asking ? '生成中' : '发送' }}
          </button>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { pushMessage } from '../feedback'
import { useAppStore } from '../stores/app'

const route = useRoute()
const store = useAppStore()
const projectId = route.params.id
const sessions = ref([])
const messages = ref([])
const activeSessionId = ref('')
const question = ref('')
const loading = ref(false)
const asking = ref(false)
const messageBox = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  try {
    sessions.value = await store.listConsultationSessions(projectId)
    if (!sessions.value.length) {
      const session = await store.createConsultationSession(projectId, '项目咨询')
      sessions.value = [session]
    }
    activeSessionId.value = activeSessionId.value || sessions.value[0]?.id || ''
    if (activeSessionId.value) await loadMessages()
  } catch (err) {
    pushMessage('error', '咨询中心加载失败', err.response?.data?.message || err.response?.data?.detail || err.message)
  } finally {
    loading.value = false
  }
}

async function newSession() {
  loading.value = true
  try {
    const session = await store.createConsultationSession(projectId, '新咨询')
    sessions.value.unshift(session)
    activeSessionId.value = session.id
    messages.value = []
  } catch (err) {
    pushMessage('error', '新建会话失败', err.response?.data?.message || err.response?.data?.detail || err.message)
  } finally {
    loading.value = false
  }
}

async function selectSession(id) {
  activeSessionId.value = id
  await loadMessages()
}

async function loadMessages() {
  messages.value = await store.listConsultationMessages(projectId, activeSessionId.value)
  await scrollBottom()
}

async function ask() {
  const text = question.value.trim()
  if (!text) return
  messages.value.push({ id: `local-${Date.now()}`, role: 'user', content: text, citations: [], meta: {} })
  question.value = ''
  asking.value = true
  await scrollBottom()
  try {
    const result = await store.askConsultation(projectId, activeSessionId.value, text)
    messages.value = await store.listConsultationMessages(projectId, result.session.id)
    sessions.value = await store.listConsultationSessions(projectId)
  } catch (err) {
    pushMessage('error', '咨询失败', err.response?.data?.detail || err.message)
  } finally {
    asking.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (messageBox.value) messageBox.value.scrollTop = messageBox.value.scrollHeight
}

function roleLabel(role) {
  return { admin: '系统管理员视角', project_admin: '投标经理视角', writer: '编制人员视角', reviewer: '审核人员视角' }[role] || '项目成员视角'
}

function formatTime(value) {
  if (!value) return ''
  return value.slice(5, 16).replace('T', ' ')
}
</script>

<style scoped>
.consultation-page { max-width: 1500px; height: calc(100vh - 48px); display: flex; flex-direction: column; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
h2 { margin: 0 0 8px; color: #1a1a2e; }
.role-pill { display: inline-flex; padding: 4px 10px; border-radius: 999px; background: #e8f1fb; color: #0f3460; font-size: 12px; font-weight: 600; }
.btn-primary { padding: 10px 18px; background: #0f3460; color: #fff; border: 0; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; transition: transform .15s, box-shadow .15s, background .15s; }
.btn-primary:hover:not(:disabled) { background: #14508f; box-shadow: 0 8px 18px rgba(15,52,96,.18); transform: translateY(-1px); }
.btn-primary:active:not(:disabled) { transform: translateY(0); box-shadow: none; }
.btn-primary:disabled { opacity: .55; cursor: not-allowed; }
.workspace { flex: 1; display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; min-height: 0; }
.sessions, .chat-panel { background: #fff; border: 1px solid #e9edf3; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
.sessions { padding: 10px; overflow: auto; }
.session-item { width: 100%; display: flex; flex-direction: column; gap: 4px; text-align: left; padding: 10px 12px; border: 1px solid transparent; border-radius: 6px; background: transparent; cursor: pointer; color: #1a1a2e; transition: background .15s, border .15s, transform .15s; }
.session-item:hover { background: #f5f9ff; }
.session-item:active { transform: scale(.99); }
.session-item.active { border-color: #8fc7ff; background: #eaf5ff; }
.session-item span { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-item small { color: #8a94a6; font-size: 12px; }
.chat-panel { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.messages { flex: 1; overflow: auto; padding: 18px; }
.empty-state { height: 100%; display: grid; place-items: center; color: #9aa3ad; }
.message { display: flex; margin-bottom: 14px; }
.message.user { justify-content: flex-end; }
.bubble { max-width: min(760px, 78%); padding: 12px 14px; border-radius: 8px; line-height: 1.55; font-size: 14px; white-space: pre-wrap; }
.user .bubble { background: #0f3460; color: #fff; }
.assistant .bubble { background: #f6f8fb; color: #20283a; border: 1px solid #e7edf5; }
.confidence-line { margin-top: 10px; color: #69758a; font-size: 12px; white-space: normal; }
.citations { margin-top: 10px; display: grid; gap: 8px; white-space: normal; }
.citation { border-left: 3px solid #3aa0e6; padding: 8px 10px; background: #fff; border-radius: 4px; }
.citation b { margin-right: 8px; color: #0f3460; }
.citation span { color: #69758a; font-size: 12px; }
.citation p { margin: 6px 0 0; color: #4c5668; font-size: 12px; }
.thinking { display: inline-flex; gap: 5px; }
.thinking span { width: 7px; height: 7px; border-radius: 50%; background: #3aa0e6; animation: pulse 1s infinite ease-in-out; }
.thinking span:nth-child(2) { animation-delay: .15s; }
.thinking span:nth-child(3) { animation-delay: .3s; }
.composer { display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 12px; padding: 14px; border-top: 1px solid #edf1f6; background: #fff; }
textarea { resize: none; border: 1px solid #d8e0ea; border-radius: 6px; padding: 10px 12px; font-size: 14px; outline: none; }
textarea:focus { border-color: #3aa0e6; box-shadow: 0 0 0 3px rgba(58,160,230,.12); }
@keyframes pulse { 0%, 80%, 100% { opacity: .35; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }
@media (max-width: 900px) {
  .consultation-page { height: auto; }
  .workspace { grid-template-columns: 1fr; }
  .sessions { max-height: 180px; }
  .messages { min-height: 420px; }
  .bubble { max-width: 92%; }
}
</style>
