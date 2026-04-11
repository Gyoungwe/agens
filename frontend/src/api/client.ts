import axios from 'axios'

const API_BASE = '/api'

export function getDirectApiBaseUrl(): string {
  if (typeof window === 'undefined') {
    return 'http://localhost:8000/api'
  }

  const { protocol, hostname, port, origin } = window.location
  if (port === '8000') {
    return `${origin}/api`
  }

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${protocol}//${hostname}:8000/api`
  }

  return `${origin}/api`
}

const client = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
