import service from './index'

/**
 * Inicia a geração do relatório
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return service.post('/api/report/generate', data)
}

/**
 * Obtém o status da geração do relatório
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * Obtém os logs do Agent (incremental)
 * @param {string} reportId
 * @param {number} fromLine - a partir de qual linha obter
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * Obtém os logs do console (incremental)
 * @param {string} reportId
 * @param {number} fromLine - a partir de qual linha obter
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * Baixa o relatório em Markdown. É um GET autenticado, então não dá para usar um link
 * simples: o arquivo vem como Blob e o download é disparado no navegador.
 * @param {string} reportId
 * @returns {Promise<Blob>}
 */
export const downloadReport = (reportId) => {
  return service.get(`/api/report/${encodeURIComponent(reportId)}/download`, { responseType: 'blob' })
}

/**
 * Obtém os detalhes do relatório
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * Conversa com o Report Agent
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return service.post('/api/report/chat', data)
}
