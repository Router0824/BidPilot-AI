<template>
  <div class="settings-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Runtime Model</p>
        <h1>模型设置</h1>
        <p>给部署后的使用者输入自己的 API Key；不填写时保持 Mock 模式，仍可完整演示。</p>
      </div>
      <div :class="['mode-pill', form.provider === 'mock' ? 'mock' : 'real']">
        <span></span>
        {{ form.provider === 'mock' ? 'Mock 演示模式' : '真实模型模式' }}
      </div>
    </header>

    <section class="hero-panel">
      <div class="provider-card" :class="{ active: form.provider === 'mock' }" @click="selectProvider('mock')">
        <b>Mock</b>
        <span>无需 Key，适合评委快速体验完整流程。</span>
      </div>
      <div class="provider-card" :class="{ active: form.provider === 'deepseek' }" @click="selectProvider('deepseek')">
        <b>DeepSeek</b>
        <span>OpenAI 兼容接口，推荐国内部署演示。</span>
      </div>
      <div class="provider-card" :class="{ active: form.provider === 'openai' }" @click="selectProvider('openai')">
        <b>OpenAI</b>
        <span>使用 OpenAI Chat Completions 兼容模型。</span>
      </div>
      <div class="provider-card" :class="{ active: form.provider === 'custom' }" @click="selectProvider('custom')">
        <b>Custom</b>
        <span>填写任意 OpenAI 兼容 Base URL。</span>
      </div>
    </section>

    <section class="settings-grid">
      <form class="config-panel" @submit.prevent="save">
        <div class="panel-title">
          <h2>API 连接</h2>
          <small>{{ config?.api_key_configured ? '已保存 Key，留空不会覆盖' : '尚未保存 Key' }}</small>
        </div>

        <label>
          <span>API Key</span>
          <input
            v-model="form.api_key"
            :disabled="form.provider === 'mock'"
            type="password"
            autocomplete="off"
            placeholder="sk-... 或平台提供的访问密钥"
          />
        </label>

        <label>
          <span>Base URL</span>
          <input v-model="form.base_url" :disabled="form.provider === 'mock'" placeholder="https://api.deepseek.com" />
        </label>

        <div class="two-col">
          <label>
            <span>默认模型</span>
            <input v-model="form.model" :disabled="form.provider === 'mock'" placeholder="deepseek-v4-flash" />
          </label>
          <label>
            <span>高质量模型</span>
            <input v-model="form.quality_model" :disabled="form.provider === 'mock'" placeholder="deepseek-v4-pro" />
          </label>
        </div>

        <div class="two-col">
          <label>
            <span>快速模型</span>
            <input v-model="form.fast_model" :disabled="form.provider === 'mock'" placeholder="deepseek-v4-flash" />
          </label>
          <label>
            <span>超时秒数</span>
            <input v-model.number="form.timeout_seconds" type="number" min="5" max="300" />
          </label>
        </div>

        <div class="two-col">
          <label>
            <span>项目成本上限</span>
            <input v-model.number="form.cost_limit_per_project" type="number" min="0" step="0.01" />
          </label>
          <label>
            <span>每千 Token 估算成本</span>
            <input v-model.number="form.estimated_cost_per_1k_tokens" type="number" min="0" step="0.0001" />
          </label>
        </div>

        <div class="actions">
          <button class="btn-primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '保存并启用' }}</button>
          <button class="btn-secondary" type="button" :disabled="testing || saving" @click="test">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
        </div>

        <p v-if="message" :class="['message', messageType]">{{ message }}</p>
      </form>

      <aside class="guide-panel">
        <h2>给使用者看的步骤</h2>
        <ol>
          <li>选择 Mock 可直接跑 Demo，不需要任何密钥。</li>
          <li>选择 DeepSeek/OpenAI/Custom 后输入 API Key。</li>
          <li>确认 Base URL 和模型名，点击“保存并启用”。</li>
          <li>点击“测试连接”，成功后再运行 Agent 工作流。</li>
        </ol>
        <div class="notice">
          <b>安全提示</b>
          <p>API Key 只保存在当前部署实例的本地配置文件中，页面不会回显明文。公开分享部署时请不要预置个人 Key。</p>
        </div>
        <div class="status-box">
          <span>当前配置文件</span>
          <code>{{ config?.config_path || '加载中' }}</code>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const config = ref(null)
const saving = ref(false)
const testing = ref(false)
const message = ref('')
const messageType = ref('success')

const defaults = {
  mock: { base_url: '', model: '', fast_model: '', quality_model: '' },
  deepseek: {
    base_url: 'https://api.deepseek.com',
    model: 'deepseek-v4-flash',
    fast_model: 'deepseek-v4-flash',
    quality_model: 'deepseek-v4-pro',
  },
  openai: {
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    fast_model: 'gpt-4o-mini',
    quality_model: 'gpt-4o',
  },
  custom: { base_url: '', model: '', fast_model: '', quality_model: '' },
}

