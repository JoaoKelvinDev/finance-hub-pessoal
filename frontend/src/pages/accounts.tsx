import { zodResolver } from '@hookform/resolvers/zod'
import { motion } from 'motion/react'
import { Archive, ArchiveRestore, ArrowLeft, ChevronLeft, ChevronRight, Landmark, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'
import { CurrencyDisplay, MoneyInput } from '@/components/finance/currency'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton, TransactionList } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { useTransactionActions } from '@/features/transactions/actions'
import { ApiError } from '@/lib/api'
import { formatDate, todayISO } from '@/lib/date'
import { riseItem, staggerContainer } from '@/lib/motion'
import { useAccounts, useCreateAccount, useLedger, useUpdateAccount } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { Account, AccountType } from '@/types/api'

const TYPE_LABEL: Record<AccountType, string> = {
  CHECKING: 'Conta corrente',
  SAVINGS: 'Poupança',
  CASH: 'Dinheiro',
  DIGITAL_WALLET: 'Carteira digital',
  OTHER: 'Outra',
}

const COLORS = ['#2A78D6', '#1BAF7A', '#EB6834', '#EDA100', '#E87BA4', '#6250D6', '#52514E']

export function AccountsPage() {
  const [params, setParams] = useSearchParams()
  const [showArchived, setShowArchived] = useState(false)
  const { data, isLoading, isError, refetch } = useAccounts(true)
  const [open, setOpen] = useState(params.get('nova') === '1')
  const update = useUpdateAccount()

  const visible = data?.filter((a) => showArchived || !a.archived_at) ?? []
  const total = data?.filter((a) => !a.archived_at).reduce((s, a) => s + a.balance_cents, 0) ?? 0

  const toggleArchive = async (a: Account) => {
    try {
      await update.mutateAsync({ id: a.id, archived: !a.archived_at })
      toast.success(a.archived_at ? `“${a.name}” reativada.` : `“${a.name}” arquivada. O histórico foi preservado.`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Não foi possível atualizar.')
    }
  }

  return (
    <div className="mx-auto max-w-[1100px] space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted">Saldo consolidado das contas ativas</p>
          {data ? <CurrencyDisplay cents={total} className="text-3xl font-semibold tracking-tight" /> : <Skeleton className="mt-1 h-9 w-48" />}
        </div>
        <div className="flex items-center gap-2">
          <Segmented
            label="Exibir"
            layoutId="acc-archived"
            value={showArchived ? 'all' : 'active'}
            onChange={(v) => setShowArchived(v === 'all')}
            options={[
              { value: 'active', label: 'Ativas' },
              { value: 'all', label: 'Todas' },
            ]}
          />
          <Button onClick={() => setOpen(true)}>
            <Plus /> Nova conta
          </Button>
        </div>
      </div>

      {isError ? (
        <Card>
          <ErrorState onRetry={() => refetch()} />
        </Card>
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Landmark />}
            title="Nenhuma conta cadastrada"
            description="Cadastre conta corrente, poupança, dinheiro ou carteira digital com o saldo de hoje."
            action={
              <Button size="sm" onClick={() => setOpen(true)}>
                <Plus /> Cadastrar conta
              </Button>
            }
          />
        </Card>
      ) : (
        <motion.ul variants={staggerContainer} initial="initial" animate="enter" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((a) => (
            <motion.li key={a.id} variants={riseItem} layout>
              <Card className={cn('group relative flex h-full flex-col overflow-hidden', a.archived_at && 'opacity-60')}>
                <span className="absolute inset-x-0 top-0 h-1" style={{ background: a.color }} aria-hidden />
                <Link to={`/contas/${a.id}`} className="flex-1 p-5 pt-6 transition-colors hover:bg-surface-2/50">
                  <p className="text-xs text-muted">
                    {TYPE_LABEL[a.type]}
                    {a.institution && ` · ${a.institution}`}
                    {a.archived_at && ' · Arquivada'}
                  </p>
                  <p className="mt-1 font-semibold">{a.name}</p>
                  <CurrencyDisplay cents={a.balance_cents} className="mt-4 block text-2xl font-semibold tracking-tight" />
                  {a.planned_balance_cents !== a.balance_cents && (
                    <p className="mt-1 text-xs text-muted">
                      Com previstos: <CurrencyDisplay cents={a.planned_balance_cents} animated={false} />
                    </p>
                  )}
                </Link>
                <div className="flex justify-end border-t border-border px-3 py-2">
                  <Button variant="ghost" size="sm" onClick={() => toggleArchive(a)}>
                    {a.archived_at ? <ArchiveRestore /> : <Archive />}
                    {a.archived_at ? 'Reativar' : 'Arquivar'}
                  </Button>
                </div>
              </Card>
            </motion.li>
          ))}
        </motion.ul>
      )}

      <AccountDialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o)
          if (!o && params.get('nova')) {
            params.delete('nova')
            setParams(params, { replace: true })
          }
        }}
      />
    </div>
  )
}

const accountSchema = z.object({
  name: z.string().trim().min(1, 'Dê um nome à conta.').max(80),
  type: z.enum(['CHECKING', 'SAVINGS', 'CASH', 'DIGITAL_WALLET', 'OTHER']),
  institution: z.string().trim().max(80),
  opening_balance_cents: z.number().int().nullable(),
  negative: z.boolean(),
  opening_date: z.string().min(10, 'Informe a data.'),
  color: z.string(),
})

function AccountDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateAccount()
  const form = useForm<z.infer<typeof accountSchema>>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      name: '',
      type: 'CHECKING',
      institution: '',
      opening_balance_cents: null,
      negative: false,
      opening_date: todayISO(),
      color: COLORS[0],
    },
  })
  const { register, control, handleSubmit, formState, reset, watch, setValue } = form

  useEffect(() => {
    if (open) reset()
  }, [open, reset])

  const onSubmit = handleSubmit(async (v) => {
    const cents = (v.opening_balance_cents ?? 0) * (v.negative ? -1 : 1)
    try {
      await create.mutateAsync({
        name: v.name,
        type: v.type,
        institution: v.institution || null,
        opening_balance_cents: cents,
        opening_date: v.opening_date,
        color: v.color,
      })
      toast.success(`Conta “${v.name}” criada.`)
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Não foi possível criar a conta.')
    }
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Nova conta" description="O saldo inicial é o valor na data informada; lançamentos anteriores já estão nele.">
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome" error={formState.errors.name?.message}>
            {(p) => <Input {...p} autoFocus placeholder="Ex.: Nubank" {...register('name')} />}
          </Field>
          <Field label="Tipo">
            {(p) => (
              <Select {...p} {...register('type')}>
                {Object.entries(TYPE_LABEL).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Field label="Instituição (opcional)">{(p) => <Input {...p} {...register('institution')} />}</Field>
        <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
          <Field label="Saldo inicial">
            {(p) => (
              <Controller
                control={control}
                name="opening_balance_cents"
                render={({ field }) => <MoneyInput {...p} valueCents={field.value} onChangeCents={field.onChange} />}
              />
            )}
          </Field>
          <Field label="Data do saldo" error={formState.errors.opening_date?.message}>
            {(p) => <Input {...p} type="date" max={todayISO()} {...register('opening_date')} />}
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted">
          <input type="checkbox" className="size-4 accent-[var(--accent)]" {...register('negative')} />
          Saldo inicial negativo (conta no cheque especial)
        </label>
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Cor</legend>
          <div className="flex gap-2">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setValue('color', c)}
                aria-label={`Cor ${c}`}
                aria-pressed={watch('color') === c}
                className={cn(
                  'size-8 rounded-full ring-offset-2 ring-offset-surface transition-[box-shadow,transform] hover:scale-110',
                  watch('color') === c && 'ring-2 ring-fg',
                )}
                style={{ background: c }}
              />
            ))}
          </div>
        </fieldset>
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={formState.isSubmitting}>
            Criar conta
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export function AccountDetailPage() {
  const { id = '' } = useParams()
  const [page, setPage] = useState(1)
  const { data, isLoading, isError, refetch, isFetching } = useLedger(id, page)
  const actions = useTransactionActions()
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1

  return (
    <div className="mx-auto max-w-[1000px] space-y-5">
      <Link to="/contas" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" /> Contas e carteiras
      </Link>
      {isError ? (
        <Card>
          <ErrorState message="Conta não encontrada ou indisponível." onRetry={() => refetch()} />
        </Card>
      ) : (
        <>
          <Card className="relative overflow-hidden">
            {data && <span className="absolute inset-y-0 left-0 w-1" style={{ background: data.account.color }} aria-hidden />}
            <div className="grid gap-4 p-5 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted">{data ? TYPE_LABEL[data.account.type] : ' '}</p>
                {data ? <p className="text-lg font-semibold">{data.account.name}</p> : <Skeleton className="mt-1 h-6 w-40" />}
              </div>
              <div>
                <p className="text-xs text-muted">Saldo atual</p>
                {data ? (
                  <CurrencyDisplay cents={data.account.balance_cents} className="text-2xl font-semibold" />
                ) : (
                  <Skeleton className="mt-1 h-7 w-32" />
                )}
              </div>
              <div>
                <p className="text-xs text-muted">Saldo inicial</p>
                {data && (
                  <p className="text-sm">
                    <CurrencyDisplay cents={data.account.opening_balance_cents} animated={false} /> em{' '}
                    {formatDate(data.account.opening_date)}
                  </p>
                )}
              </div>
            </div>
          </Card>
          <Card className="overflow-hidden">
            <CardHeader title="Extrato" description="Inclui previstos e cancelados para histórico completo." />
            {isLoading || !data ? (
              <ListSkeleton />
            ) : data.items.length ? (
              <div className={isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
                <TransactionList items={data.items} onCancel={actions.onCancel} onPost={actions.onPost} />
              </div>
            ) : (
              <EmptyState icon={<Landmark />} title="Sem lançamentos" description="Os lançamentos desta conta aparecerão aqui." />
            )}
            {data && data.total > data.limit && (
              <div className="flex items-center justify-between border-t border-border px-5 py-3 text-sm">
                <span className="text-muted">
                  Página {page} de {pages}
                </span>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon-sm" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Página anterior">
                    <ChevronLeft />
                  </Button>
                  <Button variant="ghost" size="icon-sm" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Próxima página">
                    <ChevronRight />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
      {actions.dialog}
    </div>
  )
}
