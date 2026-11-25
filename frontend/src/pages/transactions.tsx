import { ArrowLeftRight, ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuickAdd } from '@/app/layout'
import { CurrencyDisplay } from '@/components/finance/currency'
import { ExportButton } from '@/components/finance/export-button'
import { PeriodPicker, usePeriod } from '@/components/finance/period-picker'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton, TransactionList } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { useTransactionActions } from '@/features/transactions/actions'
import { useAccounts, useTransactions, type TxFilters } from '@/lib/queries'

type Group = NonNullable<TxFilters['group']>

export function TransactionsPage() {
  const [params, setParams] = useSearchParams()
  const period = usePeriod()
  const quickAdd = useQuickAdd()
  const actions = useTransactionActions()
  const accounts = useAccounts(true)

  const group = (params.get('group') as Group) ?? 'all'
  const status = params.get('status') ?? ''
  const accountId = params.get('account') ?? ''
  const page = Number(params.get('page') ?? 1)
  const [search, setSearch] = useState(params.get('q') ?? '')

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  // Busca com debounce para não disparar uma requisição por tecla.
  useEffect(() => {
    const id = setTimeout(() => {
      if ((params.get('q') ?? '') !== search) set('q', search)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  const filters: TxFilters = {
    from: period.from || undefined,
    to: period.to || undefined,
    group,
    status: status || undefined,
    account_id: accountId || undefined,
    q: params.get('q') || undefined,
    page,
  }
  const { data, isLoading, isError, refetch, isFetching } = useTransactions(filters)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1

  return (
    <div className="mx-auto max-w-[1100px] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented<Group>
          label="Tipo"
          layoutId="tx-group"
          value={group}
          onChange={(v) => set('group', v === 'all' ? '' : v)}
          options={[
            { value: 'all', label: 'Todas' },
            { value: 'income', label: 'Receitas' },
            { value: 'expense', label: 'Despesas' },
            { value: 'transfer', label: 'Transferências' },
          ]}
        />
        <ExportButton kind="transactions" from={period.from} to={period.to} />
        <Button variant="secondary" onClick={() => quickAdd(group === 'income' ? 'INCOME' : group === 'transfer' ? 'TRANSFER' : 'EXPENSE')}>
          <Plus /> Lançar
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <PeriodPicker period={period} allowAll />
        <div className="w-44">
          <Select aria-label="Situação" value={status} onChange={(e) => set('status', e.target.value)}>
            <option value="">Todas as situações</option>
            <option value="POSTED">Efetivados</option>
            <option value="PLANNED">Previstos</option>
            <option value="CANCELLED">Cancelados</option>
          </Select>
        </div>
        <div className="w-48">
          <Select aria-label="Conta" value={accountId} onChange={(e) => set('account', e.target.value)}>
            <option value="">Todas as contas</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="relative min-w-48 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input aria-label="Buscar" placeholder="Buscar descrição…" className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-border bg-border">
          <Total label="Receitas efetivadas" cents={data.totals.income_cents} />
          <Total label="Despesas efetivadas" cents={-data.totals.expense_cents} />
          <Total label="Resultado" cents={data.totals.net_cents} signed />
        </div>
      )}

      <Card className="overflow-hidden">
        {isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : isLoading || !data ? (
          <ListSkeleton rows={8} />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={<ArrowLeftRight />}
            title="Nenhum lançamento encontrado"
            description="Ajuste os filtros ou registre um novo lançamento."
            action={
              <Button size="sm" onClick={() => quickAdd()}>
                <Plus /> Novo lançamento
              </Button>
            }
          />
        ) : (
          <div className={isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
            <TransactionList items={data.items} onCancel={actions.onCancel} onPost={actions.onPost} />
          </div>
        )}
        {data && data.total > data.limit && (
          <div className="flex items-center justify-between border-t border-border px-5 py-3 text-sm">
            <span className="text-muted">
              {data.total} lançamentos · página {page} de {pages}
            </span>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon-sm" disabled={page <= 1} onClick={() => set('page', String(page - 1))} aria-label="Página anterior">
                <ChevronLeft />
              </Button>
              <Button variant="ghost" size="icon-sm" disabled={page >= pages} onClick={() => set('page', String(page + 1))} aria-label="Próxima página">
                <ChevronRight />
              </Button>
            </div>
          </div>
        )}
      </Card>
      <p className="text-xs text-muted">Totais consideram exatamente os filtros acima; previstos e cancelados não somam. Transferências não são receita nem despesa.</p>
      {actions.dialog}
    </div>
  )
}

function Total({ label, cents, signed }: { label: string; cents: number; signed?: boolean }) {
  return (
    <div className="bg-surface px-4 py-3">
      <p className="text-[11px] text-muted sm:text-xs">{label}</p>
      <CurrencyDisplay cents={cents} signed={signed} tone className="text-sm font-semibold sm:text-base" />
    </div>
  )
}
