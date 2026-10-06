/**
 * Classifica uma linha do console de log do relatório (`[hora] NÍVEL: mensagem`).
 * O nível (ERROR/WARNING) é o sinal principal; as palavras "erro"/"aviso" (e as
 * chinesas, de logs antigos) cobrem linhas INFO cuja mensagem relata um problema.
 */
export function logLevelClass(log) {
  const line = String(log ?? '')
  if (line.includes('ERROR') || line.includes('错误') || /\berro/i.test(line)) return 'error'
  if (line.includes('WARNING') || line.includes('警告') || /\bavis[oa]/i.test(line)) return 'warning'
  // INFO usa a cor padrão, não é marcado como success
  return ''
}
