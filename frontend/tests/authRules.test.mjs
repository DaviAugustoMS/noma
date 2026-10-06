import test from 'node:test'
import assert from 'node:assert/strict'
import {
  MIN_PASSWORD_LENGTH,
  authErrorKey,
  normalizeEmail,
  safeRedirect,
  validateAuthForm
} from '../src/lib/authRules.js'

const ok = { email: 'ana@exemplo.com', password: 'senha-forte-1', confirm: 'senha-forte-1' }

test('formulário válido não gera erros', () => {
  assert.deepEqual(validateAuthForm('login', ok), {})
  assert.deepEqual(validateAuthForm('register', ok), {})
})

test('email: obrigatório, formato e normalização', () => {
  assert.equal(validateAuthForm('login', { ...ok, email: '  ' }).email.key, 'emailRequired')
  for (const bad of ['ana', 'ana@', 'ana@exemplo', 'a na@x.com', '@x.com']) {
    assert.equal(validateAuthForm('login', { ...ok, email: bad }).email.key, 'emailInvalid', bad)
  }
  assert.equal(normalizeEmail('  Ana@Exemplo.COM '), 'ana@exemplo.com')
  assert.equal(normalizeEmail(undefined), '')
})

test('senha: no login só exige preenchimento; no cadastro, tamanho mínimo', () => {
  assert.equal(validateAuthForm('login', { ...ok, password: '' }).password.key, 'passwordRequired')
  assert.deepEqual(validateAuthForm('login', { ...ok, password: 'x' }), {})

  const short = validateAuthForm('register', { ...ok, password: 'curta', confirm: 'curta' })
  assert.equal(short.password.key, 'passwordShort')
  assert.deepEqual(short.password.params, { min: MIN_PASSWORD_LENGTH })
})

test('cadastro: confirmação precisa conferir (e só é checada com senha válida)', () => {
  assert.equal(validateAuthForm('register', { ...ok, confirm: 'outra-senha' }).confirm.key, 'passwordMismatch')
  const both = validateAuthForm('register', { ...ok, password: 'curta', confirm: 'x' })
  assert.equal(both.password.key, 'passwordShort')
  assert.equal(both.confirm, undefined)
  assert.deepEqual(validateAuthForm('login', { ...ok, confirm: 'qualquer' }), {})
})

test('erros do axios viram chaves de i18n', () => {
  const http = (status) => ({ response: { status } })
  assert.equal(authErrorKey(http(401)), 'invalidCredentials')
  assert.equal(authErrorKey(http(409)), 'emailTaken')
  assert.equal(authErrorKey(http(400)), 'invalid')
  assert.equal(authErrorKey(http(422)), 'invalid')
  assert.equal(authErrorKey(http(429)), 'rateLimited')
  assert.equal(authErrorKey(http(500)), 'unknown')
  assert.equal(authErrorKey({ code: 'ERR_NETWORK' }), 'network')
  assert.equal(authErrorKey({ code: 'ECONNABORTED' }), 'network')
  assert.equal(authErrorKey({ request: {} }), 'network')
  assert.equal(authErrorKey(new Error('boom')), 'unknown')
  assert.equal(authErrorKey(undefined), 'unknown')
})

test('redirecionamento só aceita caminhos internos', () => {
  assert.equal(safeRedirect('/simulation/abc?x=1'), '/simulation/abc?x=1')
  assert.equal(safeRedirect('/'), '/')
  for (const bad of [
    'https://evil.example', '//evil.example', '/\\evil.example', 'javascript:alert(1)',
    'evil', '', undefined, null, ['/x'], '/ok\nSet-Cookie: a=b', '/auth', '/auth?redirect=/'
  ]) {
    assert.equal(safeRedirect(bad), '/', String(bad))
  }
  assert.equal(safeRedirect('https://evil.example', '/home'), '/home')
})

import { apiAuthAction } from '../src/lib/authRules.js'

test('erros do backend: só reage aos códigos do guard de autenticação', () => {
  const err = (status, code) => ({ response: { status, data: { code } } })
  assert.equal(apiAuthAction(err(401, 'auth_invalid')), 'refresh')
  assert.equal(apiAuthAction(err(401, 'auth_required')), 'refresh')
  assert.equal(apiAuthAction(err(401, 'auth_invalid'), { alreadyRetried: true }), 'signout')
  assert.equal(apiAuthAction(err(403, 'auth_forbidden')), 'denied')
  // outros 401/403/503 e erros sem resposta seguem o fluxo normal
  assert.equal(apiAuthAction(err(401, undefined)), null)
  assert.equal(apiAuthAction(err(403, 'outra_coisa')), null)
  assert.equal(apiAuthAction(err(503, 'auth_unavailable')), null)
  assert.equal(apiAuthAction({ code: 'ERR_NETWORK' }), null)
  assert.equal(apiAuthAction(undefined), null)
})

import { logLevelClass } from '../src/lib/logLevel.js'

test('console de log do relatório: nível e palavras (pt/zh) classificam a linha', () => {
  assert.equal(logLevelClass('[10:00:01] ERROR: falha ao gerar a seção'), 'error')
  assert.equal(logLevelClass('[10:00:01] INFO: houve um erro ao consultar o grafo'), 'error')
  assert.equal(logLevelClass('[10:00:01] INFO: 生成章节时发生错误'), 'error')
  assert.equal(logLevelClass('[10:00:01] WARNING: grafo vazio'), 'warning')
  assert.equal(logLevelClass('[10:00:01] INFO: aviso: poucos fatos encontrados'), 'warning')
  assert.equal(logLevelClass('[10:00:01] INFO: 警告 配置缺失'), 'warning')
  assert.equal(logLevelClass('[10:00:01] INFO: seção concluída'), '')
  assert.equal(logLevelClass('[10:00:01] INFO: terror e interrompido'), '')   // sem falso positivo no meio da palavra
  assert.equal(logLevelClass(undefined), '')
})
