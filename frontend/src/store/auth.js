/**
 * Sessão do usuário (cadastro/login no Zeep Orbit).
 *
 * Isto é uma tela de entrada, não autorização: o backend do Noma não valida o
 * token. O token fica em localStorage, então um XSS poderia lê-lo; mantenha
 * isso em mente antes de expor o app.
 */
import { reactive, computed } from 'vue'
import * as authApi from '../api/auth'
import { normalizeEmail } from '../lib/authRules'

const STORAGE_KEY = 'noma.auth.v1'

// `VITE_AUTH_REQUIRED=false` desliga a exigência de login (uso local).
export const AUTH_REQUIRED = import.meta.env.VITE_AUTH_REQUIRED !== 'false'

const state = reactive({ token: null, refreshToken: null, user: null })

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persist() {
  try {
    if (!state.token) localStorage.removeItem(STORAGE_KEY)
    else {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ token: state.token, refreshToken: state.refreshToken, user: state.user })
      )
    }
  } catch {
    // Armazenamento bloqueado (modo privado, etc.): a sessão vale só nesta aba.
  }
}

function clearSession() {
  state.token = null
  state.refreshToken = null
  state.user = null
  persist()
}

const saved = readStorage()
if (saved?.token) {
  state.token = saved.token
  state.refreshToken = saved.refreshToken || null
  state.user = saved.user || null
}

export const authState = state

// Conta que o backend recusou (login válido, email fora da lista). Fica só em memória:
// a tela de login mostra qual conta foi negada, sem colocar o email na URL.
export const deniedAccount = reactive({ email: '' })
export const isAuthenticated = computed(() => !!state.token)

function setTokens({ token, refresh_token: refreshToken }) {
  state.token = token
  // /register devolve só `token`; só trocamos o refresh quando ele vem.
  if (refreshToken) state.refreshToken = refreshToken
  persist()
}

function pickUser(data) {
  return data ? { id: data.id, email: data.email, name: data.name || '' } : null
}

export async function signIn({ email, password }) {
  const tokens = await authApi.login({ email: normalizeEmail(email), password })
  state.refreshToken = null
  setTokens(tokens)
  try {
    state.user = pickUser(await authApi.me(state.token))
  } catch {
    state.user = { id: '', email: normalizeEmail(email), name: '' }
  }
  persist()
  deniedAccount.email = '' // login novo: o aviso de acesso negado anterior não vale mais
  restorePromise = Promise.resolve(true) // acabamos de confirmar a sessão
}

/**
 * Cria a conta e já entra. O /register devolve só o token (sem refresh), então
 * fazemos o login em seguida para obter a sessão renovável. Se ele falhar, a
 * conta existe: sinalizamos com `accountCreated` para a tela orientar o usuário.
 */
export async function signUp({ email, password, name }) {
  await authApi.register({ email: normalizeEmail(email), password, name: name?.trim() })
  try {
    await signIn({ email, password })
  } catch (error) {
    error.accountCreated = true
    throw error
  }
}

export function signOut() {
  const token = state.token
  restorePromise = null
  clearSession()
  if (token) {
    // Não esperamos: a sessão local já foi descartada e a tela não deve aguardar a rede.
    authApi.logout(token).catch(() => {})
  }
  return Promise.resolve()
}

let restorePromise = null

/**
 * Confirma a sessão salva (uma vez por carregamento da página).
 * - 401 no `me`: tenta renovar com o refresh token; se falhar, descarta a sessão.
 * - Erro de rede/servidor: mantém a sessão. Não trancamos o app por o Orbit estar fora.
 */
export function restoreSession() {
  if (!state.token) return Promise.resolve(false)
  if (!restorePromise) {
    restorePromise = (async () => {
      try {
        state.user = pickUser(await authApi.me(state.token)) || state.user
        persist()
        return true
      } catch (error) {
        if (error?.response?.status !== 401) return true
      }
      if (state.refreshToken) {
        try {
          setTokens(await authApi.refresh(state.refreshToken))
          state.user = pickUser(await authApi.me(state.token)) || state.user
          persist()
          return true
        } catch (error) {
          if (error?.response?.status && error.response.status !== 401) return true
        }
      }
      clearSession()
      return false
    })()
  }
  return restorePromise.finally(() => {
    // Depois de um logout/login manual, a próxima restauração deve rodar de novo.
    if (!state.token) restorePromise = null
  })
}

let refreshing = null

/**
 * Renova o token com o refresh token (uma renovação por vez, mesmo com várias
 * chamadas falhando juntas). Devolve true se a sessão foi renovada.
 */
export function refreshSession() {
  if (!state.refreshToken) return Promise.resolve(false)
  if (!refreshing) {
    refreshing = authApi
      .refresh(state.refreshToken)
      .then((tokens) => {
        setTokens(tokens)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}
