import { motion } from 'motion/react'
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  CalendarClock,
  Info,
  Landmark,
  Plus,
  Scale,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { FinancialKpi } from '@/components/finance/kpi'
import { PeriodPicker, usePeriod } from '@/components/finance/period-picker'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton, TransactionList } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/misc'
import { useQuickAdd } from '@/app/layout'
import { useTransactionActions } from '@/features/transactions/actions'
import { daysBetween, formatDate } from '@/lib/date'
import { riseItem, staggerContainer } from '@/lib/motion'
import { useDashboard } from '@/lib/queries'
import { cn } from '@/lib/utils'

// Recharts fica num chunk separado, carregado depois do painel principal.
const IncomeExpenseChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.IncomeExpenseChart })))
const BalanceChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.BalanceChart })))
const CategoryChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.CategoryChart })))

function ChartSlot({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Skeleton className="m-5 h-64" />}>{children}</Suspense>
}

export function DashboardPage() {
  const period = usePeriod()
  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useDashboard(period.from, period.to)
  const quickAdd = useQuickAdd()
  const actions = useTransactionActions()
  const navigate = useNavigate()

  const toTx = (extra: string) => `/lancamentos?period=custom&from=${period.from}&to=${period.to}${extra}`

  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PeriodPicker period={period} />
        <p className="flex items-center gap-2 text-xs text-muted" aria-live="polite">
          <span className={cn('size-1.5 rounded-full bg-positive', isFetching && 'animate-pulse bg-warning')} aria-hidden />
          {isFetching ? 'Atualizando…' : dataUpdatedAt ? `Atualizado às ${new Date(dataUpdatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : ''}
          {data && ` · ${data.timezone}`}
        </p>
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
        <motion.div variants={staggerContainer} initial="initial" animate="enter" className="space-y-5">
          {/* Quanto posso gastar hoje? */}
          <motion.div variants={riseItem}>
            <Card className="relative overflow-hidden">
              <div
                className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full bg-accent/10 blur-3xl"
                aria-hidden
              />
              <div className="relative grid grid-cols-1 gap-6 p-5 sm:p-6 lg:grid-cols-[1.2fr_1fr_1fr_auto] lg:items-end">
                <div>
                  <p className="flex items-center gap-1.5 text-sm font-medium text-muted">
                    Quanto posso gastar até {formatDate(data.free_until)}?
                    <Tooltip content="Saldo disponível menos despesas previstas (inclusive vencidas) até o próximo recebimento previsto, ou 30 dias. Calculado só com o que você cadastrou — não é garantia.">
                      <button className="text-muted/70 hover:text-fg" aria-label="Como é calculado">
                        <Info className="size-3.5" />
                      </button>
                    </Tooltip>
                  </p>
                  <CurrencyDisplay
                    cents={data.free_after_commitments_cents}
                    className={cn(
                      'mt-2 block text-4xl font-semibold tracking-tight sm:text-[42px]',
                      data.free_after_commitments_cents < 0 && 'text-negative',
                    )}
                  />
                  <p className="mt-1 text-xs text-muted">
                    Saldo livre estimado · {daysBetween(data.today, data.free_until)} dias
                  </p>
                </div>
                <HeroStat label="Saldo disponível" cents={data.kpis.available_balance.value_cents} icon={<Wallet />} />
                <HeroStat
                  label="Compromissos no intervalo"
                  cents={-(data.kpis.available_balance.value_cents - data.free_after_commitments_cents)}
                  icon={<CalendarClock />}
                />
                <div className="flex gap-2 lg:flex-col">
                  <Button variant="secondary" size="sm" onClick={() => quickAdd('EXPENSE')}>
                    <ArrowUpRight /> Despesa
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => quickAdd('INCOME')}>
                    <ArrowDownLeft /> Receita
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>

          {/* KPIs */}
          <motion.div variants={staggerContainer} className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <FinancialKpi label="Receitas realizadas" kpi={data.kpis.income} icon={<ArrowDownLeft />} to={toTx('&group=income')} />
            <FinancialKpi label="Despesas realizadas" kpi={data.kpis.expense} icon={<ArrowUpRight />} to={toTx('&group=expense')} inverse />
            <FinancialKpi label="Resultado do período" kpi={data.kpis.net} icon={<Scale />} to={toTx('')} />
            <FinancialKpi
              label="A vencer (30 dias)"
              kpi={data.kpis.due_soon}
              icon={<CalendarClock />}
              to="/lancamentos?period=all&status=PLANNED&group=expense"
              emphasis={data.kpis.due_soon.value_cents > 0 ? 'warning' : 'default'}
            />
            <FinancialKpi
              label="Vencidas"
              kpi={data.kpis.overdue}
              icon={<AlertTriangle />}
              to="/lancamentos?period=all&status=PLANNED&group=expense"
              emphasis={data.kpis.overdue.value_cents > 0 ? 'danger' : 'default'}
            />
            <FinancialKpi label="Disponível projetado (30 dias)" kpi={data.kpis.projected} icon={<TrendingUp />} />
          </motion.div>

          {/* Gráficos */}
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <ChartSlot>
                  <IncomeExpenseChart data={data.monthly} />
                </ChartSlot>
              </Card>
            </motion.div>
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <ChartSlot>
                  <BalanceChart data={data.balance_series} today={data.today} />
                </ChartSlot>
              </Card>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <ChartSlot>
                  <CategoryChart data={data.expenses_by_category} />
                </ChartSlot>
              </Card>
            </motion.div>
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <CardHeader
                  title="Pendências prioritárias"
                  description="Vencidas primeiro, depois as próximas."
                  action={
                    <Link to="/lancamentos?period=all&status=PLANNED" className="text-[13px] font-medium text-accent hover:underline">
                      Ver todas
                    </Link>
                  }
                />
                {data.upcoming.length ? (
                  <TransactionList items={data.upcoming} onPost={actions.onPost} onCancel={actions.onCancel} compact />
                ) : (
                  <EmptyState
                    icon={<CalendarClock />}
                    title="Nada pendente"
                    description="Lance contas futuras como “Previsto” para acompanhá-las aqui."
                  />
                )}
              </Card>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <CardHeader
                  title="Contas e carteiras"
                  action={
                    <Link to="/contas" className="text-[13px] font-medium text-accent hover:underline">
                      Gerenciar
                    </Link>
                  }
                />
                <ul className="divide-y divide-border">
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
            </motion.div>
            <motion.div variants={riseItem}>
              <Card className="h-full">
                <CardHeader
                  title="Últimas movimentações"
                  action={
                    <Link to="/lancamentos" className="text-[13px] font-medium text-accent hover:underline">
                      Ver lançamentos
                    </Link>
                  }
                />
                {data.recent.length ? (
                  <TransactionList items={data.recent} onCancel={actions.onCancel} />
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
          </div>
        </motion.div>
      )}
      {actions.dialog}
    </div>
  )
}

function HeroStat({ label, cents, icon }: { label: string; cents: number; icon: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-surface-2 [&_svg]:size-4" aria-hidden>
        {icon}
      </span>
      <div>
        <p className="text-xs text-muted">{label}</p>
        <CurrencyDisplay cents={cents} className="mt-0.5 block text-lg font-semibold" />
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Carregando painel">
      <Skeleton className="h-36 rounded-xl" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Skeleton className="h-80 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
      <Card>
        <ListSkeleton />
      </Card>
    </div>
  )
}
