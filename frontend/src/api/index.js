import axios from 'axios'
import i18n from '../i18n'
import { AUTH_REQUIRED, authState, deniedAccount, refreshSession, signOut } from '../store/auth'
import { apiAuthAction } from '../lib/authRules'

// Cria a instância do axios
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5001',
  timeout: 300000, // Tempo esgotado de 5 minutos (a geração da ontologia pode levar bastante tempo)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Interceptor de requisição
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

// Interceptor de resposta (mecanismo de tolerância a falhas com nova tentativa)
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // Se o código de status retornado não for success, lança um erro
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
        // Várias chamadas recebem 403 juntas: só a primeira ainda vê o usuário (as outras
        // chegam depois do signOut), então nunca sobrescrevemos o email com vazio.
        if (action === 'denied' && authState.user?.email) deniedAccount.email = authState.user.email
        await signOut()
        // import dinâmico: o router importa as views, que importam este módulo
        const { default: router } = await import('../router')
        const query = action === 'denied' ? { denied: '1' } : { redirect: router.currentRoute.value.fullPath }
        router.replace({ name: 'Auth', query })
      }
    }
    console.error('Response error:', error)
    const apiError = error.response?.data?.error || error.response?.data?.message
    
    // Trata tempo esgotado
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    // Trata erro de rede
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
