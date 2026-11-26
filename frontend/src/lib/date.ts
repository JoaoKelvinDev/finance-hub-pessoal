// Datas civis tratadas como strings ISO (YYYY-MM-DD) para não sofrer com fuso.

export const TZ = 'America/Fortaleza'

export function todayISO(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(new Date())
}

function parts(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return { y, m, d }
}

export function toISO(y: number, m: number, d: number) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export function lastDay(y: number, m: number) {
  return new Date(Date.UTC(y, m, 0)).getUTCDate()
}

export function addMonths(iso: string, n: number) {
  const { y, m } = parts(iso)
  const idx = y * 12 + (m - 1) + n
  return toISO(Math.floor(idx / 12), (idx % 12) + 1, 1)
}

export function addDays(iso: string, n: number) {
  const { y, m, d } = parts(iso)
  const dt = new Date(Date.UTC(y, m - 1, d + n))
  return dt.toISOString().slice(0, 10)
}

export function monthRange(iso: string): [string, string] {
  const { y, m } = parts(iso)
  return [toISO(y, m, 1), toISO(y, m, lastDay(y, m))]
}

export function formatDate(iso: string) {
  const { y, m, d } = parts(iso)
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}/${y}`
}

const monthNames = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

export function formatShortDate(iso: string) {
  const { m, d } = parts(iso)
  return `${d} ${monthNames[m - 1]}`
}

export function formatMonth(yyyymm: string) {
  const [y, m] = yyyymm.split('-').map(Number)
  return `${monthNames[m - 1]}/${String(y).slice(2)}`
}

export function daysBetween(a: string, b: string) {
  const pa = parts(a)
  const pb = parts(b)
  return Math.round((Date.UTC(pb.y, pb.m - 1, pb.d) - Date.UTC(pa.y, pa.m - 1, pa.d)) / 86_400_000)
}

/**
 * dd/mm/aaaa. Data civil (AAAA-MM-DD) é formatada sem conversão de fuso; data-hora (com "T")
 * é convertida para o fuso do app. Nunca use `new Date('AAAA-MM-DD')` para exibir: o JS lê como
 * meia-noite UTC e, em Fortaleza (UTC−3), a data aparece um dia antes.
 */
export function formatRelativeDate(value: string): string {
  if (value.length > 10) {
    return new Intl.DateTimeFormat('pt-BR', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' }).format(
      new Date(value),
    )
  }
  return formatDate(value)
}

/** 'AAAA-MM-DD' → 'novembro de 2026', sem conversão de fuso. */
export function formatMonthLong(iso: string): string {
  const { y, m } = parts(iso)
  return new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC', month: 'long', year: 'numeric' }).format(new Date(Date.UTC(y, m - 1, 1)))
}

export function formatDateForInput(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export type PeriodPreset = 'this-month' | 'last-month' | 'last-3' | 'last-6' | 'last-12' | 'custom' | 'all'

export const PRESET_LABELS: Record<Exclude<PeriodPreset, 'custom' | 'all'>, string> = {
  'this-month': 'Este mês',
  'last-month': 'Mês anterior',
  'last-3': 'Últimos 3 meses',
  'last-6': 'Últimos 6 meses',
  'last-12': 'Últimos 12 meses',
}

export function presetRange(preset: Exclude<PeriodPreset, 'custom' | 'all'>, today = todayISO()): [string, string] {
  const [, end] = monthRange(today)
  switch (preset) {
    case 'this-month':
      return monthRange(today)
    case 'last-month':
      return monthRange(addMonths(today, -1))
    case 'last-3':
      return [addMonths(today, -2), end]
    case 'last-6':
      return [addMonths(today, -5), end]
    case 'last-12':
      return [addMonths(today, -11), end]
  }
}
