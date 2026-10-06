import service from './index'

/**
 * Criar simulação
 * @param {Object} data - { project_id, graph_id?, enable_twitter?, enable_reddit? }
 */
export const createSimulation = (data) => {
  return service.post('/api/simulation/create', data)
}

/**
 * Preparar ambiente de simulação (tarefa assíncrona)
 * @param {Object} data - { simulation_id, entity_types?, use_llm_for_profiles?, parallel_profile_count?, force_regenerate? }
 */
export const prepareSimulation = (data) => {
  return service.post('/api/simulation/prepare', data)
}

/**
 * Consultar progresso da tarefa de preparação
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getPrepareStatus = (data) => {
  return service.post('/api/simulation/prepare/status', data)
}

/**
 * Obter status da simulação
 * @param {string} simulationId
 */
export const getSimulation = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}`)
}

/**
 * Obter os Agent Profiles da simulação
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter' (se omitido, o backend escolhe automaticamente com base na configuração da simulação)
 */
export const getSimulationProfiles = (simulationId, platform) => {
  const params = platform ? { platform } : {}
  return service.get(`/api/simulation/${simulationId}/profiles`, { params })
}

/**
 * Obter em tempo real os Agent Profiles em geração
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter' (se omitido, o backend escolhe automaticamente com base na configuração da simulação)
 */
export const getSimulationProfilesRealtime = (simulationId, platform) => {
  const params = platform ? { platform } : {}
  return service.get(`/api/simulation/${simulationId}/profiles/realtime`, { params })
}

/**
 * Obter configuração da simulação
 * @param {string} simulationId
 */
export const getSimulationConfig = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config`)
}

/**
 * Obter em tempo real a configuração da simulação em geração
 * @param {string} simulationId
 * @returns {Promise} retorna as informações de configuração, incluindo metadados e conteúdo da configuração
 */
export const getSimulationConfigRealtime = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/config/realtime`)
}

/**
 * Listar todas as simulações
 * @param {string} projectId - opcional, filtra por ID do projeto
 */
export const listSimulations = (projectId) => {
  const params = projectId ? { project_id: projectId } : {}
  return service.get('/api/simulation/list', { params })
}

/**
 * Iniciar simulação
 * @param {Object} data - { simulation_id, platform?, max_rounds?, enable_graph_memory_update? }
 */
export const startSimulation = (data) => {
  return service.post('/api/simulation/start', data)
}

/**
 * Parar simulação
 * @param {Object} data - { simulation_id }
 */
export const stopSimulation = (data) => {
  return service.post('/api/simulation/stop', data)
}

/**
 * Obter status em tempo real da execução da simulação
 * @param {string} simulationId
 */
export const getRunStatus = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status`)
}

/**
 * Obter status detalhado da execução da simulação (inclui ações recentes)
 * @param {string} simulationId
 */
export const getRunStatusDetail = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/run-status/detail`)
}

/**
 * Obter as postagens da simulação
 * @param {string} simulationId
 * @param {string} [platform] - 'reddit' | 'twitter' (se omitido, o backend escolhe automaticamente com base na configuração da simulação)
 * @param {number} limit - quantidade a retornar
 * @param {number} offset - deslocamento
 */
export const getSimulationPosts = (simulationId, platform, limit = 50, offset = 0) => {
  const params = { limit, offset }
  if (platform) params.platform = platform
  return service.get(`/api/simulation/${simulationId}/posts`, { params })
}

/**
 * Obter linha do tempo da simulação (resumida por rodada)
 * @param {string} simulationId
 * @param {number} startRound - rodada inicial
 * @param {number} endRound - rodada final
 */
export const getSimulationTimeline = (simulationId, startRound = 0, endRound = null) => {
  const params = { start_round: startRound }
  if (endRound !== null) {
    params.end_round = endRound
  }
  return service.get(`/api/simulation/${simulationId}/timeline`, { params })
}

/**
 * Obter estatísticas dos Agents
 * @param {string} simulationId
 */
export const getAgentStats = (simulationId) => {
  return service.get(`/api/simulation/${simulationId}/agent-stats`)
}

/**
 * Obter histórico de ações da simulação
 * @param {string} simulationId
 * @param {Object} params - { limit, offset, platform, agent_id, round_num }
 */
export const getSimulationActions = (simulationId, params = {}) => {
  return service.get(`/api/simulation/${simulationId}/actions`, { params })
}

/**
 * Encerrar ambiente de simulação (saída graciosa)
 * @param {Object} data - { simulation_id, timeout? }
 */
export const closeSimulationEnv = (data) => {
  return service.post('/api/simulation/close-env', data)
}

/**
 * Obter status do ambiente de simulação
 * @param {Object} data - { simulation_id }
 */
export const getEnvStatus = (data) => {
  return service.post('/api/simulation/env-status', data)
}

/**
 * Entrevistar Agents em lote
 * @param {Object} data - { simulation_id, interviews: [{ agent_id, prompt }] }
 */
export const interviewAgents = (data) => {
  return service.post('/api/simulation/interview/batch', data)
}

/**
 * Obter lista de simulações históricas (com detalhes do projeto)
 * Usado para exibir os projetos históricos na página inicial
 * @param {number} limit - limite de quantidade a retornar
 */
export const getSimulationHistory = (limit = 20) => {
  return service.get('/api/simulation/history', { params: { limit } })
}
