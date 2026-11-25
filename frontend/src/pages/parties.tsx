import { motion } from 'motion/react'
import { AlertTriangle, ArrowDownLeft, ArrowUpRight, HandCoins, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Segmented } from '@/components/ui/misc'
import { PartyBalanceList } from '@/features/parties/balance-list'
import { NewPartyBalanceDialog } from '@/features/parties/dialogs'
import { formatBRL } from '@/lib/money'
import { listItem, staggerContainer } from '@/lib/motion'
import { usePartyBalances } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { PartyBalance } from '@/types/api'

type Tab = 'RECEIVABLE' | 'PAYABLE' | 'SETTLED'

export function PartiesPage() {
  const [tab, setTab] = useState<Tab>('RECEIVABLE')
  const [newOpen, setNewOpen] = useState(false)
  const q = usePartyBalances()
  const items = useMemo(() => q.data?.items ?? [], [q.data])
  const summary = q.data?.summary

  const visible = useMemo(() => {
    if (tab === 'SETTLED') return items.filter((b) => b.status === 'SETTLED')
    return items.filter((b) => b.direction === tab && b.status !== 'SETTLED')
  }, [items, tab])

  const groups = useMemo(() => {
    const map = new Map<string, { name: string; open: number; items: PartyBalance[] }>()
    for (const b of visible) {
      const g = map.get(b.person_id) ?? { name: b.person_name, open: 0, items: [] }
      g.open += b.open_cents
      g.items.push(b)
      map.set(b.person_id, g)
    }
    return [...map.entries()].sort((a, b) => b[1].open - a[1].open)
  }, [visible])

  const counts = {
    RECEIVABLE: items.filter((b) => b.direction === 'RECEIVABLE' && b.status !== 'SETTLED').length,
    PAYABLE: items.filter((b) => b.direction === 'PAYABLE' && b.status !== 'SETTLED').length,
    SETTLED: items.filter((b) => b.status === 'SETTLED').length,
  }

  return (
    <div className="mx-auto max-w-[1100px] space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Valores com terceiros</h1>
          <p className="mt-0.5 text-muted">
            Empréstimos, adiantamentos e dívidas com seus contatos. Nada aqui conta como receita ou despesa.
          </p>
        </div>
        <Button onClick={() => setNewOpen(true)}>
          <Plus /> Novo registro
        </Button>
      </div>

      <motion.div variants={staggerContainer} initial="initial" animate="enter" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryTile
          label="Me devem"
          icon={<ArrowDownLeft />}
          cents={summary?.receivable_open_cents}
          cls="bg-positive-soft text-positive"
        />
        <SummaryTile label="Eu devo" icon={<ArrowUpRight />} cents={summary?.payable_open_cents} cls="bg-warning-soft text-warning" />
        <SummaryTile
          label="Vencidos"
          icon={<AlertTriangle />}
          cents={summary ? summary.receivable_overdue_cents + summary.payable_overdue_cents : undefined}
          cls={
            summary && summary.receivable_overdue_cents + summary.payable_overdue_cents > 0
              ? 'bg-negative-soft text-negative'
              : 'bg-surface-2 text-muted'
          }
          hint={
            summary && summary.receivable_overdue_cents + summary.payable_overdue_cents > 0
              ? `${formatBRL(summary.receivable_overdue_cents)} a receber · ${formatBRL(summary.payable_overdue_cents)} a pagar`
              : undefined
          }
        />
      </motion.div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <Segmented
            label="Filtrar registros"
            layoutId="parties-tab"
            value={tab}
            onChange={setTab}
            options={[
              { value: 'RECEIVABLE', label: `A receber (${counts.RECEIVABLE})` },
              { value: 'PAYABLE', label: `A pagar (${counts.PAYABLE})` },
              { value: 'SETTLED', label: `Quitados (${counts.SETTLED})` },
            ]}
          />
        </div>

        {q.isError ? (
          <ErrorState message={q.error.message} onRetry={() => q.refetch()} />
        ) : q.isPending ? (
          <ListSkeleton rows={4} />
        ) : groups.length === 0 ? (
          <EmptyState
            icon={<HandCoins />}
            title={tab === 'SETTLED' ? 'Nada quitado ainda' : tab === 'RECEIVABLE' ? 'Ninguém te deve' : 'Você não deve a ninguém'}
            description={
              tab === 'SETTLED'
                ? 'Registros totalmente acertados aparecem aqui.'
                : 'Registre um empréstimo, adiantamento ou dívida com um contato.'
            }
            action={
              tab !== 'SETTLED' && (
                <Button size="sm" onClick={() => setNewOpen(true)}>
                  <Plus /> Novo registro
                </Button>
              )
            }
          />
        ) : (
          <div className="divide-y divide-border">
            {groups.map(([personId, g]) => (
              <section key={personId} aria-label={g.name}>
                <header className="flex items-center gap-3 bg-surface-2/40 px-5 py-2">
                  <span className="grid size-7 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent" aria-hidden>
                    {g.name.slice(0, 1).toUpperCase()}
                  </span>
                  <Link to={`/pessoas/${personId}`} className="min-w-0 flex-1 truncate text-sm font-semibold hover:underline">
                    {g.name}
                  </Link>
                  {tab !== 'SETTLED' && (
                    <span className="text-sm font-semibold tabular-nums">{formatBRL(g.open)}</span>
                  )}
                </header>
                <PartyBalanceList items={g.items} showPerson={false} />
              </section>
            ))}
          </div>
        )}
      </Card>

      <NewPartyBalanceDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  )
}

function SummaryTile({
  label,
  icon,
  cents,
  cls,
  hint,
}: {
  label: string
  icon: React.ReactNode
  cents?: number
  cls: string
  hint?: string
}) {
  return (
    <motion.div variants={listItem} className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <span className="flex items-center gap-2 text-[13px] font-medium text-muted">
        <span className={cn('grid size-7 place-items-center rounded-lg [&_svg]:size-4', cls)} aria-hidden>
          {icon}
        </span>
        {label}
      </span>
      {cents === undefined ? (
        <div className="shimmer mt-3 h-7 w-28 rounded-md" />
      ) : (
        <CurrencyDisplay cents={cents} className="mt-3 block text-[22px] font-semibold tracking-tight" />
      )}
      <p className="mt-1 h-4 truncate text-xs text-muted">{hint}</p>
    </motion.div>
  )
}
