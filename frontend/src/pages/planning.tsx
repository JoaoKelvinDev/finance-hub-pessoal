import { AnimatePresence, motion } from 'motion/react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  PiggyBank,
  Plus,
  Target,
  Trash2,
  TrendingDown,
  Undo2,
  Wallet,
  XCircle,
} from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { CurrencyDisplay, MoneyInput } from '@/components/finance/currency'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { ReasonDialog } from '@/features/parties/dialogs'
import { readApiError } from '@/features/parties/meta'
import { addMonths, formatDate, lastDay, monthRange, todayISO } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import { listItem, staggerContainer } from '@/lib/motion'
import {
  useAccounts,
  useAllocateGoal,
  useBudgets,
  useCancelGoal,
  useCategories,
  useCopyBudgets,
  useCreateBudget,
  useCreateGoal,
  useDeleteBudget,
  useGoals,
  useProjection,
  useReverseAllocation,
} from '@/lib/queries'
import { cn, newIdempotencyKey } from '@/lib/utils'
import type { Budget, BudgetBasis, Goal } from '@/types/api'

const ProjectionChart = lazy(() => import('@/components/charts/charts').then((m) => ({ default: m.ProjectionChart })))

type Tab = 'budgets' | 'goals' | 'projection'

const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
const monthLabel = (iso: string) => {
  const [y, m] = iso.split('-').map(Number)
  return `${MONTHS[m - 1]} de ${y}`
}

export function PlanningPage() {
  const [tab, setTab] = useState<Tab>('budgets')
  return (
    <div className="mx-auto max-w-[1200px] space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">Orçamentos, metas e para onde seu saldo está indo.</p>
        <Segmented
          label="Seção do planejamento"
          layoutId="planning-tab"
          value={tab}
          onChange={setTab}
          options={[
            { value: 'budgets', label: 'Orçamentos' },
            { value: 'goals', label: 'Metas' },
            { value: 'projection', label: 'Projeção' },
          ]}
        />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.2 } }}
          exit={{ opacity: 0, transition: { duration: 0.12 } }}
        >
          {tab === 'budgets' ? <BudgetsTab /> : tab === 'goals' ? <GoalsTab /> : <ProjectionTab />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

// =====================================================================
// Orçamentos
// =====================================================================

const BUDGET_STATUS = {
  OK: { label: 'Dentro do orçamento', icon: CheckCircle2, cls: 'text-positive', bar: 'bg-accent' },
  WARNING: { label: 'Atenção: passou de 80%', icon: AlertTriangle, cls: 'text-warning', bar: 'bg-warning' },
  OVER: { label: 'Estourado', icon: XCircle, cls: 'text-negative', bar: 'bg-negative' },
} as const

function BudgetsTab() {
  const [month, setMonth] = useState(todayISO().slice(0, 7) + '-01')
  const [from, to] = monthRange(month)
  const q = useBudgets()
  const copy = useCopyBudgets()
  const del = useDeleteBudget()
  const [newOpen, setNewOpen] = useState(false)

  const items = useMemo(
    () => (q.data ?? []).filter((b) => b.period_start <= to && b.period_end >= from).sort((a, b) => b.progress_pct - a.progress_pct),
    [q.data, from, to],
  )
  const general = items.find((b) => b.category_id === null)
  const byCategory = items.filter((b) => b.category_id !== null)

  const copyFromPrevious = async () => {
    try {
      const r = await copy.mutateAsync({ from_month: addMonths(month, -1).slice(0, 7), to_month: month.slice(0, 7) })
      toast.success(
        r.created
          ? `${r.created} orçamento(s) copiado(s) de ${monthLabel(addMonths(month, -1))}.`
          : 'Nada novo para copiar do mês anterior.',
      )
    } catch (err) {
      toast.error(readApiError(err).message)
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => setMonth(addMonths(month, -1))} aria-label="Mês anterior">
              <ChevronLeft />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => setMonth(addMonths(month, 1))} aria-label="Próximo mês">
              <ChevronRight />
            </Button>
          </div>
          <h2 className="min-w-0 flex-1 text-[15px] font-medium first-letter:uppercase" aria-live="polite">
            {monthLabel(month)}
          </h2>
          <Button variant="secondary" size="sm" onClick={copyFromPrevious} loading={copy.isPending}>
            <Copy /> Copiar do mês anterior
          </Button>
          <Button size="sm" onClick={() => setNewOpen(true)}>
            <Plus /> Novo orçamento
          </Button>
        </div>
      </Card>

      {q.isError ? (
        <Card>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </Card>
      ) : q.isPending ? (
        <Card>
          <ListSkeleton rows={3} />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={<PiggyBank />}
            title="Nenhum orçamento neste mês"
            description="Defina um teto geral ou por categoria. A partir de 80% você recebe um alerta."
            action={
              <Button size="sm" onClick={() => setNewOpen(true)}>
                <Plus /> Criar orçamento
              </Button>
            }
          />
        </Card>
      ) : (
        <motion.div variants={staggerContainer} initial="initial" animate="enter" className="grid gap-4 md:grid-cols-2">
          {general && (
            <motion.div variants={listItem} className="md:col-span-2">
              <BudgetCard budget={general} onDelete={() => del.mutate(general.id)} highlight />
            </motion.div>
          )}
          {byCategory.map((b) => (
            <motion.div key={b.id} variants={listItem}>
              <BudgetCard budget={b} onDelete={() => del.mutate(b.id)} />
            </motion.div>
          ))}
        </motion.div>
      )}

      <NewBudgetDialog open={newOpen} onOpenChange={setNewOpen} month={month} />
    </div>
  )
}