const form = reactive({
  provider: 'mock',
  api_key: '',
  base_url: '',
  model: '',
  fast_model: '',
  quality_model: '',
  timeout_seconds: 60,
  cost_limit_per_project: 0,
  estimated_cost_per_1k_tokens: 0,
})

function applyConfig(data) {
  config.value = data
  Object.assign(form, {
    provider: data.provider || 'mock',
    api_key: '',
    base_url: data.base_url || '',
    model: data.model || '',
    fast_model: data.fast_model || '',
    quality_model: data.quality_model || '',
    timeout_seconds: data.timeout_seconds || 60,
    cost_limit_per_project: data.cost_limit_per_project || 0,
    estimated_cost_per_1k_tokens: data.estimated_cost_per_1k_tokens || 0,
  })
}

function selectProvider(provider) {
  form.provider = provider
  Object.assign(form, defaults[provider])
  if (provider === 'mock') form.api_key = ''
  message.value = ''
}

async function load() {
  try {
    applyConfig(await store.fetchLLMConfig())
  } catch (e) {
    messageType.value = 'error'
    message.value = e.response?.data?.detail || '模型配置加载失败'
  }
}

async function save() {
  saving.value = true
  message.value = ''
  try {
    const payload = { ...form }
    const data = await store.saveLLMConfig(payload)
    applyConfig(data)
    messageType.value = 'success'
    message.value = data.mode === 'mock' ? '已切换到 Mock 演示模式' : '模型配置已保存并启用'
  } catch (e) {
    messageType.value = 'error'
    message.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  message.value = ''
  try {
    const data = await store.testLLMConfig()
    messageType.value = 'success'
    message.value = data.message || '连接成功'
  } catch (e) {
    messageType.value = 'error'
    message.value = e.response?.data?.detail || '连接失败'
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-page { display: flex; flex-direction: column; gap: 18px; }
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 6px 2px 2px;
}
.eyebrow {
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .08em;
  text-transform: uppercase;
}
h1 { font-size: 34px; margin: 4px 0 8px; }
.page-header p:last-child { color: var(--ink-soft); font-size: 15px; }
.mode-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,.78);
  border: 1px solid var(--line);
  font-weight: 900;
  color: var(--ink);
  white-space: nowrap;
}
.mode-pill span {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--mint);
}
.mode-pill.real span { background: var(--cyan); }
.hero-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.provider-card {
  min-height: 112px;
  padding: 18px;
  border-radius: 8px;
  background: rgba(255,255,255,.72);
  border: 1px solid rgba(255,255,255,.82);
  box-shadow: var(--shadow-soft);
  cursor: pointer;
}
.provider-card b { display: block; font-size: 20px; margin-bottom: 10px; }
.provider-card span { color: var(--ink-soft); font-size: 13px; line-height: 1.55; }
.provider-card.active {
  border-color: rgba(17,24,39,.36);
  background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(247,248,250,.86));
  box-shadow: var(--shadow-lift);
}
.settings-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(320px, .8fr);
  gap: 18px;
}
.config-panel,
.guide-panel {
  padding: 24px;
  border-radius: 8px;
  background: var(--paper);
  border: 1px solid rgba(255,255,255,.82);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(24px) saturate(1.14);
}
.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
h2 { font-size: 20px; }
.panel-title small {
  color: var(--ink-soft);
  font-weight: 800;
}
label { display: flex; flex-direction: column; gap: 7px; margin-bottom: 15px; }
label span { font-size: 13px; font-weight: 900; color: var(--ink); }
input {
  height: 44px;
  padding: 0 13px;
  font-size: 14px;
}
input:disabled {
  opacity: .58;
  cursor: not-allowed;
}
.two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
.actions button {
  min-width: 138px;
  border: none;
  padding: 11px 18px;
  cursor: pointer;
}
.message {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
}
.message.success {
  color: #166534;
  background: rgba(22,163,74,.10);
  border: 1px solid rgba(22,163,74,.20);
}
.message.error {
  color: #991b1b;
  background: rgba(220,38,38,.10);
  border: 1px solid rgba(220,38,38,.20);
}
.guide-panel ol {
  margin: 16px 0;
  padding-left: 20px;
  color: var(--ink-soft);
  line-height: 1.8;
  font-size: 14px;
}
.guide-panel li { padding-left: 2px; }
.notice,
.status-box {
  margin-top: 16px;
  padding: 14px;
  border-radius: 8px;
  background: rgba(247,248,250,.8);
  border: 1px solid var(--line);
}
.notice b { display: block; margin-bottom: 6px; }
.notice p { color: var(--ink-soft); font-size: 13px; line-height: 1.6; }
.status-box span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 8px;
}
code {
  display: block;
  max-width: 100%;
  overflow-wrap: anywhere;
  color: var(--ink-soft);
  font-family: var(--font-mono);
  font-size: 12px;
}
@media (max-width: 980px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .hero-panel,
  .settings-grid,
  .two-col { grid-template-columns: 1fr; }
}
</style>
