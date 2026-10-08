<template>
  <section class="insights" aria-labelledby="insights-title">
    <div class="insights-head">
      <h2 id="insights-title" class="insights-title">{{ $t('step5.insightsTitle') }}</h2>
      <button type="button" class="insights-btn" :disabled="loading" @click="generate">
        {{ loading ? $t('step5.insightsGenerating') : $t('step5.insightsGenerate') }}
      </button>
    </div>

    <p v-if="error" class="insights-error" role="alert">{{ error }}</p>
    <p v-else-if="loaded && !data" class="insights-empty">{{ $t('step5.insightsEmpty') }}</p>

    <div v-if="data" class="insights-grid">
      <article v-for="cat in categories" :key="cat.key" class="insights-card" :class="`tone-${cat.key}`">
        <h3>{{ $t(`report.insights.${cat.key}`) }}</h3>
        <ul v-if="data[cat.key] && data[cat.key].length">
          <li v-for="(item, i) in data[cat.key]" :key="i">
            <strong>{{ item.title }}</strong>
            <span v-if="item.detail">{{ item.detail }}</span>
          </li>
        </ul>
        <p v-else class="insights-none">{{ $t('step5.insightsNone') }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { generateReportInsights, getReportInsights } from '../api/report'

const props = defineProps({ reportId: { type: String, required: true } })
const { t } = useI18n()

const categories = [
  { key: 'positives' }, { key: 'negatives' }, { key: 'improvements' }, { key: 'avoid' }, { key: 'new_points' },
]
const data = ref(null)
const loaded = ref(false)
const loading = ref(false)
const error = ref('')

async function load() {
  try {
    const res = await getReportInsights(props.reportId)
    data.value = res.data || null
  } catch {
    data.value = null // sem insights ainda; o botão gera
  } finally {
    loaded.value = true
  }
}

async function generate() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await generateReportInsights(props.reportId)
    data.value = res.data
  } catch (e) {
    // Não logamos o erro do axios (carrega a requisição inteira).
    error.value = e?.response?.data?.error || t('common.error')
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.reportId, load)
</script>

<style scoped>
.insights { margin-top: 40px; padding-top: 24px; border-top: 1px solid #E5E7EB; }
.insights-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.insights-title { font-family: 'Times New Roman', Times, serif; font-size: 22px; font-weight: 700; color: #111827; margin: 0; }
.insights-btn {
  padding: 6px 12px; border: 1px solid #000; background: #fff; color: #000;
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; cursor: pointer;
}
.insights-btn:hover:not(:disabled) { background: #000; color: #fff; }
.insights-btn:disabled { opacity: 0.6; cursor: progress; }
.insights-empty, .insights-none { color: #6B7280; font-size: 13px; font-style: italic; margin: 0; }
.insights-error { color: #B91C1C; font-size: 13px; margin: 0 0 12px; }
.insights-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.insights-card { padding: 14px 16px; border: 1px solid #E5E7EB; border-left-width: 4px; background: #fff; }
.insights-card h3 { margin: 0 0 10px; font-size: 13px; font-weight: 700; color: #111827; text-transform: uppercase; letter-spacing: 0.04em; }
.insights-card ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }
.insights-card li { font-size: 13px; line-height: 1.5; color: #374151; }
.insights-card li strong { display: block; color: #111827; }
.tone-positives { border-left-color: #16A34A; }
.tone-negatives { border-left-color: #DC2626; }
.tone-improvements { border-left-color: #2563EB; }
.tone-avoid { border-left-color: #D97706; }
.tone-new_points { border-left-color: #7C3AED; }
</style>