function BudgetCard({ budget: b, onDelete, highlight }: { budget: Budget; onDelete: () => void; highlight?: boolean }) {
  const st = BUDGET_STATUS[b.status]
  const Icon = st.icon
  const spentPct = Math.min(100, (b.spent_cents / b.limit_cents) * 100)
  const committedPct = Math.min(100 - spentPct, (b.committed_cents / b.limit_cents) * 100)
  return (
    <Card className={cn('p-5', highlight && 'relative overflow-hidden')}>
      {highlight && <div className="pointer-events-none absolute -top-16 -right-10 size-48 rounded-full bg-accent/20 blur-3xl" aria-hidden />}
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[15px] font-medium">{b.category_name ?? 'Orçamento geral'}</p>
          <p className="text-xs text-muted">
            {b.basis === 'CASH' ? 'Base caixa' : 'Base competência'} · {formatDate(b.period_start)} a {formatDate(b.period_end)}
          </p>
        </div>
        <Button size="icon-sm" variant="ghost" onClick={onDelete} aria-label={`Excluir orçamento ${b.category_name ?? 'geral'}`}>
          <Trash2 />
        </Button>
      </div>

      <div className="relative mt-3 flex items-baseline justify-between gap-2">
        <CurrencyDisplay cents={b.used_cents} className="text-[24px] font-normal tracking-tight" />
        <span className="text-sm text-muted">de {formatBRL(b.limit_cents)}</span>
      </div>

      <div
        className="relative mt-2 flex h-2.5 overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(b.progress_pct)}
        aria-label={`${b.progress_pct.toLocaleString('pt-BR')}% usado`}
      >
        <motion.span
          className={cn('h-full', st.bar)}
          initial={{ width: 0 }}
          animate={{ width: `${spentPct}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        />
        {committedPct > 0 && (
          <motion.span
            className={cn('h-full opacity-45', st.bar)}
            style={{ backgroundImage: 'repeating-linear-gradient(135deg, transparent 0 3px, rgb(0 0 0 / 0.35) 3px 5px)' }}
            initial={{ width: 0 }}
            animate={{ width: `${committedPct}%` }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
      </div>

      <div className="relative mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className={cn('inline-flex items-center gap-1 font-medium', st.cls)}>
          <Icon className="size-3.5" aria-hidden /> {st.label} · {b.progress_pct.toLocaleString('pt-BR')}%
        </span>
        <span className="text-muted">
          {b.remaining_cents >= 0 ? `Restam ${formatBRL(b.remaining_cents)}` : `Passou ${formatBRL(-b.remaining_cents)}`}
        </span>
      </div>
      {b.committed_cents > 0 && (
        <p className="relative mt-1 text-xs text-muted">
          Pago {formatBRL(b.spent_cents)} · comprometido {formatBRL(b.committed_cents)} (contas e faturas a vencer)
        </p>
      )}
    </Card>
  )
}

function NewBudgetDialog({ open, onOpenChange, month }: { open: boolean; onOpenChange: (o: boolean) => void; month: string }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Novo orçamento" description={`Teto para ${monthLabel(month)}.`}>
      {open && <NewBudgetForm month={month} onDone={() => onOpenChange(false)} />}
    </Dialog>
  )
}

function NewBudgetForm({ month, onDone }: { month: string; onDone: () => void }) {
  const cats = useCategories()
  const create = useCreateBudget()
  const [categoryId, setCategoryId] = useState('')
  const [limit, setLimit] = useState<number | null>(null)
  const [basis, setBasis] = useState<BudgetBasis>('CASH')
  const [error, setError] = useState<string>()
  const [y, m] = month.split('-').map(Number)
  const roots = (cats.data ?? []).filter((c) => c.kind === 'EXPENSE' && !c.parent_id && !c.archived_at)
  const children = (parent: string) => (cats.data ?? []).filter((c) => c.parent_id === parent && !c.archived_at)

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!limit) return setError('Informe o teto do orçamento.')
        try {
          await create.mutateAsync({
            category_id: categoryId || null,
            period_start: month,
            period_end: `${month.slice(0, 8)}${String(lastDay(y, m)).padStart(2, '0')}`,
            limit_cents: limit,
            basis,
          })
          toast.success('Orçamento criado.')
          onDone()
        } catch (err) {
          toast.error(readApiError(err).message)
        }
      }}
    >
      <Field label="Categoria" hint="Uma categoria principal inclui as subcategorias.">
        {(p) => (
          <Select {...p} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Orçamento geral (todas as despesas)</option>
            {roots.map((r) => (
              <optgroup key={r.id} label={r.name}>
                <option value={r.id}>{r.name} (inteira)</option>
                {children(r.id).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Teto do mês" error={error}>
        {(p) => <MoneyInput {...p} valueCents={limit} onChangeCents={setLimit} />}
      </Field>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">O que conta como gasto?</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {(
            [
              ['CASH', 'Caixa', 'O que saiu da conta no mês. Cartão conta quando a fatura é paga.'],
              ['COMPETENCE', 'Competência', 'O que foi consumido no mês. Compra no cartão conta na data da compra.'],
            ] as const
          ).map(([v, label, hint]) => (
            <label
              key={v}
              className={cn(
                'flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3',
                basis === v ? 'border-accent bg-accent-soft/40' : 'border-border hover:bg-surface-2',
              )}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <input type="radio" name="basis" checked={basis === v} onChange={() => setBasis(v)} className="accent-[var(--color-accent)]" />
                {label}
              </span>
              <span className="text-xs text-muted">{hint}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" loading={create.isPending}>
          Criar orçamento
        </Button>
      </div>
    </form>
  )
}

// =====================================================================
// Metas
// =====================================================================

function GoalsTab() {
  const q = useGoals()
  const [newOpen, setNewOpen] = useState(false)
  const goals = q.data ?? []
  const active = goals.filter((g) => g.state !== 'CANCELLED')
  const cancelled = goals.filter((g) => g.state === 'CANCELLED')

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button onClick={() => setNewOpen(true)}>
          <Plus /> Nova meta
        </Button>
      </div>
      {q.isError ? (
        <Card>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </Card>
      ) : q.isPending ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-52 rounded-2xl" />
          <Skeleton className="h-52 rounded-2xl" />
        </div>
      ) : active.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Target />}
            title="Nenhuma meta ainda"
            description="Reserva de emergência, viagem, carro… Aportes entre suas contas não contam como gasto."
            action={
              <Button size="sm" onClick={() => setNewOpen(true)}>
                <Plus /> Criar meta
              </Button>
            }
          />
        </Card>
      ) : (
        <motion.div variants={staggerContainer} initial="initial" animate="enter" className="grid gap-4 md:grid-cols-2">
          {active.map((g) => (
            <motion.div key={g.id} variants={listItem}>
              <GoalCard goal={g} />
            </motion.div>
          ))}
        </motion.div>
      )}
      {cancelled.length > 0 && (
        <p className="text-xs text-muted">
          {cancelled.length} meta(s) cancelada(s): {cancelled.map((g) => g.title).join(', ')}.
        </p>
      )}
      <NewGoalDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

function monthsUntil(target: string, today: string) {
  const [ty, tm] = target.split('-').map(Number)
  const [y, m] = today.split('-').map(Number)
  return Math.max(1, (ty - y) * 12 + (tm - m))
}

function GoalCard({ goal: g }: { goal: Goal }) {
  const [allocating, setAllocating] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [reversing, setReversing] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const cancel = useCancelGoal()
  const reverse = useReverseAllocation()
  const achieved = g.state === 'ACHIEVED'
  const pct = Math.min(100, g.progress_pct)
  const perMonth = g.target_date && !achieved ? Math.ceil(g.remaining_cents / monthsUntil(g.target_date, todayISO())) : null
  const activeAllocations = g.allocations.filter((a) => !a.reversed_at)

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'grid size-10 shrink-0 place-items-center rounded-xl [&_svg]:size-5',
            achieved ? 'bg-positive-soft text-positive' : 'bg-accent-soft text-accent',
          )}
          aria-hidden
        >
          {achieved ? <CheckCircle2 /> : <Target />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-medium">{g.title}</p>
          <p className="text-xs text-muted">
            {formatBRL(g.allocated_cents)} de {formatBRL(g.target_cents)}
            {g.target_date && ` · até ${formatDate(g.target_date)}`}
          </p>
        </div>
        {achieved && (
          <span className="rounded-full bg-positive-soft px-2 py-0.5 text-[11px] font-medium text-positive">Atingida</span>
        )}
      </div>

      <div
        className="mt-4 h-2.5 overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`${g.progress_pct.toLocaleString('pt-BR')}% da meta`}
      >
        <motion.div
          className={cn('h-full rounded-full', achieved ? 'bg-positive' : 'bg-gradient-to-r from-violet-500 to-fuchsia-500')}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-muted">
        <span>{g.progress_pct.toLocaleString('pt-BR')}%</span>
        {!achieved && <span>Faltam {formatBRL(g.remaining_cents)}</span>}
      </div>
      {perMonth !== null && perMonth > 0 && (
        <p className="mt-1 text-xs text-muted">
          Para chegar no prazo: cerca de <span className="font-medium text-fg">{formatBRL(perMonth)}</span> por mês.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-1.5">
        {!achieved && (
          <Button size="sm" onClick={() => setAllocating(true)}>
            <PiggyBank /> Aportar
          </Button>
        )}
        <Button size="sm" variant="secondary" onClick={() => setShowHistory((v) => !v)} aria-expanded={showHistory}>
          Histórico ({activeAllocations.length})
        </Button>
        <Button size="sm" variant="ghost" className="text-negative hover:bg-negative-soft hover:text-negative" onClick={() => setCancelling(true)}>
          <XCircle /> Cancelar meta
        </Button>
      </div>

      <AnimatePresence initial={false}>
        {showHistory && (
          <motion.ol
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-3 divide-y divide-border overflow-hidden rounded-lg border border-border text-xs"
          >
            {g.allocations.length === 0 && <li className="px-3 py-2 text-muted">Nenhum aporte ainda.</li>}
            {[...g.allocations].reverse().map((a) => (
              <li key={a.id} className={cn('flex items-center gap-3 px-3 py-2', a.reversed_at && 'text-muted line-through')}>
                <span className="w-20 shrink-0 tabular-nums text-muted">{formatDate(a.allocated_on)}</span>
                <span className="min-w-0 flex-1 truncate">
                  {a.transfer_group_id ? 'Transferência entre contas' : 'Aporte registrado'}
                  {a.reversed_at && ` · estornado (${a.reverse_reason})`}
                </span>
                <span className="tabular-nums font-medium">{formatBRL(a.amount_cents)}</span>
                {!a.reversed_at && (
                  <Button size="icon-sm" variant="ghost" onClick={() => setReversing(a.id)} aria-label="Estornar aporte">
                    <Undo2 />
                  </Button>
                )}
              </li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>

      <AllocateDialog goal={allocating ? g : null} onClose={() => setAllocating(false)} />
      <ReasonDialog
        open={cancelling}
        title="Cancelar meta"
        description="A meta sai da lista. Os aportes já feitos continuam no histórico (o dinheiro não se move)."
        confirmLabel="Cancelar meta"
        pending={cancel.isPending}
        onClose={() => setCancelling(false)}
        onConfirm={async (reason) => {
          await cancel.mutateAsync({ id: g.id, reason })
          toast.success('Meta cancelada.')
          setCancelling(false)
        }}
      />
      <ReasonDialog
        open={!!reversing}
        title="Estornar aporte"
        description="Se o aporte moveu dinheiro entre contas, a transferência também é desfeita."
        confirmLabel="Estornar"
        pending={reverse.isPending}
        onClose={() => setReversing(null)}
        onConfirm={async (reason) => {
          await reverse.mutateAsync({ goalId: g.id, allocationId: reversing!, reason })
          toast.success('Aporte estornado.')
          setReversing(null)
        }}
      />
    </Card>
  )
}

function NewGoalDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Nova meta" description="Ex.: reserva de emergência, viagem, troca de carro.">
      {open && <NewGoalForm onDone={() => onOpenChange(false)} />}
    </Dialog>
  )
}

function NewGoalForm({ onDone }: { onDone: () => void }) {
  const create = useCreateGoal()
  const [title, setTitle] = useState('')
  const [target, setTarget] = useState<number | null>(null)
  const [date, setDate] = useState('')
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        const errs: Record<string, string> = {}
        if (!title.trim()) errs.title = 'Dê um nome para a meta.'
        if (!target) errs.target = 'Informe o valor da meta.'
        setErrors(errs)
        if (Object.keys(errs).length) return
        try {
          await create.mutateAsync({ title: title.trim(), target_cents: target, target_date: date || null, notes: notes.trim() || null })
          toast.success('Meta criada.')
          onDone()
        } catch (err) {
          toast.error(readApiError(err).message)
        }
      }}
    >
      <Field label="Nome" error={errors.title}>
        {(p) => <Input {...p} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} maxLength={80} placeholder="Reserva de emergência" />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Valor da meta" error={errors.target}>
          {(p) => <MoneyInput {...p} valueCents={target} onChangeCents={setTarget} />}
        </Field>
        <Field label="Prazo (opcional)" hint="Calculamos quanto guardar por mês.">
          {(p) => <Input {...p} type="date" min={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
      </div>
      <Field label="Observações (opcional)">
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" loading={create.isPending}>
          Criar meta
        </Button>
      </div>
    </form>
  )
}

function AllocateDialog({ goal, onClose }: { goal: Goal | null; onClose: () => void }) {
  return (
    <Dialog
      open={!!goal}
      onOpenChange={(o) => !o && onClose()}
      title={goal ? `Aportar em ${goal.title}` : ''}
      description="Aporte não é despesa: o dinheiro continua seu."
    >
      {goal && <AllocateForm key={goal.id} goal={goal} onDone={onClose} />}
    </Dialog>
  )
}

function AllocateForm({ goal, onDone }: { goal: Goal; onDone: () => void }) {
  const accounts = useAccounts()
  const allocate = useAllocateGoal()
  const [key] = useState(newIdempotencyKey)
  const [withTransfer, setWithTransfer] = useState(true)
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState(todayISO())
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const active = (accounts.data ?? []).filter((a) => !a.archived_at)

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        const errs: Record<string, string> = {}
        if (!amount) errs.amount = 'Informe o valor.'
        if (withTransfer && !fromId) errs.from = 'Escolha a conta de origem.'
        if (withTransfer && !toId) errs.to = 'Escolha a conta da reserva.'
        if (withTransfer && fromId && fromId === toId) errs.to = 'Use contas diferentes.'
        setErrors(errs)
        if (Object.keys(errs).length) return
        try {
          await allocate.mutateAsync(
            withTransfer
              ? { id: goal.id, withTransfer, from_account_id: fromId, to_account_id: toId, amount_cents: amount, effective_date: date, idempotency_key: key }
              : { id: goal.id, withTransfer, amount_cents: amount, allocated_on: date, idempotency_key: key },
          )
          toast.success('Aporte registrado.')
          onDone()
        } catch (err) {
          toast.error(readApiError(err).message)
        }
      }}
    >
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tipo de aporte">
        {(
          [
            [true, 'Transferir entre contas', 'Move o dinheiro para a conta da reserva.'],
            [false, 'Só registrar', 'O dinheiro já está separado; só marca o progresso.'],
          ] as const
        ).map(([v, label, hint]) => (
          <button
            key={String(v)}
            type="button"
            role="radio"
            aria-checked={withTransfer === v}
            onClick={() => setWithTransfer(v)}
            className={cn('rounded-lg border p-3 text-left', withTransfer === v ? 'border-accent bg-accent-soft/40' : 'border-border hover:bg-surface-2')}
          >
            <span className="block text-sm font-medium">{label}</span>
            <span className="text-xs text-muted">{hint}</span>
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Valor" error={errors.amount} hint={`Faltam ${formatBRL(goal.remaining_cents)}`}>
          {(p) => <MoneyInput {...p} valueCents={amount} onChangeCents={setAmount} />}
        </Field>
        <Field label="Data">
          {(p) => <Input {...p} type="date" max={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
      </div>
      {withTransfer && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Sai de" error={errors.from}>
            {(p) => (
              <Select {...p} value={fromId} onChange={(e) => setFromId(e.target.value)}>
                <option value="">— Selecione —</option>
                {active.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {formatBRL(a.balance_cents)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Vai para (reserva)" error={errors.to}>
            {(p) => (
              <Select {...p} value={toId} onChange={(e) => setToId(e.target.value)}>
                <option value="">— Selecione —</option>
                {active.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" loading={allocate.isPending}>
          Confirmar aporte
        </Button>
      </div>
    </form>
  )
}

// =====================================================================
// Projeção
// =====================================================================

function ProjectionTab() {
  const [days, setDays] = useState<'30' | '60' | '90'>('30')
  const q = useProjection(Number(days) as 30 | 60 | 90)
  const d = q.data

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-xs text-muted">
          Compras no cartão entram só pelo pagamento da fatura, então nada é contado duas vezes. Valores vencidos e ainda em
          aberto entram hoje.
        </p>
        <Segmented
          label="Horizonte da projeção"
          layoutId="projection-days"
          value={days}
          onChange={setDays}
          options={[
            { value: '30', label: '30 dias' },
            { value: '60', label: '60 dias' },
            { value: '90', label: '90 dias' },
          ]}
        />
      </div>

      {q.isError ? (
        <Card>
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        </Card>
      ) : !d ? (
        <Skeleton className="h-96 rounded-2xl" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile icon={<Wallet />} label="Saldo hoje" cents={d.start_balance_cents} />
            <Tile icon={<TrendingDown />} label={`Em ${d.days} dias (base)`} cents={d.base.end_cents} tone={d.base.end_cents < 0 ? 'negative' : undefined} />
            <Tile label={`Em ${d.days} dias (conservador)`} cents={d.conservative.end_cents} tone={d.conservative.end_cents < 0 ? 'negative' : undefined} />
            <Tile
              icon={<AlertTriangle />}
              label={`Menor saldo · ${formatDate(d.conservative.lowest_date)}`}
              cents={d.conservative.lowest_cents}
              tone={d.conservative.lowest_cents < 0 ? 'negative' : 'warning'}
            />
          </div>
          <Card>
            <Suspense fallback={<Skeleton className="m-5 h-72" />}>
              <ProjectionChart data={d} />
            </Suspense>
          </Card>
          <Card>
            <CardHeader title="Entradas e saídas previstas" />
            <div className="grid grid-cols-2 gap-px border-t border-border bg-border text-sm">
              {(['base', 'conservative'] as const).map((s) => (
                <div key={s} className="bg-surface px-5 py-3">
                  <p className="text-xs text-muted">{s === 'base' ? 'Cenário base' : 'Cenário conservador'}</p>
                  <p className="mt-1">
                    <span className="text-positive">+{formatBRL(d[s].inflow_cents)}</span>
                    <span className="text-muted"> · </span>
                    <span className="text-negative">−{formatBRL(d[s].outflow_cents)}</span>
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

function Tile({ label, cents, icon, tone }: { label: string; cents: number; icon?: React.ReactNode; tone?: 'negative' | 'warning' }) {
  return (
    <Card className="p-4">
      <p className="flex items-center gap-1.5 text-[13px] text-muted [&_svg]:size-4">
        {icon}
        <span className="truncate">{label}</span>
      </p>
      <CurrencyDisplay
        cents={cents}
        className={cn('mt-2 block text-[22px] font-normal tracking-tight', tone === 'negative' && 'text-negative', tone === 'warning' && 'text-warning')}
      />
    </Card>
  )
}
