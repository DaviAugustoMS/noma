import service from './index'

/**
 * Gera a ontologia (envia documentos e requisitos da simulação)
 * @param {Object} data - contém files, simulation_requirement, project_name etc.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return service({
    url: '/api/graph/ontology/generate',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * Nova tentativa de geração da ontologia (reutiliza os arquivos já salvos no servidor, sem necessidade de novo envio)
 * @param {string} projectId
 * @returns {Promise}
 */
export function retryOntology(projectId) {
  return service({
    url: '/api/graph/ontology/retry',
    method: 'post',
    data: { project_id: projectId }
  })
}

/**
 * Constrói o grafo
 * @param {Object} data - contém project_id, graph_name etc.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return service({
    url: '/api/graph/build',
    method: 'post',
    data
  })
}

/**
 * Consulta o status da tarefa
 * @param {String} taskId - ID da tarefa
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * Obtém os dados do grafo
 * @param {String} graphId - ID do grafo
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * Obtém as informações do projeto
 * @param {String} projectId - ID do projeto
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}
