import service from './index'

/**
 * Gasto de tokens do LLM.
 * @param {{projectId?: string, simulationId?: string, reportId?: string}} scope
 *   sem nenhum id devolve o total geral
 */
export function getUsage({ projectId, simulationId, reportId } = {}) {
  const params = {}
  if (projectId && projectId !== 'new') params.project_id = projectId
  if (simulationId) params.simulation_id = simulationId
  if (reportId) params.report_id = reportId
  return service({ url: '/api/usage', method: 'get', params })
}
