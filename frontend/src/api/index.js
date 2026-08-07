import axios from 'axios'
import { beginRequest, finishRequest } from '../feedback'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.meta = config.meta || {}
  config.meta.requestId = beginRequest(config)
  return config
})

api.interceptors.response.use(
  r => {
    finishRequest(r.config.meta?.requestId, true)
    return r
  },
  err => {
    finishRequest(err.config?.meta?.requestId, false, err.response?.data?.detail || err.message)
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
