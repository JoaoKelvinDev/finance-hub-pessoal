import { AnimatePresence, motion } from 'motion/react'
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Clock,
  CreditCard,
  Receipt,
  Repeat,
  SkipForward,
  Undo2,
  type LucideIcon,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, Skeleton } from '@/components/ui/card'
import { Segmented } from '@/components/ui/misc'
import { PayInstallmentDialog } from '@/features/bills/PayInstallmentDialog'
import { addDays, addMonths, formatDate, lastDay, monthRange, todayISO, toISO } from '@/lib/date'
import { formatBRL, formatCompactBRL } from '@/lib/money'
import { listItem, staggerContainer } from '@/lib/motion'
import { useCalendar } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { BillInstallment, CalendarEvent, CalendarResponse, CalendarSource, CalendarStatus } from '@/types/api'

type View = 'month' | 'week' | 'agenda'

const WEEKDAYS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
const MONTHS = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]

const SOURCES: Record<CalendarSource, { label: string; icon: LucideIcon }> = {
  CARD_STATEMENT: { label: 'Fatura de cartão', icon: CreditCard },
  BILL_INSTALLMENT: { label: 'Conta da casa', icon: Receipt },
  RECURRENCE_FORECAST: { label: 'Previsão de recorrência', icon: Repeat },
  PLANNED_TRANSACTION: { label: 'Lançamento previsto', icon: ArrowLeftRight },
}

const STATUS: Record<CalendarStatus, { label: string; icon: LucideIcon; cls: string }> = {
  OVERDUE: { label: 'Vencido', icon: AlertTriangle, cls: 'bg-negative-soft text-negative' },
  PARTIAL: { label: 'Parcial', icon: CircleDashed, cls: 'bg-warning-soft text-warning' },
  PENDING: { label: 'A vencer', icon: Clock, cls: 'bg-surface-2 text-fg' },
  FORECAST: { label: 'Previsto', icon: Clock, cls: 'bg-accent-soft text-accent' },
  PAID: { label: 'Pago', icon: CheckCircle2, cls: 'bg-positive-soft text-positive' },
  SKIPPED: { label: 'Pulado', icon: SkipForward, cls: 'bg-surface-2 text-muted' },
  REVERSED: { label: 'Estornado', icon: Undo2, cls: 'bg-surface-2 text-muted' },
}

const DONE: CalendarStatus[] = ['PAID', 'SKIPPED', 'REVERSED']

// ---------- utilitários de data (ISO civil, sem fuso) ----------

function parts(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return { y, m, d }
}

function weekday(iso: string) {
  const { y, m, d } = parts(iso)
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay()
}

function startOfWeek(iso: string) {
  return addDays(iso, -weekday(iso))
}

function daysIn(from: string, to: string) {
  const out: string[] = []
  for (let d = from; d <= to; d = addDays(d, 1)) out.push(d)
  return out
}

function rangeFor(view: View, anchor: string): [string, string] {
  if (view === 'week') {
    const s = startOfWeek(anchor)
    return [s, addDays(s, 6)]
  }
  const [first, last] = monthRange(anchor)
  if (view === 'agenda') return [first, last]
  // Grade mensal completa: domingo anterior ao dia 1 até o sábado após o último dia.
  return [startOfWeek(first), addDays(last, 6 - weekday(last))]
}

function periodLabel(view: View, anchor: string) {
  const { y, m } = parts(anchor)
  if (view !== 'week') return `${MONTHS[m - 1]} de ${y}`
  const s = startOfWeek(anchor)
  const e = addDays(s, 6)
  const ps = parts(s)
  const pe = parts(e)
  return ps.m === pe.m
    ? `${ps.d}–${pe.d} de ${MONTHS[pe.m - 1]} de ${pe.y}`
    : `${ps.d} ${MONTHS[ps.m - 1].slice(0, 3)} – ${pe.d} ${MONTHS[pe.m - 1].slice(0, 3)} ${pe.y}`
}

function dayHeading(iso: string, today: string) {
  const { d, m } = parts(iso)
  const base = `${WEEKDAYS[weekday(iso)]}, ${d} de ${MONTHS[m - 1]}`
  if (iso === today) return `Hoje · ${base}`
  if (iso === addDays(today, 1)) return `Amanhã · ${base}`
  return base
}

// ---------- página ----------

