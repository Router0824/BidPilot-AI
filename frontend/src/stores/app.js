import { defineStore } from 'pinia'
import api from '../api'

export const useAppStore = defineStore('app', {
  state: () => ({
    user: null,
    token: localStorage.getItem('token') || '',
    currentProject: null,
  }),
  actions: {
    async login(username, password) {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      const { data } = await api.post('/auth/login', { username, password })
      this.token = data.data.access_token
      this.user = data.data.user
      localStorage.setItem('token', this.token)
      return data.data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
    async fetchLLMConfig() {
      const { data } = await api.get('/system/llm-config')
      return data.data
    },
    async saveLLMConfig(payload) {
      const { data } = await api.put('/system/llm-config', payload)
      return data.data
    },
    async testLLMConfig() {
      const { data } = await api.post('/system/llm-config/test')
      return data.data
    },
    async fetchProjects(filters = {}) {
      const params = new URLSearchParams()
      if (filters.status) params.set('status', filters.status)
      const suffix = params.toString() ? `?${params.toString()}` : ''
      const { data } = await api.get(`/projects${suffix}`)
      return data.data || []
    },
    async createProject(projectData) {
      const { data } = await api.post('/projects', projectData)
      return data.data
    },
    async fetchProject(id) {
      const { data } = await api.get(`/projects/${id}`)
      this.currentProject = data.data
      return data.data
    },
    async fetchRequirements(projectId, filters = {}) {
      const params = new URLSearchParams(filters).toString()
      const { data } = await api.get(`/projects/${projectId}/requirements?${params}`)
      return data.data || []
    },
    async fetchCoverageMatrix(projectId) {
      const { data } = await api.get(`/projects/${projectId}/coverage-matrix`)
      return data.data || []
    },
    async rebuildCoverageMatrix(projectId) {
      const { data } = await api.post(`/projects/${projectId}/coverage-matrix/rebuild`)
      return data.data
    },
    async fetchEvidenceChain(projectId, requirementId) {
      const { data } = await api.get(`/projects/${projectId}/requirements/${requirementId}/evidence-chain`)
      return data.data
    },
    async confirmRequirement(projectId, requirementId) {
      const { data } = await api.post(`/projects/${projectId}/requirements/${requirementId}/confirm`)
      return data.data
    },
    async fetchFacts(projectId) {
      const { data } = await api.get(`/projects/${projectId}/facts`)
      return data.data || []
    },
    async confirmFact(projectId, factId, action) {
      const { data } = await api.post(`/projects/${projectId}/facts/${factId}/confirm`, action)
      return data.data
    },
    async fetchOutline(projectId) {
      const { data } = await api.get(`/projects/${projectId}/outline`)
      return data.data || []
    },
    async generateDraft(projectId, sectionId) {
      const { data } = await api.post(`/projects/${projectId}/outline/sections/${sectionId}/draft`, {})
      return data.data
    },
    async fetchDraftVersions(projectId, sectionId) {
      const { data } = await api.get(`/projects/${projectId}/outline/sections/${sectionId}/versions`)
      return data.data || []
    },
    async fetchDocuments(projectId) {
      const { data } = await api.get(`/projects/${projectId}/documents`)
      return data.data || []
    },
    async uploadDocument(projectId, file, docType = 'tender_main') {
      if (file.size > 50 * 1024 * 1024) {
        return await this.uploadDocumentChunked(projectId, file, docType)
      }
      const form = new FormData()
      form.append('file', file)
      form.append('document_type', docType)
      const { data } = await api.post(`/projects/${projectId}/documents`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      return data.data
    },
    async uploadDocumentChunked(projectId, file, docType = 'tender_main') {
      const hashBuffer = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
      const fileHash = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('')
      const createForm = new FormData()
      createForm.append('filename', file.name)
      createForm.append('total_size', file.size)
      createForm.append('file_hash', fileHash)
      createForm.append('document_type', docType)
      const created = await api.post(`/projects/${projectId}/documents/upload-sessions`, createForm)
      const session = created.data.data
      const chunkSize = session.chunk_size || 8 * 1024 * 1024
      let index = 0
      for (let start = 0; start < file.size; start += chunkSize) {
        const chunkForm = new FormData()
        chunkForm.append('chunk_index', index)
        chunkForm.append('file', file.slice(start, start + chunkSize), file.name)
        await api.put(`/projects/${projectId}/documents/upload-sessions/${session.upload_session_id}/chunks`, chunkForm)
        index += 1
      }
      const { data } = await api.post(`/projects/${projectId}/documents/upload-sessions/${session.upload_session_id}/complete`)
      return data.data
    },
    async parseDocument(projectId, documentId) {
      const { data } = await api.post(`/projects/${projectId}/documents/${documentId}/parse`)
      return data.data
    },
    async fetchWorkflow(projectId) {
      const { data } = await api.get(`/projects/${projectId}/workflow`)
      return data.data
    },
    workflowStreamUrl(projectId) {
      const token = encodeURIComponent(this.token || localStorage.getItem('token') || '')
      return `/api/v1/projects/${projectId}/workflow/stream?token=${token}`
    },
    collaborationWsUrl(projectId) {
      const token = encodeURIComponent(this.token || localStorage.getItem('token') || '')
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      return `${proto}://${window.location.host}/api/v1/projects/${projectId}/enterprise/collaboration/ws?token=${token}`
    },
    async startWorkflow(projectId, documentIds = []) {
      const { data } = await api.post(`/projects/${projectId}/workflow/start`, { document_ids: documentIds })
      return data.data
    },
    async resumeWorkflow(projectId) {
      const { data } = await api.post(`/projects/${projectId}/workflow/resume`)
      return data.data
    },
    async cancelWorkflow(projectId) {
      const { data } = await api.post(`/projects/${projectId}/workflow/cancel`)
      return data.data
    },
    async previewWorkflowImpact(projectId, payload) {
      const { data } = await api.post(`/projects/${projectId}/workflow/impact-preview`, payload)
      return data.data
    },
    async startIncrementalRerun(projectId, payload) {
      const { data } = await api.post(`/projects/${projectId}/workflow/incremental-rerun`, payload)
      return data.data
    },
    async listConfirmations(projectId) {
      const { data } = await api.get(`/projects/${projectId}/workflow/confirmations`)
      return data.data || []
    },
    async resolveConfirmation(projectId, confirmationId, action) {
      const { data } = await api.post(`/projects/${projectId}/workflow/confirmations/${confirmationId}/resolve`, action)
      return data.data
    },
    async runReview(projectId, reviewType = 'full') {
      const { data } = await api.post(`/projects/${projectId}/reviews?review_type=${reviewType}`)
      return data.data
    },
    async listReviews(projectId) {
      const { data } = await api.get(`/projects/${projectId}/reviews`)
      return data.data || []
    },
    async updateFinding(projectId, findingId, status, ignoreReason) {
      const params = new URLSearchParams({ status })
      if (ignoreReason) params.append('ignore_reason', ignoreReason)
      const { data } = await api.patch(`/projects/${projectId}/reviews/findings/${findingId}?${params}`)
      return data.data
    },
    async fixFinding(projectId, findingId, apply = true) {
      const { data } = await api.post(`/projects/${projectId}/reviews/findings/${findingId}/fix?apply=${apply}`)
      return data.data
    },
    async listFixAttempts(projectId) {
      const { data } = await api.get(`/projects/${projectId}/fixes`)
      return data.data || []
    },
    async exportData(projectId, exportType, format) {
      const { data } = await api.post(`/projects/${projectId}/exports`, { export_type: exportType, format })
      return data.data
    },
    async fetchKnowledge(materialType) {
      const params = materialType ? `?material_type=${materialType}` : ''
      const { data } = await api.get(`/knowledge${params}`)
      return data.data || []
    },
    async addKnowledge(formData) {
      const { data } = await api.post('/knowledge', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
      return data.data
    },
    async auditKnowledge(chunkId) {
      const { data } = await api.post(`/knowledge/${chunkId}/audit`)
      return data.data
    },
    async rebuildKnowledgeIndex(materialType) {
      const params = materialType ? `?material_type=${encodeURIComponent(materialType)}` : ''
      const { data } = await api.post(`/knowledge/rebuild-index${params}`)
      return data.data
    },
    async searchKnowledge(query, limit = 8) {
      const { data } = await api.get(`/knowledge/search?q=${encodeURIComponent(query)}&limit=${limit}`)
      return (data.data || []).map(item => ({ ...item, content: item.content || item.content_snippet }))
    },
    async fetchScoring(projectId) {
      const { data } = await api.get(`/projects/${projectId}/scoring`)
      return data.data || []
    },
    async fetchScoringCoverage(projectId) {
      const { data } = await api.get(`/projects/${projectId}/scoring/coverage`)
      return data.data
    },
    async mergeCrossPageScoring(projectId) {
      const { data } = await api.post(`/projects/${projectId}/scoring/merge-cross-page`)
      return data.data
    },
    async detectAddendumConflicts(projectId) {
      const { data } = await api.post(`/projects/${projectId}/addendum-conflicts/detect`)
      return data.data
    },
    async listAddendumConflicts(projectId) {
      const { data } = await api.get(`/projects/${projectId}/addendum-conflicts`)
      return data.data || []
    },
    async fetchEnterpriseMembers(projectId) {
      const { data } = await api.get(`/projects/${projectId}/enterprise/members`)
      return data.data || []
    },
    async saveEnterpriseMember(projectId, userId, role = 'writer') {
      const { data } = await api.post(`/projects/${projectId}/enterprise/members?user_id=${encodeURIComponent(userId)}&role=${encodeURIComponent(role)}`)
      return data.data
    },
    async lockSection(projectId, sectionId) {
      const { data } = await api.post(`/projects/${projectId}/enterprise/sections/${sectionId}/lock`)
      return data.data
    },
    async unlockSection(projectId, sectionId) {
      const { data } = await api.delete(`/projects/${projectId}/enterprise/sections/${sectionId}/lock`)
      return data.data
    },
    async detectAddendumConflicts(projectId) {
      const { data } = await api.post(`/projects/${projectId}/addendum-conflicts/detect`)
      return data.data
    },
    async assignSection(projectId, sectionId, userId) {
      const { data } = await api.post(`/projects/${projectId}/enterprise/sections/${sectionId}/assign?user_id=${encodeURIComponent(userId)}`)
      return data.data
    },
    async submitSectionApproval(projectId, sectionId, reviewerId) {
      const suffix = reviewerId ? `?reviewer_id=${encodeURIComponent(reviewerId)}` : ''
      const { data } = await api.post(`/projects/${projectId}/enterprise/sections/${sectionId}/approval${suffix}`)
      return data.data
    },
    async resolveApproval(projectId, approvalId, action, comment = '') {
      const params = new URLSearchParams({ action })
      if (comment) params.append('comment', comment)
      const { data } = await api.post(`/projects/${projectId}/enterprise/approvals/${approvalId}/resolve?${params}`)
      return data.data
    },
    async fetchApprovals(projectId) {
      const { data } = await api.get(`/projects/${projectId}/enterprise/approvals`)
      return data.data || []
    },
    async fetchIndustryTemplates(projectId) {
      const { data } = await api.get(`/projects/${projectId}/enterprise/templates`)
      return data.data || []
    },
    async applyIndustryTemplate(projectId, templateKey) {
      const { data } = await api.post(`/projects/${projectId}/enterprise/templates/${templateKey}/apply`)
      return data.data
    },
    async fetchAudits(projectId) {
      const { data } = await api.get(`/projects/${projectId}/enterprise/audits`)
      return data.data || []
    },
    async generateCommercialBid(projectId) {
      const { data } = await api.post(`/projects/${projectId}/enterprise/commercial/generate`)
      return data.data
    },
    async generateQualificationBid(projectId) {
      const { data } = await api.post(`/projects/${projectId}/enterprise/qualification/generate`)
      return data.data
    },
    async fetchConfidenceReport(projectId) {
      const { data } = await api.get(`/projects/${projectId}/confidence/report`)
      return data.data
    },
    async recalculateConfidence(projectId) {
      const { data } = await api.post(`/projects/${projectId}/confidence/recalculate`)
      return data.data
    },
    async listConsultationSessions(projectId) {
      const { data } = await api.get(`/projects/${projectId}/consultation/sessions`)
      return data.data || []
    },
    async createConsultationSession(projectId, title = '') {
      const { data } = await api.post(`/projects/${projectId}/consultation/sessions`, { title })
      return data.data
    },
    async listConsultationMessages(projectId, sessionId) {
      const { data } = await api.get(`/projects/${projectId}/consultation/sessions/${sessionId}/messages`)
      return data.data || []
    },
    async askConsultation(projectId, sessionId, question) {
      const { data } = await api.post(`/projects/${projectId}/consultation/sessions/${sessionId}/ask`, { question })
      return data.data
    },
    async listOpportunityMonitors() {
      const { data } = await api.get('/information/monitors')
      return data.data || []
    },
    async createOpportunityMonitor(payload) {
      const { data } = await api.post('/information/monitors', payload)
      return data.data
    },
    async runOpportunityMonitor(monitorId) {
      const { data } = await api.post(`/information/monitors/${monitorId}/run`)
      return data.data
    },
    async refreshOpportunities() {
      const { data } = await api.post('/information/opportunities/refresh-all')
      return data.data
    },
    async listOpportunities(params = {}) {
      const search = new URLSearchParams(params).toString()
      const { data } = await api.get(`/information/opportunities${search ? `?${search}` : ''}`)
      return data.data || []
    },
  }
})
