import axios from 'axios'
import { invalidateSession } from '@/services/session'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
const api = axios.create({ baseURL: apiBaseUrl, timeout: 10000 })

api.interceptors.request.use(config => {
  const route = config.url ?? ''
  const isPublic = route === '/login' || route === '/register'
  const token = localStorage.getItem('token')
  const isRelative = !/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(route)
  if (!isPublic && isRelative && token && !config.headers.has('Authorization')) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

api.interceptors.response.use(undefined, error => {
  if (error.response?.status === 401) {
    const authorization = error.config?.headers.get('Authorization')
    if (typeof authorization === 'string' && authorization.startsWith('Bearer ')) {
      invalidateSession(authorization.slice(7))
    }
  }
  return Promise.reject(error)
})

export async function authFetch(path: `/${string}`, init: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers })
  if (response.status === 401) invalidateSession(token)
  return response
}

export default api
