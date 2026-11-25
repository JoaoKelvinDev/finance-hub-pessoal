import { motion } from 'motion/react'
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  ChevronRight,
  CreditCard,
  HandCoins,
  Info,
  Landmark,
  Minus,
  Plus,
  Receipt,
  Repeat,
  Scale,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useMemo, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { PeriodPicker, usePeriod } from '@/components/finance/period-picker'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton, TransactionList } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, Skeleton } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/misc'
import { useQuickAdd } from '@/app/layout'
import { useTransactionActions } from '@/features/transactions/actions'
import { addDays, daysBetween, formatDate, formatMonth, formatShortDate } from '@/lib/date'
import { formatBRL, formatPct } from '@/lib/money'
import { riseItem, staggerContainer } from '@/lib/motion'
import { useCalendar, useDashboard } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { CalendarEvent, CalendarSource, Dashboard, Kpi } from '@/types/api'

// Recharts fica num chunk separado, carregado depois do painel principal.
const BalanceChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.BalanceChart })))
const CategoryChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.CategoryChart })))
const Sparkline = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.Sparkline })))

function ChartSlot({ children, h = 'h-64' }: { children: ReactNode; h?: string }) {
  return <Suspense fallback={<Skeleton className={cn('m-5', h)} />}>{children}</Suspense>
}

