<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo" @click="$router.push('/')">
        <span class="logo-mark">BP</span>
        <span>
          <b>BidPilot</b>
          <small>proposal command</small>
        </span>
      </div>
      <nav>
        <div class="nav-label">工作区</div>
        <router-link to="/" class="nav-item">项目工作台</router-link>
        <router-link to="/information" class="nav-item">资讯中心</router-link>
        <template v-if="currentProject">
          <div class="nav-label">当前项目</div>
          <router-link :to="`/project/${currentProject.id}`" class="nav-item">项目详情</router-link>
          <router-link :to="`/project/${currentProject.id}/facts`" class="nav-item">事实确认</router-link>
          <router-link :to="`/project/${currentProject.id}/requirements`" class="nav-item">要求矩阵</router-link>
          <router-link :to="`/project/${currentProject.id}/outline`" class="nav-item">技术标大纲</router-link>
          <router-link :to="`/project/${currentProject.id}/reviews`" class="nav-item">审查中心</router-link>
          <router-link :to="`/project/${currentProject.id}/workflow`" class="nav-item">Agent 任务</router-link>
          <router-link :to="`/project/${currentProject.id}/knowledge`" class="nav-item">知识库</router-link>
          <router-link :to="`/project/${currentProject.id}/consultation`" class="nav-item">咨询中心</router-link>
          <router-link :to="`/project/${currentProject.id}/enterprise`" class="nav-item">企业协作</router-link>
        </template>
      </nav>
      <div class="user-info">
        <span>{{ store.user?.display_name }}</span>
        <button @click="logout">退出</button>
      </div>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const router = useRouter()
const currentProject = computed(() => store.currentProject)

function logout() {
  store.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { display: flex; min-height: 100vh; }
.sidebar {
  width: 246px;
  background:
    linear-gradient(180deg, rgba(45,156,189,.13), transparent 28%),
    repeating-linear-gradient(0deg, rgba(255,255,255,.035) 0, rgba(255,255,255,.035) 1px, transparent 1px, transparent 38px),
    #111827;
  color: white;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border-right: 1px solid rgba(255,255,255,.08);
  box-shadow: 14px 0 38px rgba(17,24,39,.18);
}
.logo {
  padding: 20px 18px;
  font-size: 20px;
  font-weight: 800;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(145deg, #f0b35b, #2d9cbd);
  color: #101827;
  font-family: var(--font-title);
  font-size: 15px;
  box-shadow: 0 12px 30px rgba(45,156,189,.22);
}
.logo b { display: block; line-height: 1; }
.logo small {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  line-height: 1;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: rgba(255,255,255,.48);
}
nav { flex: 1; padding: 12px 0; }
.nav-label {
  padding: 16px 20px 7px;
  color: rgba(255,255,255,.38);
  font-size: 11px;
  font-weight: 800;
}
.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 38px;
  margin: 2px 10px;
  padding: 8px 12px 8px 18px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  font-size: 14px;
  border-radius: 7px;
  transition: all 0.2s;
}
.nav-item::before {
  content: "";
  position: absolute;
  left: 8px;
  width: 3px;
  height: 16px;
  border-radius: 999px;
  background: transparent;
}
.nav-item:hover { color: white; background: rgba(255,255,255,0.08); }
.nav-item.router-link-active {
  color: white;
  background: linear-gradient(90deg, rgba(45,156,189,.24), rgba(255,255,255,.08));
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.08);
}
.nav-item.router-link-active::before { background: #f0b35b; }
.user-info {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.1);
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.user-info button {
  background: none;
  border: 1px solid rgba(255,255,255,0.3);
  color: white;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.content { flex: 1; background: #f5f6fa; padding: 24px; overflow-y: auto; }
.content {
  background:
    radial-gradient(circle at 20% 0%, rgba(45,156,189,.10), transparent 32%),
    radial-gradient(circle at 95% 12%, rgba(240,179,91,.10), transparent 26%),
    transparent;
}
@media (max-width: 860px) {
  .layout { flex-direction: column; }
  .sidebar { width: 100%; min-height: auto; }
  nav { display: flex; overflow-x: auto; padding: 8px; }
  .nav-label { display: none; }
  .nav-item { white-space: nowrap; }
  .content { padding: 16px; }
}
</style>
