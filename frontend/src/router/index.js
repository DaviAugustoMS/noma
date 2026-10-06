import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Auth from '../views/Auth.vue'
import { AUTH_REQUIRED, restoreSession } from '../store/auth'
import { safeRedirect } from '../lib/authRules'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'

const routes = [
  {
    path: '/auth',
    name: 'Auth',
    component: Auth,
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Tela de entrada (não é autorização: o backend não valida o token). Só usa a
// sessão local; o Orbit é consultado uma vez por carregamento e, se estiver
// fora do ar, a sessão salva continua valendo.
router.beforeEach(async (to) => {
  if (!AUTH_REQUIRED) return true
  const loggedIn = await restoreSession()
  if (to.meta.public) {
    return loggedIn && to.name === 'Auth' ? { path: safeRedirect(to.query.redirect) } : true
  }
  return loggedIn ? true : { name: 'Auth', query: { redirect: to.fullPath } }
})

export default router
