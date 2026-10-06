import axios from 'axios'
import i18n from '../i18n'
import { AUTH_REQUIRED, authState, refreshSession, signOut } from '../store/auth'
import { apiAuthAction } from '../lib/authRules'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5001',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    config.headers['Accept-Language'] = i18n.global.locale.value
    // O backend valida o token no Orbit; sem sessão a chamada segue sem cabeçalho.
    if (authState.token) config.headers.Authorization = `Bearer ${authState.token}`
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（容错重试机制）
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  async error => {
    if (AUTH_REQUIRED) {
      const config = error.config
      const action = apiAuthAction(error, { alreadyRetried: !!config?._authRetried })
      if (action === 'refresh' && (await refreshSession())) {
        config._authRetried = true
        config.headers.Authorization = `Bearer ${authState.token}`
        return service(config)
      }
      if (action === 'refresh' || action === 'signout' || action === 'denied') {
        await signOut()
        // import dinâmico: o router importa as views, que importam este módulo
        const { default: router } = await import('../router')
        const query = action === 'denied' ? { denied: '1' } : { redirect: router.currentRoute.value.fullPath }
        router.replace({ name: 'Auth', query })
      }
    }
    console.error('Response error:', error)
    const apiError = error.response?.data?.error || error.response?.data?.message
    
    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    // 处理网络错误
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    // Axios rejects non-2xx responses before the success interceptor can
    // surface the backend's safe, actionable error message.
    if (typeof apiError === 'string' && apiError) {
      error.message = apiError
    }
    
    return Promise.reject(error)
  }
)

export default service
