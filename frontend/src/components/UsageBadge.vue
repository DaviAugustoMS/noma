<template>
  <div class="usage" :class="{ pulse }" @mouseleave="open = false">
    <button
      type="button"
      class="usage-chip"
      :aria-expanded="open"
      :title="$t('usage.hint')"
      @click="open = !open"
      @focus="open = true"
    >
      <span class="dot" aria-hidden="true"></span>
      <span class="usage-total">{{ formatTokens(data.total_tokens, numLocale) }}</span>
      <span class="usage-unit">{{ $t('usage.tokens') }}</span>
      <span v-if="costText" class="usage-cost">{{ costText }}</span>
    </button>

    <div v-if="open" class="usage-pop" role="status">
      <div class="usage-pop-title">{{ scopeTitle }}</div>
      <div class="row"><span>{{ $t('usage.input') }}</span><b>{{ formatExact(data.prompt_tokens, numLocale) }}</b></div>
      <div class="row"><span>{{ $t('usage.output') }}</span><b>{{ formatExact(data.completion_tokens, numLocale) }}</b></div>
      <div class="row"><span>{{ $t('usage.calls') }}</span><b>{{ formatExact(data.calls, numLocale) }}</b></div>
      <div v-if="rows.length" class="usage-stages">
        <div v-for="r in rows" :key="r.key" class="row">
          <span>{{ $t(`usage.stage.${r.key}`) }}</span>
          <b>{{ formatExact(r.total_tokens, numLocale) }}</b>
        </div>
      </div>
      <p v-if="data.estimated_calls" class="usage-note">{{ $t('usage.estimated', { n: data.estimated_calls }) }}</p>
      <p v-if="error" class="usage-note usage-error">{{ $t('usage.error') }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getUsage } from '../api/usage'
import { formatCost, formatExact, formatTokens, stageRows } from '../lib/usageFormat'

// Sem ids = total geral. O gasto é atualizado a cada poucos segundos enquanto a aba está visível.
const props = defineProps({
  projectId: { type: String, default: '' },
  simulationId: { type: String, default: '' },
  reportId: { type: String, default: '' },
  intervalMs: { type: Number, default: 3000 },
})

const { t, locale } = useI18n()
const numLocale = computed(() => ({ pt: 'pt-BR', en: 'en-US', zh: 'zh-CN' })[locale.value] || 'pt-BR')

const empty = () => ({
  prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, calls: 0, estimated_calls: 0,
  cost: null, currency: null, stages: {},
})
const data = reactive(empty())
const open = ref(false)
const error = ref(false)
const pulse = ref(false)
let timer = null
let inFlight = false
let alive = true

const rows = computed(() => stageRows(data.stages))
const costText = computed(() => formatCost(data.cost, data.currency, numLocale.value))
const scopeTitle = computed(() =>
  props.projectId || props.simulationId || props.reportId ? t('usage.thisProject') : t('usage.allProjects'),
)

async function refresh() {
  if (inFlight || document.hidden) return
  inFlight = true
  try {
    const res = await getUsage(props)
    if (!alive) return
    const next = { ...empty(), ...res.data }
    if (next.total_tokens > data.total_tokens) {
      pulse.value = true
      setTimeout(() => { pulse.value = false }, 900)
    }
    Object.assign(data, next)
    error.value = false
  } catch {
    // Não logamos o erro do axios (carrega a requisição inteira); só sinalizamos.
    if (alive) error.value = true
  } finally {
    inFlight = false
  }
}

function start() {
  stop()
  Object.assign(data, empty())
  refresh()
  timer = setInterval(refresh, props.intervalMs)
}
function stop() {
  if (timer) clearInterval(timer)
  timer = null
}

onMounted(start)
onBeforeUnmount(() => { alive = false; stop() })
watch(() => [props.projectId, props.simulationId, props.reportId], start)
</script>

<style scoped>
.usage {
  position: relative;
  display: inline-flex;
  font-family: 'JetBrains Mono', monospace;
}
.usage-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid currentColor;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  opacity: 0.85;
}
.usage-chip:hover,
.usage-chip:focus-visible { opacity: 1; }
.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #19e3c4;
  transition: transform 0.3s, box-shadow 0.3s;
}
.pulse .dot { transform: scale(1.7); box-shadow: 0 0 10px #19e3c4; }
.usage-total { font-weight: 700; }
.usage-unit { opacity: 0.7; }
.usage-cost { padding-left: 6px; border-left: 1px solid currentColor; }
.usage-pop {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  min-width: 230px;
  padding: 12px 14px;
  border: 1px solid #2c3e50;
  border-radius: 12px;
  background: #0b1a26;
  color: #e6f1f7;
  font-size: 0.75rem;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
}
.usage-pop-title { margin-bottom: 8px; font-weight: 700; color: #19e3c4; }
.row { display: flex; justify-content: space-between; gap: 16px; padding: 2px 0; }
.usage-stages { margin-top: 8px; padding-top: 8px; border-top: 1px solid #243746; }
.usage-note { margin-top: 8px; color: #9fb4c2; line-height: 1.4; }
.usage-error { color: #ff9d9d; }
</style>