export function CalendarPage() {
  const today = todayISO()
  const navigate = useNavigate()
  const [view, setView] = useState<View>('month')
  const [anchor, setAnchor] = useState(today)
  const [selected, setSelected] = useState(today)
  const [hidden, setHidden] = useState<Set<CalendarSource>>(new Set())
  const [paying, setPaying] = useState<CalendarEvent | null>(null)

  const [from, to] = rangeFor(view, anchor)
  const q = useCalendar(from, to)

  const events = useMemo(
    () => (q.data?.events ?? []).filter((e) => !hidden.has(e.source)),
    [q.data, hidden],
  )
  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    for (const e of events) {
      const list = map.get(e.date) ?? []
      list.push(e)
      map.set(e.date, list)
    }
    return map
  }, [events])

  const shift = (dir: -1 | 1) => {
    const next = view === 'week' ? addDays(anchor, 7 * dir) : addMonths(anchor, dir)
    setAnchor(next)
    if (view === 'week') setSelected(startOfWeek(next))
    else setSelected(next.slice(0, 7) === today.slice(0, 7) ? today : next)
  }

  const goToday = () => {
    setAnchor(today)
    setSelected(today)
  }

  const toggleSource = (s: CalendarSource) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })

  const openEvent = (e: CalendarEvent) => {
    switch (e.source) {
      case 'BILL_INSTALLMENT':
        if (e.status === 'PENDING' || e.status === 'OVERDUE') setPaying(e)
        else navigate('/contas-da-casa')
        break
      case 'CARD_STATEMENT':
        navigate(`/cartoes/${e.ref_id}`)
        break
      case 'RECURRENCE_FORECAST':
        navigate('/contas-da-casa')
        break
      case 'PLANNED_TRANSACTION':
        navigate('/lancamentos')
        break
    }
  }

  const summary = q.data?.summary

  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Calendário financeiro</h1>
          <p className="mt-0.5 text-muted">Vencimentos de faturas, contas da casa, recorrências e lançamentos previstos.</p>
        </div>
        <Segmented
          label="Visualização do calendário"
          layoutId="calendar-view"
          value={view}
          onChange={(v) => {
            setView(v)
            setAnchor(selected)
          }}
          options={[
            { value: 'month', label: 'Mês' },
            { value: 'week', label: 'Semana' },
            { value: 'agenda', label: 'Agenda' },
          ]}
        />
      </div>

      <SummaryRow loading={q.isPending} summary={summary} />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => shift(-1)} aria-label="Período anterior">
              <ChevronLeft />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => shift(1)} aria-label="Próximo período">
              <ChevronRight />
            </Button>
          </div>
          <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight first-letter:uppercase" aria-live="polite">
            {periodLabel(view, anchor)}
          </h2>
          <Button variant="secondary" size="sm" onClick={goToday}>
            Hoje
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2.5" role="group" aria-label="Filtrar por origem">
          {(Object.keys(SOURCES) as CalendarSource[]).map((s) => {
            const Icon = SOURCES[s].icon
            const active = !hidden.has(s)
            return (
              <button
                key={s}
                type="button"
                aria-pressed={active}
                onClick={() => toggleSource(s)}
                className={cn(
                  'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors',
                  active ? 'border-border bg-surface-2 text-fg' : 'border-dashed border-border text-muted line-through',
                )}
              >
                <Icon className="size-3.5" aria-hidden />
                {SOURCES[s].label}
              </button>
            )
          })}
        </div>

        {q.isError ? (
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        ) : q.isPending ? (
          <div className="p-4">
            <Skeleton className="h-[420px] w-full rounded-lg" />
          </div>
        ) : view === 'month' ? (
          <div className="grid gap-0 lg:grid-cols-[1fr_340px]">
            <MonthGrid
              from={from}
              to={to}
              anchor={anchor}
              today={today}
              selected={selected}
              byDay={byDay}
              onSelect={setSelected}
            />
            <div className="border-t border-border lg:border-t-0 lg:border-l">
              <DayPanel
                date={selected}
                today={today}
                events={byDay.get(selected) ?? []}
                onOpen={openEvent}
              />
            </div>
          </div>
        ) : view === 'week' ? (
          <WeekView from={from} today={today} byDay={byDay} onOpen={openEvent} />
        ) : (
          <AgendaView events={events} today={today} onOpen={openEvent} />
        )}
      </Card>

      <PayInstallmentDialog
        key={paying?.key}
        open={!!paying}
        onOpenChange={(open) => {
          if (!open) setPaying(null)
        }}
        installment={
          paying
            ? ({
                id: paying.source_id,
                bill_id: paying.ref_id,
                bill_name: paying.title,
                due_date: paying.date,
                amount_cents: paying.amount_cents,
              } as BillInstallment)
            : null
        }
      />
    </div>
  )
}

