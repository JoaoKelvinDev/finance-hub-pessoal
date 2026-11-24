import { CalendarRange } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Select } from '@/components/ui/field'
import { PRESET_LABELS, presetRange, type PeriodPreset } from '@/lib/date'

type Fixed = Exclude<PeriodPreset, 'custom' | 'all'>

/** Período persistido na URL (?period=&from=&to=), compartilhável e com voltar do navegador. */
export function usePeriod(defaultPreset: Fixed = 'this-month') {
  const [params, setParams] = useSearchParams()
  const preset = (params.get('period') as PeriodPreset | null) ?? defaultPreset
  let [from, to] = presetRange(defaultPreset)
  if (preset === 'all') {
    from = ''
    to = ''
  } else if (preset === 'custom' && params.get('from') && params.get('to')) {
    from = params.get('from')!
    to = params.get('to')!
  } else if (preset in PRESET_LABELS) {
    ;[from, to] = presetRange(preset as Fixed)
  }

  const setPeriod = (p: PeriodPreset, range?: [string, string]) => {
    const next = new URLSearchParams(params)
    next.set('period', p)
    if (p === 'custom') {
      const [f, t] = range ?? (from && to ? [from, to] : presetRange(defaultPreset))
      next.set('from', f)
      next.set('to', t)
    } else {
      next.delete('from')
      next.delete('to')
    }
    next.delete('page')
    setParams(next, { replace: true })
  }
  return { preset, from, to, setPeriod }
}

export function PeriodPicker({ period, allowAll }: { period: ReturnType<typeof usePeriod>; allowAll?: boolean }) {
  const { preset, from, to, setPeriod } = period
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="w-48">
        <Select aria-label="Período" value={preset} onChange={(e) => setPeriod(e.target.value as PeriodPreset)}>
          {Object.entries(PRESET_LABELS).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
          <option value="custom">Personalizado</option>
          {allowAll && <option value="all">Todo o período</option>}
        </Select>
      </div>
      {preset === 'custom' && (
        <div className="flex items-center gap-2 text-sm">
          <CalendarRange className="size-4 text-muted" aria-hidden />
          <input
            type="date"
            aria-label="Data inicial"
            value={from}
            max={to}
            onChange={(e) => e.target.value && setPeriod('custom', [e.target.value, to])}
            className="h-10 rounded-lg border border-border bg-surface px-2 shadow-card"
          />
          <span className="text-muted">até</span>
          <input
            type="date"
            aria-label="Data final"
            value={to}
            min={from}
            onChange={(e) => e.target.value && setPeriod('custom', [from, e.target.value])}
            className="h-10 rounded-lg border border-border bg-surface px-2 shadow-card"
          />
        </div>
      )}
    </div>
  )
}
