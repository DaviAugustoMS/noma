import axios from 'axios'

// O login e o cadastro falam direto com o Zeep Orbit (a senha não passa pelo
// backend do Noma). O CORS do Orbit libera qualquer origem nesses endpoints.
export const ORBIT_URL = (import.meta.env.VITE_ORBIT_URL || 'https://orbit.dlec.app').replace(/\/+$/, '')
export const ORBIT_APP = import.meta.env.VITE_ORBIT_APP || 'mirofish'

// Instância própria: não herda os interceptors do backend nem loga erros
// (o objeto de erro do axios carrega o corpo da requisição, que contém a senha).
const http = axios.create({
  baseURL: `${ORBIT_URL}/${ORBIT_APP}/auth`,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

const bearer = (token) => ({ headers: { Authorization: `Bearer ${token}` } })

export async function register({ email, password, name }) {
  const body = { email, password }
  if (name) body.name = name
  const { data } = await http.post('/register', body)
  return data // { token }
}

export async function login({ email, password }) {
  const { data } = await http.post('/login', { email, password })
  return data // { token, refresh_token }
}

export async function refresh(refreshToken) {
  const { data } = await http.post('/refresh', { refresh_token: refreshToken })
  return data // { token, refresh_token }
}

export async function me(token) {
  const { data } = await http.get('/me', bearer(token))
  return data
}

export async function logout(token) {
  await http.post('/logout', null, bearer(token))
}