export function DashboardPage() {
  const period = usePeriod()
  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useDashboard(period.from, period.to)
  const quickAdd = useQuickAdd()
  const actions = useTransactionActions()
  const navigate = useNavigate()

  const toTx = (extra: string) => `/lancamentos?period=custom&from=${period.from}&to=${period.to}${extra}`

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-xs text-muted" aria-live="polite">
            <span className={cn('size-1.5 rounded-full bg-positive', isFetching && 'animate-pulse bg-warning')} aria-hidden />
            {isFetching
              ? 'Atualizando…'
              : dataUpdatedAt
                ? `Atualizado às ${new Date(dataUpdatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
                : ''}
          </p>
        </div>
        <PeriodPicker period={period} />
      </div>

      {isError ? (
        <Card>
          <ErrorState message={(error as Error)?.message} onRetry={() => refetch()} />
        </Card>
      ) : isLoading || !data ? (
        <DashboardSkeleton />
      ) : data.accounts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Landmark />}
            title="Comece cadastrando uma conta"
            description="Informe o saldo atual da sua conta corrente ou carteira. Todos os números do painel partem dela."
            action={
              <Button onClick={() => navigate('/contas?nova=1')}>
                <Plus /> Cadastrar conta
              </Button>
            }
          />
        </Card>
      ) : (
        <motion.div
          variants={staggerContainer}
          initial="initial"
          animate="enter"
          className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]"
        >
          {/* Coluna principal */}
          <div className="min-w-0 space-y-5">
            {/* No celular/tablet, a pergunta principal vem primeiro; no desktop ela fica na coluna lateral. */}
            <motion.div variants={riseItem} className="xl:hidden">
              <FreeToSpend data={data} onExpense={() => quickAdd('EXPENSE')} onIncome={() => quickAdd('INCOME')} />
            </motion.div>
            <KpiRow data={data} toTx={toTx} />

            <motion.div variants={riseItem}>
              <Card>
                <ChartSlot h="h-72">
                  <BalanceChart data={data.balance_series} today={data.today} />
                </ChartSlot>
              </Card>
            </motion.div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
              <motion.div variants={riseItem}>
                <Card className="h-full overflow-hidden">
                  <SectionHeader title="Últimas movimentações" to="/lancamentos" />
                  {data.recent.length ? (
                    <TransactionList items={data.recent} onCancel={actions.onCancel} compact />
                  ) : (
                    <EmptyState
                      icon={<ArrowUpRight />}
                      title="Nenhuma movimentação ainda"
                      description="Registre sua primeira despesa ou receita."
                      action={
                        <Button size="sm" onClick={() => quickAdd()}>
                          <Plus /> Novo lançamento
                        </Button>
                      }
                    />
                  )}
                </Card>
              </motion.div>
              <motion.div variants={riseItem}>
                <UpcomingPayments today={data.today} dueSoon={data.kpis.due_soon} overdue={data.kpis.overdue} />
              </motion.div>
            </div>
          </div>

          {/* Coluna lateral */}
          <div className="min-w-0 space-y-5">
            <motion.div variants={riseItem} className="hidden xl:block">
              <FreeToSpend data={data} onExpense={() => quickAdd('EXPENSE')} onIncome={() => quickAdd('INCOME')} />
            </motion.div>
            <motion.div variants={riseItem}>
              <Card>
                <ChartSlot h="h-80">
                  <CategoryChart data={data.expenses_by_category} />
                </ChartSlot>
              </Card>
            </motion.div>
            <motion.div variants={riseItem}>
              <PartiesCard receivables={data.kpis.receivables} payables={data.kpis.payables} />
            </motion.div>
            <motion.div variants={riseItem}>
              <AccountsCard data={data} />
            </motion.div>
          </div>
        </motion.div>
      )}
      {actions.dialog}
    </div>
  )
}

// ---------- KPIs com minigráfico ----------

function KpiRow({ data, toTx }: { data: Dashboard; toTx: (extra: string) => string }) {
  const monthly = data.monthly
  const label = (m: string) => formatMonth(m)
  const realBalance = data.balance_series.filter((p) => !p.projected)
  // Até ~30 pontos: suficiente para a forma da curva sem pesar o cartão.
  const step = Math.max(1, Math.ceil(realBalance.length / 30))
  const balancePoints = realBalance
    .filter((_, i) => i % step === 0 || i === realBalance.length - 1)
    .map((p) => ({ label: formatShortDate(p.date), value: p.balance_cents }))

  return (
    <motion.div variants={staggerContainer} className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
      <KpiTile
        id="balance"
        label="Saldo disponível"
        kpi={data.kpis.available_balance}
        icon={Wallet}
        tone="accent"
        points={balancePoints}
        to="/contas"
      />
      <KpiTile
        id="income"
        label="Receitas"
        kpi={data.kpis.income}
        icon={ArrowDownLeft}
        tone="positive"
        points={monthly.map((m) => ({ label: label(m.month), value: m.income_cents }))}
        to={toTx('&group=income')}
      />
      <KpiTile
        id="expense"
        label="Despesas"
        kpi={data.kpis.expense}
        icon={ArrowUpRight}
        tone="negative"
        inverse
        points={monthly.map((m) => ({ label: label(m.month), value: m.expense_cents }))}
        to={toTx('&group=expense')}
      />
      <KpiTile
        id="net"
        label="Resultado"
        kpi={data.kpis.net}
        icon={Scale}
        tone={data.kpis.net.value_cents < 0 ? 'negative' : 'positive'}
        points={monthly.map((m) => ({ label: label(m.month), value: m.net_cents }))}
        to={toTx('')}
      />
    </motion.div>
  )
}

function KpiTile({
  id,
  label,
  kpi,
  icon: Icon,
  tone,
  points,
  to,
  inverse,
}: {
  id: string
  label: string
  kpi: Kpi
  icon: LucideIcon
  tone: 'positive' | 'negative' | 'accent'
  points: { label: string; value: number }[]
  to: string
  /** true quando subir é ruim (despesas). */
  inverse?: boolean
}) {
  const change = kpi.change_pct
  const good = change === null || change === 0 ? null : inverse ? change < 0 : change > 0
  const Trend = change === null || change === 0 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <motion.div variants={riseItem}>
      <Link
        to={to}
        className="group block h-full rounded-2xl border border-border bg-surface bg-gradient-to-b from-white/[0.025] to-transparent p-4 shadow-card transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/40"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-[13px] text-muted">
            <Icon className="size-4" aria-hidden />
            {label}
          </span>
          <Tooltip content={kpi.formula}>
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => e.preventDefault()}
              className="grid size-6 place-items-center rounded-md text-muted/60 hover:text-fg"
              aria-label={`Como é calculado: ${kpi.formula}`}
            >
              <Info className="size-3.5" />
            </span>
          </Tooltip>
        </div>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
          <CurrencyDisplay cents={kpi.value_cents} className="text-[26px] font-normal tracking-tight" />
          {change !== null && (
            <span
              className={cn(
                'inline-flex items-center gap-0.5 text-xs font-medium',
                good === true && 'text-positive',
                good === false && 'text-negative',
                good === null && 'text-muted',
              )}
              title="Variação em relação ao período anterior"
            >
              <Trend className="size-3.5" aria-hidden />
              {formatPct(change)}
            </span>
          )}
        </div>
        <div className="mt-2">
          <Suspense fallback={<div className="h-12" />}>
            <Sparkline id={id} points={points} tone={tone} />
          </Suspense>
        </div>
      </Link>
    </motion.div>
  )
}

// ---------- Cartões laterais ----------

function SectionHeader({ title, to, label = 'Ver mais', extra }: { title: string; to?: string; label?: string; extra?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-3">
      <h2 className="text-[15px] font-medium tracking-tight">{title}</h2>
      <div className="flex items-center gap-3">
        {extra}
        {to && (
          <Link to={to} className="inline-flex items-center gap-0.5 text-[13px] text-muted hover:text-fg">
            {label} <ChevronRight className="size-3.5" aria-hidden />
          </Link>
        )}
      </div>
    </div>
  )
}

function FreeToSpend({ data, onExpense, onIncome }: { data: Dashboard; onExpense: () => void; onIncome: () => void }) {
  const commitments = data.kpis.available_balance.value_cents - data.free_after_commitments_cents
  return (
    <Card className="relative overflow-hidden p-5">
      <div className="pointer-events-none absolute -top-20 -right-16 size-56 rounded-full bg-accent/25 blur-3xl" aria-hidden />
      <p className="relative flex items-center gap-1.5 text-[13px] text-muted">
        Quanto posso gastar até {formatDate(data.free_until)}?
        <Tooltip content="Saldo disponível menos despesas previstas (inclusive vencidas) até o próximo recebimento previsto, ou 30 dias. Calculado só com o que você cadastrou — não é garantia.">
          <button className="text-muted/70 hover:text-fg" aria-label="Como é calculado">
            <Info className="size-3.5" />
          </button>
        </Tooltip>
      </p>
      <CurrencyDisplay
        cents={data.free_after_commitments_cents}
        className={cn('relative mt-1.5 block text-[34px] font-normal tracking-tight', data.free_after_commitments_cents < 0 && 'text-negative')}
      />
      <p className="relative mt-1 text-xs text-muted">
        {formatBRL(commitments)} comprometidos · {daysBetween(data.today, data.free_until)} dias
      </p>
      <div className="relative mt-4 grid grid-cols-2 gap-2">
        <Button variant="secondary" size="sm" onClick={onExpense}>
          <ArrowUpRight /> Despesa
        </Button>
        <Button variant="secondary" size="sm" onClick={onIncome}>
          <ArrowDownLeft /> Receita
        </Button>
      </div>
    </Card>
  )
}

function PartiesCard({ receivables, payables }: { receivables: Kpi; payables: Kpi }) {
  // Proporção visual entre o que me devem e o que devo (não é compensação de dívidas).
  const total = receivables.value_cents + payables.value_cents
  const share = total > 0 ? Math.round((receivables.value_cents / total) * 100) : 0
  return (
    <Card>
      <SectionHeader title="Valores com terceiros" to="/terceiros" />
      <div className="space-y-3 px-5 pb-5">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-muted">Me devem</p>
            <CurrencyDisplay cents={receivables.value_cents} className="text-lg text-positive" />
          </div>
          <div className="text-right">
            <p className="text-xs text-muted">Eu devo</p>
            <CurrencyDisplay cents={payables.value_cents} className="text-lg text-warning" />
          </div>
        </div>
        {total > 0 ? (
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={`${share}% do total em aberto é a receber`}>
            <span className="h-full rounded-full bg-positive" style={{ width: `${share}%` }} />
            <span className="h-full flex-1 rounded-full bg-warning" />
          </div>
        ) : (
          <p className="text-xs text-muted">Nenhum valor em aberto com terceiros.</p>
        )}
      </div>
    </Card>
  )
}

function AccountsCard({ data }: { data: Dashboard }) {
  return (
    <Card className="overflow-hidden">
      <SectionHeader title="Contas e carteiras" to="/contas" label="Gerenciar" />
      <ul className="divide-y divide-border border-t border-border">
        {data.accounts.map((a) => (
          <li key={a.id}>
            <Link to={`/contas/${a.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-surface-2/60">
              <span className="size-2.5 rounded-full" style={{ background: a.color }} aria-hidden />
              <span className="flex-1 truncate text-sm">{a.name}</span>
              <CurrencyDisplay cents={a.balance_cents} className="text-sm font-medium" />
            </Link>
          </li>
        ))}
      </ul>
      <div className="grid grid-cols-2 gap-px border-t border-border bg-border text-center">
        <div className="bg-surface px-4 py-3">
          <p className="text-[11px] text-muted">Taxa de poupança</p>
          <p className="num text-sm font-semibold">
            {data.health.savings_rate_pct === null ? 'N/A' : `${data.health.savings_rate_pct.toLocaleString('pt-BR')}%`}
          </p>
        </div>
        <div className="bg-surface px-4 py-3">
          <p className="text-[11px] text-muted">Obrigações vencidas</p>
          <p className={cn('num text-sm font-semibold', data.health.overdue_count > 0 && 'text-negative')}>
            {data.health.overdue_count}
          </p>
        </div>
      </div>
    </Card>
  )
}

