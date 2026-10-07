/** Formatação pura do gasto de tokens (testável com `node --test`). */

export function formatTokens(value, locale = 'pt-BR') {
  const n = Math.max(0, Number(value) || 0)
  if (n < 1000) return String(Math.round(n))
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(n)
}

export function formatExact(value, locale = 'pt-BR') {
  return new Intl.NumberFormat(locale).format(Math.max(0, Math.round(Number(value) || 0)))
}

/** Custo só existe quando o preço foi configurado no backend (`cost` null = não mostrar). */
export function formatCost(cost, currency, locale = 'pt-BR') {
  if (cost === null || cost === undefined || !currency) return ''
  const digits = cost > 0 && cost < 0.01 ? 4 : 2
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(cost)
  } catch {
    return `${cost.toFixed(digits)} ${currency}`
  }
}

/** Etapas na ordem do processo, só as que já gastaram algo. */
export const STAGE_ORDER = ['seed', 'ontology', 'prepare', 'simulation', 'report', 'chat', 'interviews', 'other']

export function stageRows(stages = {}) {
  return STAGE_ORDER.filter((key) => stages[key] && stages[key].total_tokens > 0).map((key) => ({
    key,
    ...stages[key],
  }))
}
