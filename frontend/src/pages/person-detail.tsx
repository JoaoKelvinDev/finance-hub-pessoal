import { ArrowLeft, Info, Plus, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/misc'
import { PartyBalanceList } from '@/features/parties/balance-list'
import { NewPartyBalanceDialog } from '@/features/parties/dialogs'
import { formatDate } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import { usePersonPosition } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { PartyBalanceDetail } from '@/types/api'

export function PersonDetailPage() {
  const { id = '' } = useParams()
  const q = usePersonPosition(id)
  const [newOpen, setNewOpen] = useState(false)
  const data = q.data

  const { open, closed, details, upcoming } = useMemo(() => {
    const balances = data?.balances ?? []
    const details: Record<string, PartyBalanceDetail> = Object.fromEntries(balances.map((b) => [b.id, b]))
    const open = balances.filter((b) => b.status !== 'SETTLED' && b.status !== 'CANCELLED')
    const closed = balances.filter((b) => b.status === 'SETTLED' || b.status === 'CANCELLED')
    const upcoming = open.filter((b) => b.due_date).sort((a, b) => a.due_date!.localeCompare(b.due_date!)).slice(0, 3)
    return { open, closed, details, upcoming }
  }, [data])

  if (q.isError) {
    return (
      <Card>
        <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
      </Card>
    )
  }

  return (
    <div className="mx-auto max-w-[1000px] space-y-5">
      <Link to="/pessoas" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
        <ArrowLeft className="size-4" /> Pessoas
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-12 place-items-center rounded-full bg-accent-soft text-lg font-semibold text-accent" aria-hidden>
            {data?.person_name.slice(0, 1).toUpperCase() ?? '…'}
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{data?.person_name ?? 'Carregando…'}</h1>
            <p className="text-sm text-muted">
              {data?.contact ?? 'Contato financeiro'}
              {data?.archived && ' · arquivado'}
            </p>
          </div>
        </div>
        {data && !data.archived && (
          <Button onClick={() => setNewOpen(true)}>
            <Plus /> Novo registro
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Tile label="Me deve" cents={data?.summary.receivable_open_cents} tone="text-positive" />
        <Tile label="Eu devo" cents={data?.summary.payable_open_cents} tone="text-warning" />
        <Tile
          label="Saldo líquido"
          cents={data?.net_cents}
          info="Apenas informativo. Dívidas em sentidos opostos não são compensadas automaticamente."
          tone={data && data.net_cents < 0 ? 'text-warning' : 'text-fg'}
        />
      </div>

      {upcoming.length > 0 && (
        <Card>
          <CardHeader title="Próximos vencimentos" />
          <ul className="divide-y divide-border border-t border-border">
            {upcoming.map((b) => (
              <li key={b.id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
                <span className={cn('w-24 shrink-0 tabular-nums', b.status === 'OVERDUE' ? 'font-medium text-negative' : 'text-muted')}>
                  {formatDate(b.due_date!)}
                </span>
                <span className="min-w-0 flex-1 truncate">{b.description}</span>
                <span className="shrink-0 text-xs text-muted">{b.direction === 'RECEIVABLE' ? 'a receber' : 'a pagar'}</span>
                <span className="shrink-0 font-semibold tabular-nums">{formatBRL(b.open_cents)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="overflow-hidden">
        <CardHeader title="Em aberto" description={`${open.length} ${open.length === 1 ? 'registro' : 'registros'}`} />
        <div className="border-t border-border">
          {q.isPending ? (
            <ListSkeleton rows={2} />
          ) : open.length === 0 ? (
            <EmptyState icon={<Users />} title="Tudo acertado" description="Não há valores em aberto com esta pessoa." />
          ) : (
            <PartyBalanceList items={open} showPerson={false} details={details} />
          )}
        </div>
      </Card>

      {closed.length > 0 && (
        <Card className="overflow-hidden">
          <CardHeader title="Histórico" description="Quitados e cancelados." />
          <div className="border-t border-border">
            <PartyBalanceList items={closed} showPerson={false} details={details} />
          </div>
        </Card>
      )}

      <NewPartyBalanceDialog open={newOpen} onOpenChange={setNewOpen} defaultPersonId={id} />
    </div>
  )
}

function Tile({ label, cents, tone, info }: { label: string; cents?: number; tone: string; info?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <span className="flex items-center gap-1.5 text-[13px] font-medium text-muted">
        {label}
        {info && (
          <Tooltip content={info}>
            <span role="img" tabIndex={0} aria-label={info} className="text-muted/70 hover:text-fg">
              <Info className="size-3.5" />
            </span>
          </Tooltip>
        )}
      </span>
      {cents === undefined ? (
        <div className="shimmer mt-3 h-7 w-28 rounded-md" />
      ) : (
        <CurrencyDisplay cents={cents} className={cn('mt-2 block text-[22px] font-semibold tracking-tight', tone)} />
      )}
    </div>
  )
}