// ---------- Próximos pagamentos (mesma fonte do calendário) ----------

const SOURCE_ICON: Record<CalendarSource, LucideIcon> = {
  CARD_STATEMENT: CreditCard,
  BILL_INSTALLMENT: Receipt,
  RECURRENCE_FORECAST: Repeat,
  PLANNED_TRANSACTION: CalendarClock,
  PARTY_BALANCE: HandCoins,
}
const OPEN: CalendarEvent['status'][] = ['PENDING', 'OVERDUE', 'PARTIAL']

function UpcomingPayments({ today, dueSoon, overdue }: { today: string; dueSoon: Kpi; overdue: Kpi }) {
  // Janela: 30 dias para trás (vencidos) até 30 à frente — dentro do limite de 92 dias da API.
  const q = useCalendar(addDays(today, -30), addDays(today, 30))
  const items = useMemo(
    () =>
      (q.data?.events ?? [])
        .filter((e) => e.direction === 'OUT' && OPEN.includes(e.status))
        .sort((a, b) => Number(b.status === 'OVERDUE') - Number(a.status === 'OVERDUE') || a.date.localeCompare(b.date))
        .slice(0, 6),
    [q.data],
  )

  return (
    <Card className="h-full overflow-hidden">
      <SectionHeader title="Próximos pagamentos" to="/calendario" label="Calendário" />
      <div className="grid grid-cols-2 gap-px border-y border-border bg-border text-center">
        <div className="bg-surface px-3 py-2.5">
          <p className="text-[11px] text-muted">A vencer (30 dias)</p>
          <CurrencyDisplay cents={dueSoon.value_cents} className="text-sm font-semibold" animated={false} />
        </div>
        <div className="bg-surface px-3 py-2.5">
          <p className="text-[11px] text-muted">Vencidas</p>
          <CurrencyDisplay
            cents={overdue.value_cents}
            className={cn('text-sm font-semibold', overdue.value_cents > 0 && 'text-negative')}
            animated={false}
          />
        </div>
      </div>
      {q.isPending ? (
        <ListSkeleton rows={3} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<CalendarClock />}
          title="Nada a pagar"
          description="Sem faturas, contas ou dívidas abertas nos próximos 30 dias."
        />
      ) : (
        <ul className="divide-y divide-border">
          {items.map((e) => {
            const Icon = SOURCE_ICON[e.source]
            const late = e.status === 'OVERDUE'
            return (
              <li key={e.key} className="flex items-center gap-3 px-5 py-3">
                <span
                  className="grid size-9 shrink-0 place-items-center rounded-full [&_svg]:size-4"
                  style={{ background: `${e.color}26`, color: e.color }}
                  aria-hidden
                >
                  <Icon />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{e.title}</p>
                  <p className={cn('text-xs', late ? 'font-medium text-negative' : 'text-muted')}>
                    {late ? (
                      <span className="inline-flex items-center gap-1">
                        <AlertTriangle className="size-3" aria-hidden /> Venceu {formatShortDate(e.date)}
                      </span>
                    ) : (
                      `Vence ${formatShortDate(e.date)}`
                    )}
                    {e.estimated && ' · estimado'}
                  </p>
                </div>
                <span className="num shrink-0 text-sm font-medium">{formatBRL(e.open_cents)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]" aria-busy="true" aria-label="Carregando painel">
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-2xl" />
        <Card>
          <ListSkeleton />
        </Card>
      </div>
      <div className="space-y-5">
        <Skeleton className="h-48 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    </div>
  )
}
