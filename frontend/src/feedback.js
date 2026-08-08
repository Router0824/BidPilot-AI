import { reactive } from 'vue'

let requestSeq = 0
let messageSeq = 0

export const feedbackState = reactive({
  pending: [],
  messages: [],
  progress: [],
})

function friendlyUrl(url = '') {
  const clean = url.replace(/^\/api\/v1/, '').split('?')[0]
  const map = [
    [/\/workflow\/start$/, '启动工作流'],
    [/\/workflow\/resume$/, '继续工作流'],
    [/\/workflow\/cancel$/, '取消工作流'],
    [/\/documents$/, '上传/读取文件'],
    [/\/parse$/, '解析文件'],
    [/\/draft$/, '生成章节初稿'],
    [/\/reviews$/, '审查标书'],
    [/\/exports$/, '导出文件'],
    [/\/knowledge\/rebuild-index$/, '重建知识索引'],
    [/\/knowledge\/search$/, '搜索知识库'],
    [/\/addendum-conflicts\/detect$/, '识别补遗冲突'],
    [/\/scoring\/merge-cross-page$/, '合并跨页评分'],
  ]
  return map.find(([pattern]) => pattern.test(clean))?.[1] || '操作'
}

function isSilentRequest(config) {
  if (config.meta?.silent) return true
  const url = String(config.url || '')
  if (url.includes('/auth/login') || url.includes('/auth/me')) return true
  const method = (config.method || 'get').toLowerCase()
  return method === 'get'
}

export function beginRequest(config) {
  const id = ++requestSeq
  const method = (config.method || 'get').toUpperCase()
  const label = config.meta?.label || friendlyUrl(config.url)
  const silent = isSilentRequest(config)
  if (silent) return id
  feedbackState.pending.unshift({
    id,
    label,
    method,
    startedAt: Date.now(),
    url: config.url,
  })
  return id
}

export function finishRequest(id, ok = true, detail = '') {
  const index = feedbackState.pending.findIndex(item => item.id === id)
  const item = index >= 0 ? feedbackState.pending.splice(index, 1)[0] : null
  if (!item) return
  pushMessage(ok ? 'success' : 'error', ok ? `${item.label}完成` : `${item.label}失败`, ok ? '' : detail)
}

export function pushMessage(type, title, detail = '') {
  const message = { id: ++messageSeq, type, title, detail, createdAt: Date.now() }
  feedbackState.messages.unshift(message)
  feedbackState.messages = feedbackState.messages.slice(0, 5)
  setTimeout(() => {
    const index = feedbackState.messages.findIndex(item => item.id === message.id)
    if (index >= 0) feedbackState.messages.splice(index, 1)
  }, type === 'error' ? 6000 : 2800)
}

export function pushProgress(event) {
  const item = { id: ++messageSeq, ...event }
  feedbackState.progress.unshift(item)
  feedbackState.progress = feedbackState.progress.slice(0, 20)
  setTimeout(() => {
    const index = feedbackState.progress.findIndex(progress => progress.id === item.id)
    if (index >= 0) feedbackState.progress.splice(index, 1)
  }, 5000)
}
