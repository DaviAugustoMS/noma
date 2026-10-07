/**
 * Armazenamento temporário de arquivos e requisitos pendentes de upload
 * Usado para redirecionar imediatamente ao clicar em iniciar o motor na página inicial, fazendo a chamada de API somente na página Process
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  seedUsage: null,
  isPending: false
})

export function setPendingUpload(files, requirement, seedUsage = null) {
  state.files = files
  state.simulationRequirement = requirement
  state.seedUsage = seedUsage
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    seedUsage: state.seedUsage,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.seedUsage = null
  state.isPending = false
}

export default state
