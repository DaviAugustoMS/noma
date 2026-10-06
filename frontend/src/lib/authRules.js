/**
 * Regras puras de autenticação (sem Vue, axios nem DOM), testáveis com `node --test`.
 */

// Regra só do cliente: a política real de senha é do Orbit, que responde 400
// quando recusa. Aqui evitamos uma ida ao servidor para o erro mais comum.
export const MIN_PASSWORD_LENGTH = 8

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function normalizeEmail(value) {
  return String(value ?? '').trim().toLowerCase()
}

/**
 * Valida o formulário. Retorna `{ campo: { key, params? } }` com chaves de i18n
 * sob `auth.errors.*`; objeto vazio significa válido.
 */
export function validateAuthForm(mode, { email, password, confirm } = {}) {
  const errors = {}
  const normalized = normalizeEmail(email)

  if (!normalized) errors.email = { key: 'emailRequired' }
  else if (!EMAIL_RE.test(normalized)) errors.email = { key: 'emailInvalid' }

  const pass = String(password ?? '')
  if (!pass) {
    errors.password = { key: 'passwordRequired' }
  } else if (mode === 'register' && pass.length < MIN_PASSWORD_LENGTH) {
    errors.password = { key: 'passwordShort', params: { min: MIN_PASSWORD_LENGTH } }
  }

  if (mode === 'register' && !errors.password && pass !== String(confirm ?? '')) {
    errors.confirm = { key: 'passwordMismatch' }
  }
  return errors
}

/** Converte um erro do axios em uma chave de `auth.errors.*`. */
export function authErrorKey(error) {
  const status = error?.response?.status
  if (!error?.response) {
    return error?.code === 'ERR_NETWORK' || error?.code === 'ECONNABORTED' || error?.request
      ? 'network'
      : 'unknown'
  }
  if (status === 401) return 'invalidCredentials'
  if (status === 409) return 'emailTaken'
  if (status === 400 || status === 422) return 'invalid'
  if (status === 429) return 'rateLimited'
  return 'unknown'
}

/**
 * O destino pós-login vem da URL, então só aceitamos caminhos internos.
 * Bloqueia `//host`, `/\host`, esquemas e qualquer coisa que não comece com `/`.
 */
export function safeRedirect(target, fallback = '/') {
  if (typeof target !== 'string') return fallback
  if (!target.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) {
    return fallback
  }
  if (/[\u0000-\u001f]/.test(target)) return fallback
  if (target === '/auth' || target.startsWith('/auth?')) return fallback
  return target
}

/**
 * O que fazer com um erro de uma chamada ao backend do Noma.
 * Só reage aos códigos que o guard do backend devolve; qualquer outro 401/403
 * (de uma rota, de outra causa) segue o fluxo normal de erro.
 *  - 'refresh': token recusado -> renovar a sessão e repetir a chamada (uma vez);
 *  - 'signout': já renovamos e continua recusado -> encerrar a sessão;
 *  - 'denied': login válido, mas a conta não está na lista de permitidos.
 */
export function apiAuthAction(error, { alreadyRetried = false } = {}) {
  const status = error?.response?.status
  const code = error?.response?.data?.code
  if (status === 401 && (code === 'auth_invalid' || code === 'auth_required')) {
    return alreadyRetried ? 'signout' : 'refresh'
  }
  if (status === 403 && code === 'auth_forbidden') return 'denied'
  return null
}
