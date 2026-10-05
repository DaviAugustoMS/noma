import service from './index'

/**
 * 检查外部依赖（LLM / Zep）状态
 * @returns {Promise<{success: boolean, data: {ok: boolean, llm: Object, zep: Object}}>}
 */
export function getSystemCheck() {
  return service({
    url: '/api/system/check',
    method: 'get',
    timeout: 8000
  })
}
