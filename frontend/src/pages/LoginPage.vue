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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const error = ref('')

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
    radial-gradient(circle at 18% 20%, rgba(45,156,189,.28), transparent 28%),
    radial-gradient(circle at 84% 78%, rgba(240,179,91,.24), transparent 24%),
    repeating-linear-gradient(0deg, rgba(255,255,255,.045) 0, rgba(255,255,255,.045) 1px, transparent 1px, transparent 34px),
    repeating-linear-gradient(90deg, rgba(255,255,255,.035) 0, rgba(255,255,255,.035) 1px, transparent 1px, transparent 34px),
    #111827;
  padding: 24px;
}
.login-card {
  position: relative;
  background: rgba(255,255,255,.94);
  padding: 38px;
  border: 1px solid rgba(255,255,255,.62);
  border-radius: 8px;
  box-shadow: 0 26px 80px rgba(0,0,0,0.32);
  width: 420px;
  max-width: 90vw;
  backdrop-filter: blur(18px);
  overflow: hidden;
}
.login-card::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 5px;
  height: 100%;
  background: linear-gradient(#2d9cbd, #f0b35b);
}
.brand-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  margin: 0 auto 14px;
  border-radius: 8px;
  background: linear-gradient(145deg, #f0b35b, #2d9cbd);
  color: #101827;
  font-family: var(--font-title);
  font-weight: 900;
  box-shadow: 0 14px 34px rgba(45,156,189,.22);
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
  background: linear-gradient(180deg, var(--navy-2), var(--navy));
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
  margin-top: 8px;
  font-weight: 800;
  box-shadow: 0 12px 28px rgba(14,43,79,.22);
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: var(--red); font-size: 13px; margin-top: 8px; text-align: center; }
.hint {
  margin-top: 24px;
  padding: 12px;
  background: #f3f6f3;
  border: 1px solid #e0e8df;
  border-radius: 6px;
  font-size: 12px;
  color: var(--ink-soft);
}
.hint p { margin: 2px 0; }
</style>
