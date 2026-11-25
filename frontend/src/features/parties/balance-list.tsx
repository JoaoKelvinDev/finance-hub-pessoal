import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, HandCoins, Handshake, Percent, Undo2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { CurrencyDisplay } from '@/components/finance/currency'
import { Button } from '@/components/ui/button'
import { daysBetween, formatDate, todayISO } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import { listItem } from '@/lib/motion'
import { useCancelPartyBalance, usePartyBalance, useReversePartySettlement } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { PartyBalance, PartyBalanceDetail } from '@/types/api'
import { AdjustDialog, ReasonDialog, SettleDialog } from './dialogs'
import { ORIGINS, PARTY_STATUS } from './meta'

/** Lista de registros com ações: acertar, juros/desconto, histórico, estorno e cancelamento. */
export function PartyBalanceList({
  items,
  showPerson = true,
  details,
}: {
  items: PartyBalance[]
  showPerson?: boolean
  /** Detalhes já carregados (tela da pessoa) — evita uma requisição por item. */
  details?: Record<string, PartyBalanceDetail>
}) {
  const [settling, setSettling] = useState<PartyBalance | null>(null)
  const [adjusting, setAdjusting] = useState<PartyBalance | null>(null)
  const [cancelling, setCancelling] = useState<PartyBalance | null>(null)
  const cancel = useCancelPartyBalance()

  return (
    <>
      <ul className="divide-y divide-border">
        <AnimatePresence initial={false}>
          {items.map((b) => (
            <motion.li key={b.id} layout="position" variants={listItem} initial="initial" animate="enter" exit="exit">
              <BalanceRow
                balance={b}
                showPerson={showPerson}
                preloaded={details?.[b.id]}
                onSettle={() => setSettling(b)}
                onAdjust={() => setAdjusting(b)}
                onCancel={() => setCancelling(b)}
              />
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>

      <SettleDialog balance={settling} onClose={() => setSettling(null)} />
      <AdjustDialog balance={adjusting} onClose={() => setAdjusting(null)} />
      <ReasonDialog
        open={!!cancelling}
        title="Cancelar registro"
        description={
          cancelling?.origin_transaction_id
            ? 'O lançamento de origem também será cancelado e o saldo da conta volta ao que era. O histórico é preservado.'
            : 'O registro sai dos totais, mas o histórico é preservado.'
        }
        confirmLabel="Cancelar registro"
        pending={cancel.isPending}
        onClose={() => setCancelling(null)}
        onConfirm={async (reason) => {
          await cancel.mutateAsync({ id: cancelling!.id, reason })
          toast.success('Registro cancelado.')
          setCancelling(null)
        }}
      />
    </>
  )
}

function BalanceRow({
  balance: b,
  showPerson,
  preloaded,
  onSettle,
  onAdjust,
  onCancel,
}: {
  balance: PartyBalance
  showPerson: boolean
  preloaded?: PartyBalanceDetail
  onSettle: () => void
  onAdjust: () => void
  onCancel: () => void
}) {
  const [open, setOpen] = useState(false)
  const status = PARTY_STATUS[b.status]
  const StatusIcon = status.icon
  const receivable = b.direction === 'RECEIVABLE'
  const active = b.status !== 'CANCELLED' && b.status !== 'SETTLED'
  const total = b.principal_cents + b.charges_cents - b.discounts_cents
  const progress = total > 0 ? Math.min(100, Math.round(((total - b.open_cents) / total) * 100)) : 0
  const daysLate = b.status === 'OVERDUE' && b.due_date ? daysBetween(b.due_date, todayISO()) : 0

  return (
    <div className={cn('px-5 py-3.5', b.status === 'CANCELLED' && 'opacity-60')}>
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'grid size-9 shrink-0 place-items-center rounded-xl',
            receivable ? 'bg-positive-soft text-positive' : 'bg-warning-soft text-warning',
          )}
          aria-hidden
        >
          <HandCoins className="size-4" />
        </span>

        <div className="min-w-0 flex-1">
          <p className={cn('truncate text-sm font-medium', b.status === 'CANCELLED' && 'line-through')}>
            {showPerson && (
              <>
                <Link to={`/pessoas/${b.person_id}`} className="hover:underline">
                  {b.person_name}
                </Link>
                <span className="text-muted"> · </span>
              </>
            )}
            {b.description}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span className={cn('inline-flex items-center gap-1 rounded-full px-1.5 py-px font-medium', status.cls)}>
              <StatusIcon className="size-3" aria-hidden />
              {status.label}
              {daysLate > 0 && ` há ${daysLate} ${daysLate === 1 ? 'dia' : 'dias'}`}
            </span>
            <span>{b.from_split ? 'Rateio de conta da casa' : ORIGINS[b.origin_type].short}</span>
            <span aria-hidden>·</span>
            <span className="num">{formatDate(b.operation_date)}</span>
            {b.due_date && (
              <span className="num">
                · vence {formatDate(b.due_date)}
              </span>
            )}
          </p>
        </div>

        <div className="shrink-0 text-right">
          <span className="block text-[11px] text-muted">{receivable ? 'A receber' : 'A pagar'}</span>
          <CurrencyDisplay
            cents={b.open_cents}
            animated={false}
            className={cn('text-sm font-semibold', b.open_cents === 0 && 'text-muted')}
          />
          {b.open_cents !== total && b.status !== 'CANCELLED' && (
            <span className="block text-[11px] text-muted tabular-nums">de {formatBRL(total)}</span>
          )}
        </div>
      </div>

      {active && total > 0 && progress > 0 && (
        <div className="mt-2 ml-12 h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
          <div className="h-full rounded-full bg-positive transition-[width]" style={{ width: `${progress}%` }} />
        </div>
      )}

      <div className="mt-2 ml-12 flex flex-wrap items-center gap-1.5">
        {active && (
          <>
            <Button size="sm" onClick={onSettle}>
              <Handshake /> {receivable ? 'Registrar recebimento' : 'Registrar pagamento'}
            </Button>
            <Button size="sm" variant="secondary" onClick={onAdjust}>
              <Percent /> Juros/desconto
            </Button>
          </>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <ChevronDown className={cn('transition-transform', open && 'rotate-180')} /> Histórico
        </Button>
        {b.status !== 'CANCELLED' && b.settled_cents === 0 && !b.from_split && (
          <Button size="sm" variant="ghost" className="text-negative hover:bg-negative-soft hover:text-negative" onClick={onCancel}>
            <XCircle /> Cancelar
          </Button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <History balanceId={b.id} preloaded={preloaded} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function History({ balanceId, preloaded }: { balanceId: string; preloaded?: PartyBalanceDetail }) {
  const q = usePartyBalance(preloaded ? null : balanceId)
  const d = preloaded ?? q.data
  const reverse = useReversePartySettlement()
  const [reversing, setReversing] = useState<string | null>(null)

  if (!d) return <div className="mt-3 ml-12 h-16 shimmer rounded-lg" />

  type Entry = { key: string; date: string; label: string; cents: number; tone: string; muted?: boolean; action?: () => void }
  const entries: Entry[] = [
    {
      key: 'origin',
      date: d.operation_date,
      label: `${ORIGINS[d.origin_type].short}${d.account_name ? ` · ${d.account_name}` : ''}`,
      cents: d.principal_cents,
      tone: '',
    },
    ...d.adjustments.map((a) => ({
      key: a.id,
      date: a.applied_on,
      label: `${a.kind === 'CHARGE' ? 'Juros/multa' : 'Desconto'} · ${a.reason}`,
      cents: a.kind === 'CHARGE' ? a.amount_cents : -a.amount_cents,
      tone: a.kind === 'CHARGE' ? 'text-warning' : 'text-positive',
    })),
    ...d.settlements.map((s) => ({
      key: s.id,
      date: s.settled_on,
      label: `${d.direction === 'RECEIVABLE' ? 'Recebido' : 'Pago'} · ${s.account_name}${s.reversed_at ? ` · estornado (${s.reverse_reason})` : ''}`,
      cents: -s.amount_cents,
      tone: 'text-positive',
      muted: !!s.reversed_at,
      action: s.reversed_at || d.status === 'CANCELLED' ? undefined : () => setReversing(s.id),
    })),
  ].sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div className="mt-3 ml-12 rounded-lg border border-border">
      <ol className="divide-y divide-border text-xs">
        {entries.map((e) => (
          <li key={e.key} className={cn('flex items-center gap-3 px-3 py-2', e.muted && 'text-muted line-through')}>
            <span className="w-20 shrink-0 text-muted tabular-nums">{formatDate(e.date)}</span>
            <span className="min-w-0 flex-1 truncate">{e.label}</span>
            <span className={cn('shrink-0 font-medium tabular-nums', !e.muted && e.tone)}>
              {e.cents > 0 && e.key !== 'origin' ? '+' : ''}
              {formatBRL(e.cents)}
            </span>
            {e.action && (
              <Button size="icon-sm" variant="ghost" onClick={e.action} aria-label="Estornar acerto">
                <Undo2 />
              </Button>
            )}
          </li>
        ))}
      </ol>
      {d.cancel_reason && <p className="border-t border-border px-3 py-2 text-xs text-muted">Cancelado: {d.cancel_reason}</p>}
      {d.notes && <p className="border-t border-border px-3 py-2 text-xs text-muted">{d.notes}</p>}

      <ReasonDialog
        open={!!reversing}
        title="Estornar acerto"
        description="O lançamento do acerto será cancelado e o valor volta para o saldo em aberto."
        confirmLabel="Estornar"
        pending={reverse.isPending}
        onClose={() => setReversing(null)}
        onConfirm={async (reason) => {
          await reverse.mutateAsync({ settlementId: reversing!, reason })
          toast.success('Acerto estornado.')
          setReversing(null)
        }}
      />
    </div>
  )
}