// ---------- resumo ----------

function SummaryRow({ loading, summary }: { loading: boolean; summary?: CalendarResponse['summary'] }) {
  const tiles = [
    { label: 'A pagar no período', value: summary?.to_pay_cents, icon: ArrowUpRight, cls: 'bg-surface-2 text-fg' },
    { label: 'A receber no período', value: summary?.to_receive_cents, icon: ArrowDownLeft, cls: 'bg-positive-soft text-positive' },
    { label: 'Já pago', value: summary?.paid_cents, icon: CheckCircle2, cls: 'bg-accent-soft text-accent' },
    {
      label: summary?.overdue_count ? `Vencido · ${summary.overdue_count} ${summary.overdue_count === 1 ? 'item' : 'itens'}` : 'Vencido',
      value: summary?.overdue_cents,
      icon: AlertTriangle,
      cls: summary?.overdue_cents ? 'bg-negative-soft text-negative' : 'bg-surface-2 text-muted',
    },
  ]
  return (
    <motion.div variants={staggerContainer} initial="initial" animate="enter" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((t) => (
        <motion.div key={t.label} variants={listItem} className="rounded-xl border border-border bg-surface p-4 shadow-card">
          <span className="flex items-center gap-2 text-[13px] font-medium text-muted">
            <span className={cn('grid size-7 place-items-center rounded-lg [&_svg]:size-4', t.cls)} aria-hidden>
              <t.icon />
            </span>
            <span className="truncate">{t.label}</span>
          </span>
          {loading || t.value === undefined ? (
            <Skeleton className="mt-3 h-7 w-28" />
          ) : (
            <CurrencyDisplay cents={t.value} className="mt-3 block text-[20px] font-semibold tracking-tight sm:text-[22px]" />
          )}
        </motion.div>
      ))}
    </motion.div>
  )
}

// ---------- mês ----------

