import test from 'node:test'
import assert from 'node:assert/strict'
import { formatTokens, formatCost, stageRows } from '../src/lib/usageFormat.js'

test('formatTokens: abaixo de mil mostra o número; acima, compacto', () => {
  assert.equal(formatTokens(0), '0')
  assert.equal(formatTokens(999), '999')
  assert.match(formatTokens(12500, 'pt-BR'), /12,5/)
  assert.equal(formatTokens(-5), '0')
  assert.equal(formatTokens('abc'), '0')
})

test('formatCost: sem preço configurado não mostra nada', () => {
  assert.equal(formatCost(null, null), '')
  assert.equal(formatCost(undefined, 'BRL'), '')
  assert.match(formatCost(1.5, 'BRL', 'pt-BR'), /1,50/)
  assert.match(formatCost(0.0042, 'USD', 'en-US'), /0\.0042/)
})

test('stageRows: ordem do processo e ignora etapas sem gasto', () => {
  const rows = stageRows({
    report: { total_tokens: 10 },
    seed: { total_tokens: 5 },
    chat: { total_tokens: 0 },
    desconhecida: { total_tokens: 9 },
  })
  assert.deepEqual(rows.map((r) => r.key), ['seed', 'report'])
})
