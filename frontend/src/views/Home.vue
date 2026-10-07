<template>
  <div
    class="home-shell"
    ref="shellRef"
    @pointermove="onShellPointerMove"
  >
    <div class="spotlight" aria-hidden="true"></div>

    <!-- Barra de navegação superior -->
    <nav class="navbar" :class="{ scrolled: isScrolled }">
      <div class="nav-brand">
        <span class="brand-orb"></span>NOMA
      </div>
      <div class="nav-links">
        <div class="health-chip" :class="`is-${healthLevel}`" :title="healthMessage" role="status">
          <span class="health-dot"></span>
          <span class="health-text">{{ healthMessage }}</span>
        </div>
        <UserMenu />
        <LanguageSwitcher />
        <a href="https://github.com/DaviAugustoMS/noma" target="_blank" rel="noopener" class="github-link">
          {{ $t('nav.visitGithub') }} <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- Hero -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row reveal-up" style="--d: 0.05s">
            <span class="bio-tag">{{ $t('home.tagline') }}</span>
            <span class="version-text">{{ $t('home.version') }}</span>
          </div>

          <h1 class="main-title">
            <span class="title-line reveal-up" style="--d: 0.15s">{{ $t('home.heroTitle1') }}</span>
            <span class="title-line wave-line" :aria-label="$t('home.heroTitle2')" :style="{ '--n': Math.max(heroChars.length - 1, 1) }">
              <span
                v-for="(ch, i) in heroChars"
                :key="i + ch"
                class="wave-char"
                :style="{ '--i': i }"
                aria-hidden="true"
              >{{ ch === ' ' ? ' ' : ch }}</span>
            </span>
          </h1>

          <div class="hero-desc reveal-up" style="--d: 0.55s">
            <p>
              <i18n-t keypath="home.heroDesc" tag="span">
                <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
                <template #agentScale><span class="highlight-glow">{{ $t('home.heroDescAgentScale') }}</span></template>
                <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
              </i18n-t>
            </p>
            <p class="slogan-text">
              {{ $t('home.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>

          <button class="dive-btn reveal-up" style="--d: 0.75s" @click="scrollToBottom">
            <span class="dive-ring"></span>
            <span class="dive-arrow">↓</span>
          </button>
        </div>

        <div class="hero-right">
          <div class="orb-stage">
            <span class="orb-ring ring-a"></span>
            <span class="orb-ring ring-b"></span>
            <span class="orb-ring ring-c"></span>
            <span class="orbiter o1"></span>
            <span class="orbiter o2"></span>
            <span class="orbiter o3"></span>
            <div class="logo-container">
              <img src="../assets/logo/noma-mark.svg" alt="Noma" class="hero-logo" />
            </div>
          </div>
        </div>
      </section>

      <!-- Dashboard -->
      <section class="dashboard-section">
        <div class="left-panel">
          <div class="panel-header reveal" v-reveal>
            <span class="status-dot"></span> {{ $t('home.systemStatus') }}
          </div>

          <h2 class="section-title reveal" v-reveal>{{ $t('home.systemReady') }}</h2>
          <p class="section-desc reveal" v-reveal>
            {{ $t('home.systemReadyDesc') }}
          </p>

          <div class="metrics-row">
            <div class="metric-card reveal" v-reveal style="--d: 0.05s">
              <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
              <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
            </div>
            <div class="metric-card reveal" v-reveal style="--d: 0.15s">
              <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
              <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
            </div>
          </div>

          <div class="steps-container">
            <div class="steps-header reveal" v-reveal>
              <span class="diamond-icon">◇</span> {{ $t('home.workflowSequence') }}
            </div>
            <div class="workflow-list">
              <span class="timeline-track"></span>
              <span class="timeline-fill" :style="{ transform: `scaleY(${timelineProgress})` }"></span>
              <div
                v-for="n in 5"
                :key="n"
                class="workflow-item reveal"
                v-reveal="onStepRevealed"
                :data-step="n"
                :style="{ '--d': `${(n - 1) * 0.04}s` }"
              >
                <span class="step-num">0{{ n }}</span>
                <div class="step-info">
                  <div class="step-title">{{ $t(`home.step0${n}Title`) }}</div>
                  <div class="step-desc">{{ $t(`home.step0${n}Desc`) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="right-panel">
          <div
            class="console-box reveal"
            v-reveal
            ref="consoleRef"
            @pointermove="onConsolePointerMove"
            @pointerleave="onConsolePointerLeave"
          >
            <div class="console-glare" aria-hidden="true"></div>

            <!-- Gerar semente e prompt a partir do link de um site -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.siteLabel') }}</span>
              </div>
              <form class="site-row" @submit.prevent="generateFromSite">
                <input
                  v-model="siteUrl"
                  class="site-input"
                  type="url"
                  inputmode="url"
                  autocomplete="off"
                  spellcheck="false"
                  :placeholder="$t('home.sitePlaceholder')"
                  :disabled="loading || siteLoading"
                />
                <button class="site-btn" type="submit" :disabled="!siteUrl.trim() || loading || siteLoading">
                  {{ siteLoading ? $t('home.siteLoading') : $t('home.siteButton') }}
                </button>
              </form>
              <p v-if="siteError" class="site-msg site-error" role="alert">{{ siteError }}</p>
              <p v-else-if="siteDone" class="site-msg" role="status">{{ $t('home.siteDone') }}</p>
            </div>

            <!-- Área de upload -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.realitySeed') }}</span>
                <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
              </div>

              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />

                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">
                    <span class="pulse-ring"></span>
                    <span class="pulse-ring delay"></span>
                    <span class="icon-glyph">↑</span>
                  </div>
                  <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                  <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
                </div>

                <transition-group v-else name="file" tag="div" class="file-list">
                  <div v-for="(file, index) in files" :key="file.name + index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </transition-group>
              </div>
            </div>

            <div class="console-divider">
              <span>{{ $t('home.inputParams') }}</span>
            </div>

            <!-- Área de entrada -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="$t('home.promptPlaceholder')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('home.engineBadge') }}</div>
              </div>
            </div>

            <!-- Botão de iniciar -->
            <div class="console-section btn-section">
              <transition name="file">
                <div v-if="healthLevel === 'bad'" class="health-banner" role="alert">
                  <span class="banner-icon">!</span>
                  <span>{{ healthMessage }}</span>
                </div>
              </transition>
              <button
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span class="btn-shimmer"></span>
                <span v-if="!loading" class="btn-label">{{ $t('home.startEngine') }}</span>
                <span v-else class="btn-label">{{ $t('home.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Banco de dados de projetos históricos -->
      <div class="history-wrap reveal" v-reveal>
        <HistoryDatabase />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import UserMenu from '../components/UserMenu.vue'
import { getSystemCheck } from '../api/system'
import { generateSeedFromUrl } from '../api/graph'

const router = useRouter()
const { t } = useI18n()

// Dados do formulário
const formData = ref({
  simulationRequirement: ''
})

// Lista de arquivos
const files = ref([])

// Estado
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// Referência do input de arquivo
const fileInput = ref(null)

// Propriedade computada: se é possível enviar
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// Dispara a seleção de arquivo
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// Trata a seleção de arquivo
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// Trata eventos de arrastar e soltar
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return

  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// Adicionar arquivo
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// Gerar semente e prompt a partir do link de um site
const siteUrl = ref('')
const siteLoading = ref(false)
const siteError = ref('')
const siteDone = ref(false)

const hostSlug = (value) => {
  try {
    const host = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`).hostname
    return host.replace(/^www\./, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'site'
  } catch {
    return 'site'
  }
}

const generateFromSite = async () => {
  if (siteLoading.value || loading.value) return
  siteLoading.value = true
  siteError.value = ''
  siteDone.value = false
  try {
    const res = await generateSeedFromUrl(siteUrl.value.trim())
    const { seed_markdown: seed, simulation_requirement: requirement } = res.data
    const name = `semente-${hostSlug(siteUrl.value.trim())}.md`
    // Substitui a semente gerada antes para o mesmo site; arquivos enviados à mão ficam
    files.value = files.value.filter((f) => f.name !== name)
    files.value.push(new File([seed], name, { type: 'text/markdown' }))
    formData.value.simulationRequirement = requirement
    siteDone.value = true
  } catch (e) {
    // Não logamos o erro: o objeto do axios carrega a requisição inteira
    siteError.value = e?.response?.data?.error || e?.message || t('common.error')
  } finally {
    siteLoading.value = false
  }
}

// Remover arquivo
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// Rolar até o final
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Iniciar simulação - redireciona imediatamente, a chamada de API é feita na página Process
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  // Armazena os dados pendentes de upload
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)

    // Redireciona imediatamente para a página Process (usando um identificador especial para indicar novo projeto)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}

/* ---------------------------------------------------------------------------
   Visual / animation layer (não altera a lógica acima)
   --------------------------------------------------------------------------- */

const shellRef = ref(null)
const consoleRef = ref(null)
const isScrolled = ref(false)
const revealedSteps = ref(new Set())

// título animado: cada caractere sobe em onda
const heroChars = computed(() => Array.from(t('home.heroTitle2')))

// linha do tempo acende conforme os passos aparecem
const timelineProgress = computed(() => revealedSteps.value.size / 5)

const onStepRevealed = (el) => {
  const n = Number(el.dataset.step)
  if (n) {
    const next = new Set(revealedSteps.value)
    next.add(n)
    revealedSteps.value = next
  }
}

const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// diretiva v-reveal: adiciona .in quando o elemento entra na viewport
let revealObserver = null
const getObserver = () => {
  if (revealObserver) return revealObserver
  revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return
      const el = entry.target
      el.classList.add('in')
      const cb = el.__revealCb
      if (typeof cb === 'function') cb(el)
      revealObserver.unobserve(el)
    })
  }, { threshold: 0.05, rootMargin: '0px 0px -6% 0px' })
  return revealObserver
}

const vReveal = {
  mounted(el, binding) {
    if (typeof IntersectionObserver === 'undefined' || prefersReducedMotion()) {
      el.classList.add('in')
      if (typeof binding.value === 'function') binding.value(el)
      return
    }
    if (typeof binding.value === 'function') el.__revealCb = binding.value
    getObserver().observe(el)
  },
  unmounted(el) {
    revealObserver?.unobserve(el)
  }
}

// holofote que segue o mouse
let spotRaf = 0
const onShellPointerMove = (e) => {
  if (spotRaf) return
  spotRaf = requestAnimationFrame(() => {
    spotRaf = 0
    const el = shellRef.value
    if (!el) return
    el.style.setProperty('--mx', `${e.clientX}px`)
    el.style.setProperty('--my', `${e.clientY}px`)
  })
}

// inclinação 3D leve do console
const onConsolePointerMove = (e) => {
  if (prefersReducedMotion()) return
  const el = consoleRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const px = (e.clientX - rect.left) / rect.width
  const py = (e.clientY - rect.top) / rect.height
  el.style.setProperty('--rx', `${((0.5 - py) * 3.2).toFixed(2)}deg`)
  el.style.setProperty('--ry', `${((px - 0.5) * 3.8).toFixed(2)}deg`)
  el.style.setProperty('--gx', `${(px * 100).toFixed(1)}%`)
  el.style.setProperty('--gy', `${(py * 100).toFixed(1)}%`)
}

const onConsolePointerLeave = () => {
  const el = consoleRef.value
  if (!el) return
  el.style.setProperty('--rx', '0deg')
  el.style.setProperty('--ry', '0deg')
}

const onScroll = () => {
  isScrolled.value = window.scrollY > 24
}

// ---------- Verificação de saúde dos serviços (LLM / Zep) ----------
const health = ref(null) // null = verificando; { backend: false } = backend offline; senão dados do /api/system/check
let healthTimer = null

const healthProblem = computed(() => {
  const h = health.value
  if (!h) return null
  if (h.backend === false) return { key: 'backendDown' }
  const { llm, zep } = h
  if (!llm.reachable) {
    const keys = {
      not_configured: 'llmNotConfigured',
      unauthorized: 'llmUnauthorized',
      server_error: 'llmServerError',
      timeout: 'llmTimeout'
    }
    return { key: keys[llm.reason] || 'llmDown', endpoint: llm.endpoint }
  }
  if (!zep.reachable) {
    return { key: zep.reason === 'not_configured' ? 'zepNotConfigured' : 'zepDown' }
  }
  return null
})

const healthLevel = computed(() => {
  if (!health.value) return 'checking'
  return healthProblem.value ? 'bad' : 'ok'
})

const healthMessage = computed(() => {
  if (healthLevel.value === 'checking') return t('home.health.checking')
  if (healthLevel.value === 'ok') return t('home.health.ok')
  const problem = healthProblem.value
  return t(`home.health.${problem.key}`, { endpoint: problem.endpoint || '' })
})

const refreshHealth = async () => {
  try {
    const res = await getSystemCheck()
    health.value = res.data
  } catch (e) {
    health.value = { backend: false }
  }
}

onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
  refreshHealth()
  healthTimer = setInterval(refreshHealth, 20000)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  if (healthTimer) clearInterval(healthTimer)
  if (spotRaf) cancelAnimationFrame(spotRaf)
  revealObserver?.disconnect()
  revealObserver = null
})
</script>

<style scoped>
.home-shell {
  --mx: 50vw;
  --my: 30vh;
  position: relative;
  min-height: 100vh;
  color: var(--ink);
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  overflow-x: hidden;
}

/* holofote bioluminescente que acompanha o cursor */
.spotlight {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background: radial-gradient(520px circle at var(--mx) var(--my), rgba(25, 227, 196, 0.1), transparent 65%);
}

.main-content,
.navbar {
  position: relative;
  z-index: 1;
}

/* ---------- Navbar ---------- */
.navbar {
  position: sticky;
  top: 12px;
  margin: 12px auto 0;
  width: min(1320px, calc(100% - 32px));
  height: 60px;
  padding: 0 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--glass-line);
  border-radius: 18px;
  background: rgba(8, 36, 54, 0.32);
  backdrop-filter: blur(14px) saturate(1.2);
  -webkit-backdrop-filter: blur(14px) saturate(1.2);
  transition: background 0.4s, box-shadow 0.4s, border-color 0.4s, transform 0.5s var(--ease-out);
  animation: nav-drop 0.9s var(--ease-out) both;
  z-index: 50;
}

.navbar.scrolled {
  background: var(--glass-strong);
  border-color: var(--glass-line-strong);
  box-shadow: 0 14px 44px rgba(0, 8, 18, 0.55);
}

.nav-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 3px;
  text-shadow: 0 0 20px rgba(25, 227, 196, 0.45);
}

.brand-orb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #fff, var(--bio-teal) 45%, transparent 72%);
  box-shadow: 0 0 16px var(--bio-teal);
  animation: orb-pulse 2.8s ease-in-out infinite;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 22px;
}

.github-link {
  color: var(--ink-soft);
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: color 0.3s, text-shadow 0.3s;
}

.github-link:hover {
  color: var(--bio-teal);
  text-shadow: 0 0 14px rgba(25, 227, 196, 0.6);
}

.github-link .arrow {
  transition: transform 0.3s var(--ease-out);
}

.github-link:hover .arrow {
  transform: translate(3px, -3px);
}

/* ---------- Layout ---------- */
.main-content {
  width: min(1320px, calc(100% - 32px));
  margin: 0 auto;
  padding: 0 0 80px;
}

/* ---------- Hero ---------- */
.hero-section {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  align-items: center;
  gap: 40px;
  min-height: calc(100vh - 100px);
  padding: 40px 12px 20px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}

.bio-tag {
  position: relative;
  padding: 7px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #02221c;
  background: linear-gradient(110deg, var(--bio-teal), var(--bio-cyan));
  border-radius: 999px;
  box-shadow: var(--glow-teal);
  overflow: hidden;
}

.bio-tag::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 30%, rgba(255, 255, 255, 0.55) 50%, transparent 70%);
  transform: translateX(-120%);
  animation: sheen 4.5s ease-in-out infinite;
}

.version-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: var(--ink-mute);
}

.main-title {
  font-size: clamp(2.6rem, 6.4vw, 5.6rem);
  line-height: 1.04;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 30px;
  display: flex;
  flex-direction: column;
}

.title-line {
  display: block;
}

.wave-line {
  display: inline-block;
  white-space: pre-wrap;
  filter: drop-shadow(0 0 22px rgba(25, 227, 196, 0.35));
}

.wave-char {
  display: inline-block;
  opacity: 0;
  /* gradiente por letra: teal -> cyan -> violeta ao longo da palavra */
  color: color-mix(in oklab, var(--bio-teal), var(--bio-violet) calc(var(--i) / var(--n, 1) * 100%));
  transform: translateY(0.7em) rotate(4deg);
  animation:
    char-in 0.9s var(--ease-out) forwards,
    char-bob 5s ease-in-out infinite;
  animation-delay: calc(0.35s + var(--i) * 0.045s), calc(1.4s + var(--i) * 0.12s);
}

.hero-desc {
  max-width: 560px;
  color: var(--ink-soft);
  font-size: 1.05rem;
  line-height: 1.75;
  margin-bottom: 36px;
}

.hero-desc p + p {
  margin-top: 16px;
}

.highlight-bold {
  color: var(--ink);
  font-weight: 700;
}

.highlight-glow {
  color: var(--bio-teal);
  font-weight: 700;
  text-shadow: 0 0 16px rgba(25, 227, 196, 0.55);
}

.highlight-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.92em;
  padding: 2px 8px;
  border-radius: 6px;
  color: var(--bio-cyan);
  background: rgba(60, 200, 255, 0.1);
  border: 1px solid rgba(60, 200, 255, 0.22);
}

.slogan-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.92rem;
  color: var(--ink);
  letter-spacing: 0.5px;
}

.blinking-cursor {
  color: var(--bio-teal);
  animation: blink 1.1s steps(2, start) infinite;
}

.dive-btn {
  position: relative;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  border: 1px solid var(--glass-line-strong);
  background: rgba(8, 36, 54, 0.5);
  color: var(--bio-teal);
  font-size: 1.3rem;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: transform 0.4s var(--ease-out), box-shadow 0.4s, background 0.3s;
}

.dive-btn:hover {
  transform: translateY(4px);
  background: rgba(25, 227, 196, 0.14);
  box-shadow: var(--glow-teal);
}

.dive-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 1px solid rgba(25, 227, 196, 0.45);
  animation: ripple 2.6s ease-out infinite;
}

.dive-arrow {
  animation: bob 2.2s ease-in-out infinite;
}

/* ---------- Orb ---------- */
.hero-right {
  display: grid;
  place-items: center;
}

.orb-stage {
  position: relative;
  width: min(440px, 80vw);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  animation: float 8s ease-in-out infinite;
}

.orb-stage::before {
  content: '';
  position: absolute;
  inset: 8%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(25, 227, 196, 0.35), rgba(60, 200, 255, 0.12) 55%, transparent 72%);
  filter: blur(28px);
  animation: breathe 6s ease-in-out infinite;
}

.orb-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(120, 240, 235, 0.22);
}

.ring-a { inset: 2%;  animation: spin 40s linear infinite; border-style: dashed; }
.ring-b { inset: 10%; animation: spin 26s linear infinite reverse; border-color: rgba(60, 200, 255, 0.3); }
.ring-c { inset: 19%; animation: spin 18s linear infinite; border-color: rgba(182, 255, 106, 0.22); }

.orbiter {
  position: absolute;
  inset: 0;
  animation: spin var(--t, 14s) linear infinite;
}

.orbiter::after {
  content: '';
  position: absolute;
  top: 1%;
  left: 50%;
  width: var(--s, 10px);
  height: var(--s, 10px);
  margin-left: calc(var(--s, 10px) / -2);
  border-radius: 50%;
  background: var(--c, var(--bio-teal));
  box-shadow: 0 0 18px var(--c, var(--bio-teal)), 0 0 40px var(--c, var(--bio-teal));
}

.o1 { --t: 16s; --c: var(--bio-teal); --s: 10px; }
.o2 { --t: 24s; --c: var(--bio-cyan); --s: 8px; inset: 9%; animation-direction: reverse; }
.o3 { --t: 11s; --c: var(--bio-lime); --s: 6px; inset: 18%; }

.logo-container {
  position: relative;
  width: 56%;
  aspect-ratio: 1;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid var(--glass-line-strong);
  box-shadow: 0 0 60px rgba(25, 227, 196, 0.35), inset 0 0 40px rgba(2, 11, 20, 0.5);
}

.hero-logo {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 1.2s var(--ease-out);
}

.orb-stage:hover .hero-logo {
  transform: scale(1.08) rotate(2deg);
}

/* ---------- Dashboard ---------- */
.dashboard-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
  padding: 40px 0 20px;
  align-items: start;
}

.left-panel {
  padding: 8px 8px 8px 12px;
}

.panel-header {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--bio-teal);
  margin-bottom: 18px;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--bio-teal);
  box-shadow: 0 0 12px var(--bio-teal);
  animation: orb-pulse 2s ease-in-out infinite;
}

.section-title {
  font-size: clamp(1.8rem, 3.2vw, 2.6rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 14px;
}

.section-desc {
  color: var(--ink-soft);
  line-height: 1.7;
  max-width: 520px;
  margin-bottom: 28px;
}

.metrics-row {
  display: flex;
  gap: 16px;
  margin-bottom: 40px;
}

.metric-card {
  flex: 1;
  padding: 20px;
  border: 1px solid var(--glass-line);
  border-radius: 18px;
  background: var(--glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: transform 0.5s var(--ease-out), border-color 0.4s, box-shadow 0.4s;
}

.metric-card:hover {
  transform: translateY(-6px);
  border-color: var(--glass-line-strong);
  box-shadow: var(--glow-cyan);
}

.metric-value {
  font-size: 1.9rem;
  font-weight: 700;
  background: linear-gradient(100deg, var(--bio-teal), var(--bio-cyan));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 6px;
}

.metric-label {
  font-size: 0.8rem;
  color: var(--ink-mute);
  line-height: 1.5;
}

.steps-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin-bottom: 22px;
}

.diamond-icon {
  color: var(--bio-cyan);
  margin-right: 6px;
}

/* linha do tempo vertical que "acende" */
.workflow-list {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-left: 34px;
}

.timeline-track,
.timeline-fill {
  position: absolute;
  left: 11px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  border-radius: 2px;
}

.timeline-track {
  background: rgba(127, 176, 196, 0.18);
}

.timeline-fill {
  background: linear-gradient(180deg, var(--bio-teal), var(--bio-cyan), var(--bio-violet));
  box-shadow: 0 0 12px var(--bio-cyan);
  transform-origin: top;
  transition: transform 1s var(--ease-out);
}

.workflow-item {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 14px;
  transition: background 0.4s, border-color 0.4s, transform 0.5s var(--ease-out);
}

.workflow-item::before {
  content: '';
  position: absolute;
  left: -29px;
  top: 22px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--abyss-1);
  border: 2px solid var(--ink-mute);
  transition: border-color 0.5s 0.2s, background 0.5s 0.2s, box-shadow 0.5s 0.2s;
}

.workflow-item.in::before {
  border-color: var(--bio-teal);
  background: var(--bio-teal);
  box-shadow: 0 0 12px var(--bio-teal);
}

.workflow-item:hover {
  background: var(--glass);
  border-color: var(--glass-line);
  transform: translateX(6px);
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--bio-cyan);
  padding-top: 2px;
}

.step-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--ink-mute);
  line-height: 1.6;
}

/* ---------- Console ---------- */
.right-panel {
  perspective: 1200px;
}

.console-box {
  --rx: 0deg;
  --ry: 0deg;
  --gx: 50%;
  --gy: 0%;
  position: relative;
  border: 1px solid var(--glass-line-strong);
  border-radius: 24px;
  background: var(--glass-strong);
  backdrop-filter: blur(20px) saturate(1.3);
  -webkit-backdrop-filter: blur(20px) saturate(1.3);
  box-shadow: 0 30px 80px rgba(0, 8, 18, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.03), 0 0 60px rgba(25, 227, 196, 0.08);
  transform: rotateX(var(--rx)) rotateY(var(--ry));
  transition: transform 0.5s var(--ease-out), opacity 0.9s var(--ease-out), box-shadow 0.4s;
  overflow: hidden;
}

.console-glare {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(420px circle at var(--gx) var(--gy), rgba(120, 255, 235, 0.1), transparent 60%);
}

.console-section {
  padding: 22px 24px;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 14px;
}

.console-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--bio-teal);
}

.console-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: var(--ink-mute);
}

.upload-zone {
  position: relative;
  min-height: 170px;
  display: grid;
  place-items: center;
  padding: 20px;
  border: 1px dashed rgba(120, 240, 235, 0.35);
  border-radius: 18px;
  background: rgba(2, 11, 20, 0.45);
  cursor: pointer;
  transition: border-color 0.3s, background 0.3s, box-shadow 0.4s, transform 0.4s var(--ease-out);
}

.upload-zone:hover {
  border-color: var(--bio-teal);
  background: rgba(25, 227, 196, 0.06);
}

.upload-zone.drag-over {
  border-style: solid;
  border-color: var(--bio-cyan);
  background: rgba(60, 200, 255, 0.1);
  box-shadow: inset 0 0 40px rgba(60, 200, 255, 0.2), var(--glow-cyan);
  transform: scale(1.012);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  position: relative;
  width: 54px;
  height: 54px;
  margin: 0 auto 14px;
  display: grid;
  place-items: center;
}

.icon-glyph {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  font-size: 1.3rem;
  color: var(--bio-teal);
  background: rgba(25, 227, 196, 0.12);
  border: 1px solid var(--glass-line-strong);
  animation: bob 2.4s ease-in-out infinite;
}

.pulse-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(25, 227, 196, 0.55);
  animation: ripple 2.8s ease-out infinite;
}

.pulse-ring.delay {
  animation-delay: 1.4s;
}

.upload-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 0.82rem;
  color: var(--ink-mute);
}

.file-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgba(8, 36, 54, 0.7);
  border: 1px solid var(--glass-line);
}

.file-name {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid var(--glass-line);
  background: transparent;
  color: var(--ink-soft);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.3s var(--ease-out);
}

.remove-btn:hover {
  background: rgba(255, 107, 129, 0.2);
  color: #ff8fa0;
  transform: rotate(90deg);
}

.file-enter-active,
.file-leave-active {
  transition: all 0.45s var(--ease-out);
}

.file-enter-from {
  opacity: 0;
  transform: translateX(-24px) scale(0.96);
}

.file-leave-to {
  opacity: 0;
  transform: translateX(24px) scale(0.96);
}

.console-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 24px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--ink-mute);
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--glass-line-strong), transparent);
}

.site-row {
  display: flex;
  gap: 10px;
}

.site-input {
  flex: 1;
  min-width: 0;
  padding: 12px 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.88rem;
  color: var(--ink);
  background: rgba(2, 11, 20, 0.5);
  border: 1px solid var(--glass-line);
  border-radius: 12px;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.4s;
}

.site-input::placeholder {
  color: var(--ink-mute);
}

.site-input:focus {
  border-color: var(--bio-teal);
  box-shadow: 0 0 0 3px rgba(25, 227, 196, 0.14);
}

.site-btn {
  flex: none;
  padding: 0 16px;
  border: 1px solid var(--bio-teal);
  border-radius: 12px;
  background: rgba(25, 227, 196, 0.1);
  color: var(--bio-teal);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
}

.site-btn:disabled,
.site-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.site-msg {
  margin-top: 8px;
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--ink-soft);
}

.site-error {
  color: #ff9d9d;
}

@media (max-width: 520px) {
  .site-row {
    flex-direction: column;
  }
  .site-btn {
    padding: 11px 16px;
  }
}

.input-wrapper {
  position: relative;
}

.code-input {
  width: 100%;
  resize: vertical;
  min-height: 140px;
  padding: 16px 18px 40px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  line-height: 1.65;
  color: var(--ink);
  background: rgba(2, 11, 20, 0.5);
  border: 1px solid var(--glass-line);
  border-radius: 16px;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.4s;
}

.code-input::placeholder {
  color: var(--ink-mute);
}

.code-input:focus {
  border-color: var(--bio-teal);
  box-shadow: 0 0 0 3px rgba(25, 227, 196, 0.14), var(--glow-teal);
}

.code-input:disabled {
  opacity: 0.6;
}

.model-badge {
  position: absolute;
  right: 14px;
  bottom: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.68rem;
  color: var(--bio-cyan);
  background: rgba(60, 200, 255, 0.1);
  border: 1px solid rgba(60, 200, 255, 0.25);
  pointer-events: none;
}

.btn-section {
  padding-top: 6px;
}

.start-engine-btn {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 26px;
  border: none;
  border-radius: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: 1.5px;
  color: #02221c;
  background: linear-gradient(110deg, var(--bio-teal), var(--bio-cyan));
  box-shadow: 0 10px 34px rgba(25, 227, 196, 0.32);
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.4s var(--ease-out), box-shadow 0.4s, filter 0.3s;
}

.btn-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 30%, rgba(255, 255, 255, 0.5) 50%, transparent 70%);
  transform: translateX(-120%);
}

.start-engine-btn:not(:disabled):hover {
  transform: translateY(-3px);
  box-shadow: 0 16px 46px rgba(60, 200, 255, 0.45);
}

.start-engine-btn:not(:disabled):hover .btn-shimmer {
  animation: sheen-once 0.9s ease-out;
}

.start-engine-btn:not(:disabled):active {
  transform: translateY(0) scale(0.99);
}

.btn-label,
.btn-arrow {
  position: relative;
}

.btn-arrow {
  font-size: 1.3rem;
  transition: transform 0.4s var(--ease-out);
}

.start-engine-btn:not(:disabled):hover .btn-arrow {
  transform: translateX(6px);
}

.start-engine-btn:disabled {
  cursor: not-allowed;
  color: var(--ink-mute);
  background: rgba(127, 176, 196, 0.14);
  box-shadow: none;
}

/* ---------- History (painel claro flutuando) ---------- */
.history-wrap {
  margin-top: 36px;
  border-radius: 24px;
  overflow: hidden;
  background: #fff;
  color: #000;
  border: 1px solid var(--glass-line-strong);
  box-shadow: 0 30px 80px rgba(0, 8, 18, 0.6);
}

/* ---------- Health ---------- */
.health-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 280px;
  padding: 5px 12px;
  border: 1px solid var(--glass-line);
  border-radius: 999px;
  background: rgba(2, 11, 20, 0.45);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: var(--ink-soft);
  transition: border-color 0.4s, box-shadow 0.4s, color 0.4s;
}

.health-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.health-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-mute);
}

.health-chip.is-ok .health-dot {
  background: var(--bio-teal);
  box-shadow: 0 0 10px var(--bio-teal);
}

.health-chip.is-checking .health-dot {
  animation: orb-pulse 1.2s ease-in-out infinite;
}

.health-chip.is-bad {
  color: #ffb4c0;
  border-color: rgba(255, 107, 129, 0.5);
  box-shadow: 0 0 18px rgba(255, 107, 129, 0.18);
}

.health-chip.is-bad .health-dot {
  background: #ff6b81;
  box-shadow: 0 0 10px #ff6b81;
  animation: orb-pulse 1.2s ease-in-out infinite;
}

.health-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255, 107, 129, 0.45);
  background: rgba(255, 107, 129, 0.1);
  color: #ffc2cb;
  font-size: 0.85rem;
  line-height: 1.5;
}

.banner-icon {
  flex: none;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-weight: 800;
  color: #2a0a10;
  background: #ff6b81;
}

@media (max-width: 960px) {
  .health-text {
    display: none;
  }
}

/* ---------- Reveal ---------- */
.reveal-up {
  opacity: 0;
  transform: translateY(24px);
  animation: rise 0.9s var(--ease-out) forwards;
  animation-delay: var(--d, 0s);
}

.reveal {
  opacity: 0;
  transform: translateY(30px);
  filter: blur(4px);
  transition:
    opacity 0.9s var(--ease-out),
    transform 0.9s var(--ease-out),
    filter 0.9s var(--ease-out),
    background 0.4s,
    border-color 0.4s,
    box-shadow 0.4s;
  transition-delay: var(--d, 0s);
}

.reveal.in {
  opacity: 1;
  transform: none;
  filter: none;
}

/* console precisa combinar reveal + tilt */
.console-box.reveal {
  transform: translateY(30px) rotateX(var(--rx)) rotateY(var(--ry));
}

.console-box.reveal.in {
  transform: rotateX(var(--rx)) rotateY(var(--ry));
  transition-delay: 0s;
}

/* ---------- Keyframes ---------- */
@keyframes nav-drop {
  from { opacity: 0; transform: translateY(-24px); }
  to   { opacity: 1; transform: none; }
}

@keyframes rise {
  to { opacity: 1; transform: none; }
}

@keyframes char-in {
  to { opacity: 1; transform: none; }
}

@keyframes char-bob {
  0%, 100% { translate: 0 0; }
  50%      { translate: 0 -0.06em; }
}

@keyframes sheen {
  0%, 60% { transform: translateX(-120%); }
  100%    { transform: translateX(120%); }
}

@keyframes sheen-once {
  from { transform: translateX(-120%); }
  to   { transform: translateX(120%); }
}

@keyframes blink {
  to { visibility: hidden; }
}

@keyframes orb-pulse {
  50% { transform: scale(0.72); opacity: 0.75; }
}

@keyframes ripple {
  from { transform: scale(0.8); opacity: 0.9; }
  to   { transform: scale(1.8); opacity: 0; }
}

@keyframes bob {
  50% { transform: translateY(4px); }
}

@keyframes float {
  50% { transform: translateY(-14px); }
}

@keyframes breathe {
  50% { transform: scale(1.12); opacity: 0.75; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---------- Responsivo ---------- */
@media (max-width: 960px) {
  .hero-section {
    grid-template-columns: 1fr;
    min-height: auto;
    padding-top: 28px;
  }

  .hero-right {
    order: -1;
  }

  .orb-stage {
    width: min(300px, 70vw);
  }

  .dashboard-section {
    grid-template-columns: 1fr;
  }

  .metrics-row {
    flex-direction: column;
  }

  .github-link {
    display: none;
  }
}

/* ---------- Movimento reduzido ---------- */
@media (prefers-reduced-motion: reduce) {
  .home-shell *,
  .home-shell *::before,
  .home-shell *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    animation-delay: 0s !important;
    transition-duration: 0.001ms !important;
  }

  .reveal,
  .reveal-up,
  .wave-char {
    opacity: 1;
    transform: none;
    filter: none;
  }
}
</style>