function MonthGrid({
  from,
  to,
  anchor,
  today,
  selected,
  byDay,
  onSelect,
}: {
  from: string
  to: string
  anchor: string
  today: string
  selected: string
  byDay: Map<string, CalendarEvent[]>
  onSelect: (d: string) => void
}) {
  const month = anchor.slice(0, 7)
  const days = daysIn(from, to)
  const { y, m } = parts(anchor)
  const monthLast = toISO(y, m, lastDay(y, m))

  return (
    <div className="p-2 sm:p-3">
      <div className="grid grid-cols-7 pb-1.5" aria-hidden>
        {WEEKDAYS.map((w) => (
          <div key={w} className="px-1.5 text-center text-[11px] font-medium tracking-wide text-muted uppercase sm:text-left">
            {w}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border" role="grid" aria-label={`Dias até ${formatDate(monthLast)}`}>
        {days.map((d) => {
          const list = byDay.get(d) ?? []
          const inMonth = d.slice(0, 7) === month
          const isToday = d === today
          const isSelected = d === selected
          const open = list.filter((e) => !DONE.includes(e.status))
          const outCents = open.filter((e) => e.direction === 'OUT').reduce((s, e) => s + e.open_cents, 0)
          const hasOverdue = list.some((e) => e.status === 'OVERDUE')
          return (
            <button
              key={d}
              type="button"
              role="gridcell"
              aria-selected={isSelected}
              aria-label={`${formatDate(d)}: ${list.length} ${list.length === 1 ? 'evento' : 'eventos'}${outCents ? `, ${formatBRL(outCents)} a pagar` : ''}`}
              onClick={() => onSelect(d)}
              className={cn(
                'relative flex min-h-16 flex-col gap-1 bg-surface p-1.5 text-left transition-colors sm:min-h-24',
                !inMonth && 'bg-surface-2/50 text-muted',
                isSelected ? 'ring-2 ring-accent ring-inset' : 'hover:bg-surface-2',
              )}
            >
              <span className="flex items-center justify-between gap-1">
                <span
                  className={cn(
                    'grid size-6 place-items-center rounded-full text-xs tabular-nums',
                    isToday && 'bg-accent font-semibold text-accent-fg',
                  )}
                >
                  {parts(d).d}
                </span>
                {hasOverdue && <AlertTriangle className="size-3.5 text-negative" aria-hidden />}
              </span>

              {/* Desktop: até 2 eventos + contador */}
              <span className="hidden min-w-0 flex-col gap-0.5 sm:flex">
                {list.slice(0, 2).map((e) => (
                  <span
                    key={e.key}
                    className={cn(
                      'flex min-w-0 items-center gap-1 rounded px-1 py-0.5 text-[11px] leading-tight',
                      DONE.includes(e.status) ? 'text-muted line-through' : 'bg-surface-2',
                    )}
                  >
                    <span className="size-1.5 shrink-0 rounded-full" style={{ background: e.color }} />
                    <span className="truncate">{e.title}</span>
                  </span>
                ))}
                {list.length > 2 && <span className="px-1 text-[11px] text-muted">+{list.length - 2} mais</span>}
              </span>

              {/* Mobile: pontos */}
              {list.length > 0 && (
                <span className="flex flex-wrap gap-0.5 sm:hidden" aria-hidden>
                  {list.slice(0, 4).map((e) => (
                    <span
                      key={e.key}
                      className={cn('size-1.5 rounded-full', DONE.includes(e.status) && 'opacity-40')}
                      style={{ background: e.color }}
                    />
                  ))}
                </span>
              )}

              {outCents > 0 && (
                <span className="mt-auto truncate text-[10px] font-medium text-muted tabular-nums sm:text-[11px]">
                  {formatCompactBRL(outCents)}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function DayPanel({
  date,
  today,
  events,
  onOpen,
}: {
  date: string
  today: string
  events: CalendarEvent[]
  onOpen: (e: CalendarEvent) => void
}) {
  return (
    <div>
      <CardHeader title={<span className="first-letter:uppercase">{dayHeading(date, today)}</span>} description={`${events.length} ${events.length === 1 ? 'evento' : 'eventos'}`} />
      <CardContent>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={date}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0, transition: { duration: 0.18 } }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
          >
            {events.length === 0 ? (
              <EmptyState
                className="py-8"
                icon={<CalendarDays />}
                title="Nada neste dia"
                description="Sem vencimentos, previsões ou lançamentos previstos."
              />
            ) : (
              <ul className="space-y-2">
                {events.map((e) => (
                  <li key={e.key}>
                    <EventRow event={e} onOpen={onOpen} />
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        </AnimatePresence>
      </CardContent>
    </div>
  )
}

// ---------- semana ----------

function WeekView({
  from,
  today,
  byDay,
  onOpen,
}: {
  from: string
  today: string
  byDay: Map<string, CalendarEvent[]>
  onOpen: (e: CalendarEvent) => void
}) {
  const days = daysIn(from, addDays(from, 6))
  return (
    <div className="grid gap-px bg-border md:grid-cols-7">
      {days.map((d) => {
        const list = byDay.get(d) ?? []
        return (
          <section key={d} className="flex min-h-40 flex-col bg-surface p-2.5" aria-label={formatDate(d)}>
            <header className="mb-2 flex items-baseline justify-between gap-2">
              <span className="text-[11px] font-medium tracking-wide text-muted uppercase">{WEEKDAYS[weekday(d)]}</span>
              <span
                className={cn(
                  'grid size-7 place-items-center rounded-full text-sm tabular-nums',
                  d === today && 'bg-accent font-semibold text-accent-fg',
                )}
              >
                {parts(d).d}
              </span>
            </header>
            {list.length === 0 ? (
              <p className="text-xs text-muted/70">—</p>
            ) : (
              <ul className="space-y-1.5">
                {list.map((e) => (
                  <li key={e.key}>
                    <EventRow event={e} onOpen={onOpen} compact />
                  </li>
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}

// ---------- agenda ----------

function AgendaView({
  events,
  today,
  onOpen,
}: {
  events: CalendarEvent[]
  today: string
  onOpen: (e: CalendarEvent) => void
}) {
  const overdue = events.filter((e) => e.status === 'OVERDUE')
  const rest = events.filter((e) => e.status !== 'OVERDUE')
  const groups = new Map<string, CalendarEvent[]>()
  for (const e of rest) groups.set(e.date, [...(groups.get(e.date) ?? []), e])

  if (events.length === 0) {
    return (
      <EmptyState
        icon={<CalendarDays />}
        title="Nenhum compromisso neste mês"
        description="Cadastre contas da casa, recorrências ou lançamentos previstos para vê-los aqui."
      />
    )
  }

  return (
    <div className="divide-y divide-border">
      {overdue.length > 0 && (
        <AgendaGroup
          title="Vencidos"
          tone="danger"
          events={overdue}
          onOpen={onOpen}
          showDate
        />
      )}
      {[...groups.entries()].map(([d, list]) => (
        <AgendaGroup key={d} title={dayHeading(d, today)} events={list} onOpen={onOpen} highlight={d === today} />
      ))}
    </div>
  )
}

function AgendaGroup({
  title,
  events,
  onOpen,
  tone,
  showDate,
  highlight,
}: {
  title: string
  events: CalendarEvent[]
  onOpen: (e: CalendarEvent) => void
  tone?: 'danger'
  showDate?: boolean
  highlight?: boolean
}) {
  const total = events.filter((e) => !DONE.includes(e.status) && e.direction === 'OUT').reduce((s, e) => s + e.open_cents, 0)
  return (
    <section className="px-4 py-3">
      <header className="mb-2 flex items-center justify-between gap-3">
        <h3
          className={cn(
            'text-[13px] font-semibold first-letter:uppercase',
            tone === 'danger' && 'flex items-center gap-1.5 text-negative',
            highlight && 'text-accent',
          )}
        >
          {tone === 'danger' && <AlertTriangle className="size-4" aria-hidden />}
          {title}
        </h3>
        {total > 0 && <span className="text-xs text-muted tabular-nums">{formatBRL(total)} a pagar</span>}
      </header>
      <motion.ul variants={staggerContainer} initial="initial" animate="enter" className="space-y-2">
        {events.map((e) => (
          <motion.li key={e.key} variants={listItem}>
            <EventRow event={e} onOpen={onOpen} showDate={showDate} />
          </motion.li>
        ))}
      </motion.ul>
    </section>
  )
}

// ---------- item ----------

function EventRow({
  event: e,
  onOpen,
  compact,
  showDate,
}: {
  event: CalendarEvent
  onOpen: (e: CalendarEvent) => void
  compact?: boolean
  showDate?: boolean
}) {
  const source = SOURCES[e.source]
  const status = STATUS[e.status]
  const SourceIcon = source.icon
  const StatusIcon = status.icon
  const done = DONE.includes(e.status)
  const shown = done ? e.amount_cents : e.open_cents
  const actionLabel =
    e.source === 'BILL_INSTALLMENT' && (e.status === 'PENDING' || e.status === 'OVERDUE')
      ? 'Registrar pagamento'
      : 'Abrir'

  return (
    <button
      type="button"
      onClick={() => onOpen(e)}
      aria-label={`${e.title}, ${source.label}, ${status.label}, ${formatBRL(shown)}. ${actionLabel}`}
      className={cn(
        'group relative flex w-full items-start gap-3 overflow-hidden rounded-lg border border-border bg-surface text-left transition-[border-color,box-shadow] hover:border-accent/40 hover:shadow-card',
        compact ? 'p-2' : 'p-3',
      )}
    >
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: e.color }} aria-hidden />
      {!compact && (
        <span className="ml-1 grid size-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted [&_svg]:size-4" aria-hidden>
          <SourceIcon />
        </span>
      )}
      <span className={cn('min-w-0 flex-1', compact && 'ml-1')}>
        <span className={cn('block truncate font-medium', compact ? 'text-xs' : 'text-sm', done && 'text-muted line-through')}>
          {e.title}
        </span>
        <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
          <span className={cn('inline-flex items-center gap-1 rounded-full px-1.5 py-px font-medium', status.cls)}>
            <StatusIcon className="size-3" aria-hidden />
            {status.label}
          </span>
          {!compact && <span className="truncate">{showDate ? formatDate(e.date) : source.label}</span>}
        </span>
      </span>
      <span className="shrink-0 text-right">
        <span
          className={cn(
            'block font-semibold tabular-nums',
            compact ? 'text-xs' : 'text-sm',
            e.direction === 'IN' && 'text-positive',
            done && 'text-muted',
          )}
        >
          {e.direction === 'IN' ? '+' : ''}
          {compact ? formatCompactBRL(shown) : formatBRL(shown)}
        </span>
        {!compact && e.status === 'PARTIAL' && (
          <span className="block text-[11px] text-muted tabular-nums">de {formatBRL(e.amount_cents)}</span>
        )}
      </span>
    </button>
  )
}
