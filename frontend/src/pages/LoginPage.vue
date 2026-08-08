<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand-mark">BP</div>
      <h1>BidPilot</h1>
      <p class="subtitle">多 Agent 技术标编制平台</p>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="admin / bid_manager / writer / reviewer" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="admin123 / bid123 / write123 / review123" />
        </div>
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
      <div class="hint">
        <p>测试账号：</p>
        <p>admin / admin123（系统管理员）</p>
        <p>bid_manager / bid123（投标经理）</p>
        <p>writer / write123（编制人员）</p>
        <p>reviewer / review123（审核人员）</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const error = ref('')

onMounted(() => {
  store.logout()
})

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await store.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 24% 10%, rgba(37,99,235,.16), transparent 28%),
    radial-gradient(circle at 84% 72%, rgba(17,24,39,.10), transparent 26%),
    linear-gradient(180deg, #ffffff, #f5f5f7);
  padding: 24px;
}
.login-card {
  position: relative;
  background: rgba(255,255,255,.78);
  padding: 42px;
  border: 1px solid rgba(255,255,255,.86);
  border-radius: 8px;
  box-shadow: 0 32px 90px rgba(17,24,39,.14);
  width: 420px;
  max-width: 90vw;
  backdrop-filter: blur(28px) saturate(1.2);
  overflow: hidden;
}
.login-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 4px;
  background: linear-gradient(90deg, #111827, #6b7280, #d1d5db);
}
.brand-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  margin: 0 auto 14px;
  border-radius: 8px;
  background: linear-gradient(145deg, #111827, #3b4556);
  color: white;
  font-family: var(--font-title);
  font-weight: 900;
  box-shadow: 0 14px 34px rgba(17,24,39,.18);
}
h1 {
  text-align: center;
  color: var(--ink);
  margin: 0;
  font-size: 34px;
  letter-spacing: 0;
}
.subtitle {
  text-align: center;
  color: var(--ink-soft);
  margin: 8px 0 24px;
  font-size: 14px;
}
.form-group {
  margin-bottom: 16px;
}
label {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--ink);
  font-weight: 800;
}
input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}
input:focus { outline: none; border-color: #0f3460; }
button {
  width: 100%;
  padding: 12px;
  background: linear-gradient(180deg, #242934, #111827);
  color: white;
  border: none;
  border-radius: 999px;
  font-size: 15px;
  cursor: pointer;
  margin-top: 8px;
  font-weight: 800;
  box-shadow: 0 14px 30px rgba(17,24,39,.18);
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: var(--red); font-size: 13px; margin-top: 8px; text-align: center; }
.hint {
  margin-top: 24px;
  padding: 12px;
  background: rgba(247,248,250,.78);
  border: 1px solid rgba(17,24,39,.08);
  border-radius: 8px;
  font-size: 12px;
  color: var(--ink-soft);
}
.hint p { margin: 2px 0; }
</style>
