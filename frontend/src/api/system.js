import service from './index'

/**
 * Verificar status das dependências externas (LLM / Zep)
 * @returns {Promise<{success: boolean, data: {ok: boolean, llm: Object, zep: Object}}>}
 */
export function getSystemCheck() {
  return service({
    url: '/api/system/check',
    method: 'get',
    timeout: 8000
  })
}
