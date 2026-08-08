import { createRouter, createWebHistory } from 'vue-router'
import api from '../api'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },
  {
    path: '/',
    component: () => import('../pages/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../pages/DashboardPage.vue') },
      { path: 'information', name: 'Information', component: () => import('../pages/InformationPage.vue') },
      { path: 'project/:id', name: 'ProjectDetail', component: () => import('../pages/ProjectDetailPage.vue') },
      { path: 'project/:id/facts', name: 'FactsConfirm', component: () => import('../pages/FactsConfirmPage.vue') },
      { path: 'project/:id/requirements', name: 'Requirements', component: () => import('../pages/RequirementsPage.vue') },
      { path: 'project/:id/evidence', name: 'EvidenceMatrix', component: () => import('../pages/EvidenceMatrixPage.vue') },
      { path: 'project/:id/outline', name: 'Outline', component: () => import('../pages/OutlinePage.vue') },
      { path: 'project/:id/reviews', name: 'Reviews', component: () => import('../pages/ReviewsPage.vue') },
      { path: 'project/:id/workflow', name: 'Workflow', component: () => import('../pages/WorkflowPage.vue') },
      { path: 'project/:id/knowledge', name: 'Knowledge', component: () => import('../pages/KnowledgePage.vue') },
      { path: 'project/:id/consultation', name: 'Consultation', component: () => import('../pages/ConsultationPage.vue') },
      { path: 'project/:id/enterprise', name: 'Enterprise', component: () => import('../pages/EnterprisePage.vue') },
    ]
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let sessionChecked = false

router.beforeEach(async to => {
  if (to.path === '/login') return true

  const token = localStorage.getItem('token')
  if (!token) return '/login'
  if (sessionChecked) return true

  try {
    await api.get('/auth/me', { meta: { silent: true } })
    sessionChecked = true
    return true
  } catch {
    localStorage.removeItem('token')
    sessionChecked = false
    return '/login'
  }
})

export default router
