import { AnimatePresence, motion } from 'motion/react'
import { ArrowDownRight, ArrowUpRight, ChevronRight, CreditCard, HandCoins, Minus, PieChart } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router-dom'
import { BrandAvatar } from '@/components/finance/brand-avatar'
import { CurrencyDisplay } from '@/components/finance/currency'
import { ExportButton } from '@/components/finance/export-button'
import { PeriodPicker, usePeriod } from '@/components/finance/period-picker'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton } from '@/components/finance/transaction-list'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Segmented } from '@/components/ui/misc'
import { formatDate } from '@/lib/date'
import { formatBRL, formatPct } from '@/lib/money'
import { listItem, staggerContainer } from '@/lib/motion'
import { useCardReport, useCashFlowReport, useCategoryReport, useCounterpartyReport } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { AgingBuckets, CategoryReportRow } from '@/types/api'

const CashFlowChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.CashFlowChart })))

type Tab = 'categories' | 'cash-flow' | 'cards' | 'counterparties'

export function ReportsPage() {
  const period = usePeriod()
  const [tab, setTab] = useState<Tab>('categories')
  const [basis, setBasis] = useState<'CASH' | 'COMPETENCE'>('CASH')
  const exportKind = tab

  return (
    <div className="mx-auto max-w-[1200px] space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Relatório"
          layoutId="reports-tab"
          value={tab}
          onChange={setTab}
          options={[
            { value: 'categories', label: 'Categorias' },
            { value: 'cash-flow', label: 'Fluxo de caixa' },
            { value: 'cards', label: 'Cartões' },
            { value: 'counterparties', label: 'Terceiros' },
          ]}
        />
        <div className="flex flex-wrap items-center gap-2">
          <PeriodPicker period={period} />
          <ExportButton kind={exportKind} from={period.from} to={period.to} basis={basis} />
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.2 } }}
          exit={{ opacity: 0, transition: { duration: 0.12 } }}
        >
          {tab === 'categories' && <CategoriesReport from={period.from} to={period.to} basis={basis} onBasis={setBasis} />}
          {tab === 'cash-flow' && <CashFlowReportView from={period.from} to={period.to} />}
          {tab === 'cards' && <CardsReport from={period.from} to={period.to} />}
          {tab === 'counterparties' && <CounterpartiesReport from={period.from} to={period.to} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function Change({ pct, inverse }: { pct: number | null; inverse?: boolean }) {
  if (pct === null) return <span className="text-xs text-muted">—</span>
  const good = pct === 0 ? null : inverse ? pct < 0 : pct > 0
  const Icon = pct === 0 ? Minus : pct > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-xs font-medium',
        good === true && 'text-positive',
        good === false && 'text-negative',
        good === null && 'text-muted',
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {formatPct(pct)}
    </span>
  )
}

function Stat({ label, cents, tone }: { label: string; cents: number; tone?: string }) {
  return (
    <Card className="p-4">
      <p className="text-[13px] text-muted">{label}</p>
      <CurrencyDisplay cents={cents} className={cn('mt-1.5 block text-[22px] font-normal tracking-tight', tone)} />
    </Card>
  )
}

// ---------- Categorias ----------

function CategoriesReport({
  from,
  to,
  basis,
  onBasis,
}: {
  from: string
  to: string
  basis: 'CASH' | 'COMPETENCE'
  onBasis: (b: 'CASH' | 'COMPETENCE') => void
}) {
  const q = useCategoryReport(from, to, basis)
  const [open, setOpen] = useState<string | null>(null)
  const r = q.data
  const max = Math.max(1, ...(r?.rows.map((x) => x.amount_cents) ?? [1]))

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat label="Gasto no período" cents={r?.total_cents ?? 0} />
        <Stat label="Período anterior" cents={r?.previous_total_cents ?? 0} />
        <Card className="flex flex-col justify-between gap-2 p-4">
          <p className="text-[13px] text-muted">Base de cálculo</p>
          <Segmented
            label="Base de cálculo"
            layoutId="report-basis"
            value={basis}
            onChange={onBasis}
            options={[
              { value: 'CASH', label: 'Caixa' },
              { value: 'COMPETENCE', label: 'Competência' },
            ]}
          />
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader
          title="Gastos por categoria"
          description={
            r
              ? `Comparado a ${formatDate(r.previous_from)} – ${formatDate(r.previous_to)}. ${
                  basis === 'CASH' ? 'Cartão conta quando a fatura é paga.' : 'Cartão conta na data da compra.'
                }`
              : undefined
          }
        />
        {q.isError ? (
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        ) : !r ? (
          <ListSkeleton rows={5} />
        ) : r.rows.length === 0 ? (
          <EmptyState icon={<PieChart />} title="Sem gastos no período" description="Nenhuma despesa nesta base de cálculo." />
        ) : (
          <motion.ul variants={staggerContainer} initial="initial" animate="enter" className="divide-y divide-border border-t border-border">
            {r.rows.map((row) => {
              const key = row.category_id ?? 'none'
              const expanded = open === key
              return (
                <motion.li key={key} variants={listItem}>
                  <button
                    type="button"
                    onClick={() => setOpen(expanded ? null : key)}
                    disabled={!row.children.length}
                    aria-expanded={row.children.length ? expanded : undefined}
                    className="flex w-full items-center gap-3 px-5 py-3 text-left enabled:hover:bg-surface-2/60"
                  >
                    <ChevronRight
                      className={cn('size-4 shrink-0 text-muted transition-transform', expanded && 'rotate-90', !row.children.length && 'invisible')}
                      aria-hidden
                    />
                    <CategoryBar row={row} max={max} />
                  </button>
                  <AnimatePresence initial={false}>
                    {expanded && (
                      <motion.ul
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden bg-surface-2/40"
                      >
                        {row.children.map((c) => (
                          <li key={c.category_id ?? c.name} className="flex items-center gap-3 py-2.5 pr-5 pl-12">
                            <CategoryBar row={c} max={row.amount_cents || 1} small />
                          </li>
                        ))}
                      </motion.ul>
                    )}
                  </AnimatePresence>
                </motion.li>
              )
            })}
          </motion.ul>
        )}
      </Card>
    </div>
  )
}

