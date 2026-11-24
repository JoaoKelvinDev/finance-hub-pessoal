// Apenas formatação e parse de entrada. Cálculos financeiros ficam no backend.

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const compact = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function formatBRL(cents: number, opts: { signed?: boolean } = {}) {
  const text = brl.format(cents / 100)
  if (opts.signed && cents > 0) return `+${text}`
  return text
}

export function formatCompactBRL(cents: number) {
  return compact.format(cents / 100)
}

/** Converte "1.234,56" em 123456 sem ponto flutuante. Retorna null se inválido. */
export function parseBRLToCents(input: string): number | null {
  const clean = input.replace(/R\$\s?/g, '').trim()
  if (!clean) return null
  const negative = clean.startsWith('-')
  const body = clean.replace(/^-/, '')
  if (!/^(\d{1,3}(\.\d{3})*|\d+)(,\d{1,2})?$/.test(body)) return null
  const [intPart, frac = ''] = body.split(',')
  const cents = Number(intPart.replace(/\./g, '')) * 100 + Number(frac.padEnd(2, '0'))
  if (!Number.isSafeInteger(cents)) return null
  return negative ? -cents : cents
}

/** Máscara de digitação: mantém só dígitos e formata como centavos ("12345" -> "123,45"). */
export function maskCents(raw: string): { text: string; cents: number } {
  const digits = raw.replace(/\D/g, '').replace(/^0+(?=\d)/, '').slice(0, 13)
  const cents = digits ? Number(digits) : 0
  const reais = Math.floor(cents / 100)
  const text = `${reais.toLocaleString('pt-BR')},${String(cents % 100).padStart(2, '0')}`
  return { text: digits ? text : '', cents }
}

export function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`
}
