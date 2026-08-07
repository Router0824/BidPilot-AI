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
      <div class="content-shell">
        <router-view />
      </div>
    </main>
    <DemoRemote v-if="demoMode && route.params.id" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import DemoRemote from '../components/DemoRemote.vue'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const currentProject = computed(() => store.currentProject)
const demoMode = computed(() => route.query.demo === '1')

function logout() {
  store.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { display: flex; min-height: 100vh; }
.sidebar {
  position: sticky;
  top: 0;
  width: 260px;
  height: 100vh;
  background: rgba(255,255,255,.72);
  color: var(--ink);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border-right: 1px solid rgba(17,24,39,.08);
  box-shadow: 10px 0 34px rgba(17,24,39,.06);
  backdrop-filter: blur(26px) saturate(1.2);
}
.logo {
  padding: 22px 18px 18px;
  font-size: 20px;
  font-weight: 800;
  border-bottom: 1px solid rgba(17,24,39,.07);
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
  background: linear-gradient(145deg, #111827, #3b4556);
  color: white;
  font-family: var(--font-title);
  font-size: 15px;
  box-shadow: 0 12px 30px rgba(17,24,39,.16);
}
.logo b { display: block; line-height: 1; }
.logo small {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  line-height: 1;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
nav { flex: 1; padding: 12px 0; }
.nav-label {
  padding: 16px 20px 7px;
  color: var(--muted);
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
  color: var(--ink-soft);
  text-decoration: none;
  font-size: 14px;
  border-radius: 999px;
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
.nav-item:hover { color: var(--ink); background: rgba(17,24,39,.05); }
.nav-item.router-link-active {
  color: var(--ink);
  background: rgba(255,255,255,.9);
  box-shadow: var(--shadow-pop);
}
.nav-item.router-link-active::before { background: #111827; }
.user-info {
  padding: 16px 20px;
  border-top: 1px solid rgba(17,24,39,.07);
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.user-info button {
  background: rgba(255,255,255,.7);
  border: 1px solid rgba(17,24,39,.1);
  color: var(--ink);
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
}
.content {
  flex: 1;
  padding: 26px;
  overflow-y: auto;
  background: transparent;
}
.content-shell {
  max-width: 1500px;
  margin: 0 auto;
}
@media (max-width: 860px) {
  .layout { flex-direction: column; }
  .sidebar { position: relative; width: 100%; height: auto; min-height: auto; }
  nav { display: flex; overflow-x: auto; padding: 8px; }
  .nav-label { display: none; }
  .nav-item { white-space: nowrap; }
  .content { padding: 16px; }
}
</style>