function CategoryBar({ row, max, small }: { row: CategoryReportRow; max: number; small?: boolean }) {
  return (
    <span className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1">
      <span className="flex min-w-0 items-center gap-2">
        <span className="size-2.5 shrink-0 rounded-sm" style={{ background: row.color }} aria-hidden />
        <span className={cn('truncate', small ? 'text-[13px]' : 'text-sm')}>{row.name}</span>
        <span className="text-xs text-muted tabular-nums">{row.share_pct.toLocaleString('pt-BR')}%</span>
      </span>
      <span className="flex items-center gap-3">
        <Change pct={row.change_pct} inverse />
        <span className={cn('num w-28 text-right font-medium', small ? 'text-[13px]' : 'text-sm')}>{formatBRL(row.amount_cents)}</span>
      </span>
      <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <motion.span
          className="block h-full rounded-full"
          style={{ background: row.color }}
          initial={{ width: 0 }}
          animate={{ width: `${(row.amount_cents / max) * 100}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        />
      </span>
    </span>
  )
}

// ---------- Fluxo de caixa ----------

function CashFlowReportView({ from, to }: { from: string; to: string }) {
  const q = useCashFlowReport(from, to)
  const r = q.data
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat label="Receitas" cents={r?.income_cents ?? 0} tone="text-positive" />
        <Stat label="Despesas" cents={r?.expense_cents ?? 0} tone="text-negative" />
        <Stat label="Resultado" cents={r?.net_cents ?? 0} tone={r && r.net_cents < 0 ? 'text-negative' : undefined} />
      </div>
      <Card>
        {q.isError ? (
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        ) : !r ? (
          <Skeleton className="m-5 h-72" />
        ) : (
          <Suspense fallback={<Skeleton className="m-5 h-72" />}>
            <CashFlowChart data={r} />
          </Suspense>
        )}
      </Card>
      <p className="text-xs text-muted">
        Regime de caixa: pagamentos de fatura e de contas da casa contam no dia em que o dinheiro saiu. Para ver o consumo
        por categoria, use a aba Categorias.
      </p>
    </div>
  )
}

// ---------- Cartões ----------

function CardsReport({ from, to }: { from: string; to: string }) {
  const q = useCardReport(from, to)
  const r = q.data
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Compras no período" cents={r?.purchases_cents ?? 0} />
        <Stat label="Pago no período" cents={r?.paid_cents ?? 0} />
        <Stat label="Em aberto hoje" cents={r?.open_cents ?? 0} />
        <Stat label="Parcelas futuras" cents={r?.future_cents ?? 0} />
      </div>
      {q.isError ? (
        <Card>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </Card>
      ) : !r ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : r.cards.length === 0 ? (
        <Card>
          <EmptyState icon={<CreditCard />} title="Nenhum cartão" description="Cadastre um cartão para acompanhar compras e faturas." />
        </Card>
      ) : (
        <motion.div variants={staggerContainer} initial="initial" animate="enter" className="grid gap-4 md:grid-cols-2">
          {r.cards.map((c) => (
            <motion.div key={c.card_id} variants={listItem}>
              <Card className="h-full p-5">
                <Link to={`/cartoes/${c.card_id}`} className="flex items-center gap-3 hover:opacity-90">
                  <BrandAvatar name={c.bank ?? c.name} fallbackColor={c.color} />
                  <div className="min-w-0">
                    <p className="truncate font-medium">{c.name}</p>
                    <p className="text-xs text-muted">
                      {c.bank ?? 'Cartão'} · limite {formatBRL(c.limit_cents)}
                    </p>
                  </div>
                </Link>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs text-muted">Compras ({c.purchases_count})</dt>
                    <dd className="num font-medium">{formatBRL(c.purchases_cents)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Pago no período</dt>
                    <dd className="num font-medium">{formatBRL(c.paid_cents)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Em aberto</dt>
                    <dd className="num font-medium">{formatBRL(c.open_cents)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Parcelas futuras</dt>
                    <dd className="num font-medium">{formatBRL(c.future_cents)}</dd>
                  </div>
                </dl>
                {c.top_merchants.length > 0 && (
                  <>
                    <p className="mt-4 mb-2 text-xs font-medium text-muted">Onde mais gastou</p>
                    <ul className="space-y-2">
                      {c.top_merchants.map((m) => (
                        <li key={m.name} className="flex items-center gap-3">
                          <BrandAvatar name={m.name} size="sm" card={{ name: c.name, bank: c.bank, color: c.color }} />
                          <span className="min-w-0 flex-1 truncate text-sm">
                            {m.name}
                            {m.count > 1 && <span className="text-xs text-muted"> · {m.count}×</span>}
                          </span>
                          <span className="num text-sm">{formatBRL(m.amount_cents)}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </Card>
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  )
}

// ---------- Terceiros (aging) ----------

const AGING: { key: keyof AgingBuckets; label: string; cls: string }[] = [
  { key: 'current_cents', label: 'A vencer', cls: 'bg-positive' },
  { key: 'no_due_cents', label: 'Sem vencimento', cls: 'bg-muted' },
  { key: 'd0_30_cents', label: '1–30 dias', cls: 'bg-warning' },
  { key: 'd31_60_cents', label: '31–60 dias', cls: 'bg-orange-500' },
  { key: 'd61_90_cents', label: '61–90 dias', cls: 'bg-red-500' },
  { key: 'd90_plus_cents', label: '90+ dias', cls: 'bg-red-800' },
]

function AgingBar({ aging, total }: { aging: AgingBuckets; total: number }) {
  if (total <= 0) return <div className="h-2.5 rounded-full bg-surface-2" aria-hidden />
  return (
    <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={AGING.map((a) => `${a.label}: ${formatBRL(aging[a.key])}`).join('; ')}>
      {AGING.filter((a) => aging[a.key] > 0).map((a) => (
        <span key={a.key} className={cn('h-full', a.cls)} style={{ width: `${(aging[a.key] / total) * 100}%` }} />
      ))}
    </div>
  )
}

function CounterpartiesReport({ from, to }: { from: string; to: string }) {
  const q = useCounterpartyReport(from, to)
  const r = q.data
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Stat label="Me devem (em aberto)" cents={r?.receivable_cents ?? 0} tone="text-positive" />
        <Stat label="Eu devo (em aberto)" cents={r?.payable_cents ?? 0} tone="text-warning" />
      </div>
      {q.isError ? (
        <Card>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </Card>
      ) : !r ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : (
        <>
          <Card className="p-5">
            <p className="text-[15px] font-medium">Atraso dos valores a receber</p>
            <p className="mb-3 text-xs text-muted">Quanto do que te devem já venceu, por dias de atraso.</p>
            <AgingBar aging={r.receivable_aging} total={r.receivable_cents} />
            <ul className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 lg:grid-cols-6">
              {AGING.map((a) => (
                <li key={a.key} className="flex flex-col gap-0.5">
                  <span className="flex items-center gap-1.5 text-muted">
                    <span className={cn('size-2 rounded-sm', a.cls)} aria-hidden />
                    {a.label}
                  </span>
                  <span className="num text-sm font-medium">{formatBRL(r.receivable_aging[a.key])}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="overflow-hidden">
            <CardHeader title="Por pessoa" description="Recebido no período considera só os acertos não estornados." />
            {r.people.length === 0 ? (
              <EmptyState icon={<HandCoins />} title="Nada em aberto" description="Ninguém te deve e você não deve a ninguém." />
            ) : (
              <ul className="divide-y divide-border border-t border-border">
                {r.people.map((p) => (
                  <li key={p.person_id} className="px-5 py-3">
                    <div className="flex flex-wrap items-center gap-3">
                      <Link to={`/pessoas/${p.person_id}`} className="min-w-0 flex-1 truncate text-sm font-medium hover:underline">
                        {p.name}
                      </Link>
                      <span className="text-xs text-muted">
                        me deve <span className="num font-medium text-positive">{formatBRL(p.receivable_cents)}</span>
                        {p.payable_cents > 0 && (
                          <>
                            {' '}· devo <span className="num font-medium text-warning">{formatBRL(p.payable_cents)}</span>
                          </>
                        )}
                        {p.settled_in_period_cents > 0 && <> · recebido {formatBRL(p.settled_in_period_cents)}</>}
                      </span>
                    </div>
                    {p.receivable_cents > 0 && (
                      <div className="mt-2">
                        <AgingBar aging={p.receivable_aging} total={p.receivable_cents} />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
