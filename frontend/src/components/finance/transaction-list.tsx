import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  Check,
  HandCoins,
  Handshake,
  MoreHorizontal,
  Scale,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { DropdownMenu } from 'radix-ui'
import { CurrencyDisplay } from '@/components/finance/currency'
import { StatusBadge } from '@/components/finance/states'
import { formatDate, todayISO } from '@/lib/date'
import { listItem } from '@/lib/motion'
import { cn } from '@/lib/utils'
import type { Transaction, TxKind } from '@/types/api'

const KIND_ICON: Record<TxKind, LucideIcon> = {
  INCOME: ArrowDownLeft,
  EXPENSE: ArrowUpRight,
  TRANSFER_IN: ArrowLeftRight,
  TRANSFER_OUT: ArrowLeftRight,
  ADJUSTMENT: Scale,
  LOAN_OUT: HandCoins,
  LOAN_IN: HandCoins,
  SETTLEMENT_IN: Handshake,
  SETTLEMENT_OUT: Handshake,
}

const KIND_LABEL: Record<TxKind, string> = {
  INCOME: 'Receita',
  EXPENSE: 'Despesa',
  TRANSFER_IN: 'Transferência recebida',
  TRANSFER_OUT: 'Transferência enviada',
  ADJUSTMENT: 'Ajuste',
  LOAN_OUT: 'Empréstimo/adiantamento concedido',
  LOAN_IN: 'Empréstimo recebido',
  SETTLEMENT_IN: 'Acerto recebido de terceiro',
  SETTLEMENT_OUT: 'Acerto pago a terceiro',
}

/** Movimentos que não são receita nem despesa: exibidos em tom neutro. */
const NEUTRAL_KINDS: TxKind[] = [
  'TRANSFER_IN', 'TRANSFER_OUT', 'ADJUSTMENT', 'LOAN_OUT', 'LOAN_IN', 'SETTLEMENT_IN', 'SETTLEMENT_OUT',
]
const PARTY_KINDS: TxKind[] = ['LOAN_OUT', 'LOAN_IN', 'SETTLEMENT_IN', 'SETTLEMENT_OUT']

interface Props {
  items: Transaction[]
  onCancel?: (t: Transaction) => void
  onPost?: (t: Transaction) => void
  compact?: boolean
}

/** Lista responsiva: linhas tipo tabela no desktop, cartões no celular. */
export function TransactionList({ items, onCancel, onPost, compact }: Props) {
  const today = todayISO()
  return (
    <ul className="divide-y divide-border" aria-label="Lançamentos">
      <AnimatePresence initial={false}>
        {items.map((t) => {
          const Icon = KIND_ICON[t.kind]
          const overdue = t.status === 'PLANNED' && t.effective_date < today
          const transfer = t.kind === 'TRANSFER_IN' || t.kind === 'TRANSFER_OUT'
          const neutral = NEUTRAL_KINDS.includes(t.kind)
          // Lançamentos de terceiros são desfeitos pela tela de terceiros (o backend recusa aqui).
          const managed = PARTY_KINDS.includes(t.kind)
          return (
            <motion.li
              key={t.id}
              layout="position"
              variants={listItem}
              initial="initial"
              animate="enter"
              exit="exit"
              className={cn(
                'group flex items-center gap-3 px-5 py-3 hover:bg-surface-2/60',
                t.status === 'CANCELLED' && 'opacity-60',
              )}
            >
              <span
                className={cn(
                  'grid size-9 shrink-0 place-items-center rounded-xl',
                  t.kind === 'INCOME' && 'bg-positive-soft text-positive',
                  t.kind === 'EXPENSE' && 'bg-negative-soft text-negative',
                  neutral && 'bg-surface-2 text-muted',
                )}
                title={KIND_LABEL[t.kind]}
              >
                <Icon className="size-4" aria-hidden />
                <span className="sr-only">{KIND_LABEL[t.kind]}</span>
              </span>

              <div className="min-w-0 flex-1">
                <p className={cn('truncate text-sm font-medium', t.status === 'CANCELLED' && 'line-through')}>
                  {t.description}
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                  <span className="num">{formatDate(t.effective_date)}</span>
                  <span aria-hidden>·</span>
                  <span className="truncate">{t.account_name}</span>
                  {t.category_name && !compact && (
                    <span className="inline-flex items-center gap-1">
                      <span className="size-2 rounded-full" style={{ background: t.category_color ?? undefined }} aria-hidden />
                      {t.category_name}
                    </span>
                  )}
                  {t.counterparty_name && !compact && <span>· {t.counterparty_name}</span>}
                  {t.status !== 'POSTED' && <StatusBadge status={t.status} overdue={overdue} />}
                </p>
              </div>

              <CurrencyDisplay
                cents={t.amount_cents}
                signed
                tone={!neutral}
                animated={false}
                className={cn('shrink-0 text-sm font-semibold', neutral && 'text-muted')}
              />

              {(onCancel || onPost) && t.status !== 'CANCELLED' && !managed && (
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger
                    className="grid size-8 shrink-0 place-items-center rounded-lg text-muted opacity-100 hover:bg-surface-2 hover:text-fg sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100"
                    aria-label={`Ações para ${t.description}`}
                  >
                    <MoreHorizontal className="size-4" />
                  </DropdownMenu.Trigger>
                  <DropdownMenu.Portal>
                    <DropdownMenu.Content
                      align="end"
                      sideOffset={4}
                      className="z-50 min-w-44 rounded-xl border border-border bg-surface p-1 shadow-pop"
                    >
                      {onPost && t.status === 'PLANNED' && (
                        <DropdownMenu.Item
                          onSelect={() => onPost(t)}
                          className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm outline-none data-highlighted:bg-surface-2"
                        >
                          <Check className="size-4 text-positive" /> Marcar como pago
                        </DropdownMenu.Item>
                      )}
                      {onCancel && (
                        <DropdownMenu.Item
                          onSelect={() => onCancel(t)}
                          className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-negative outline-none data-highlighted:bg-negative-soft"
                        >
                          <XCircle className="size-4" /> {transfer ? 'Cancelar transferência' : 'Cancelar lançamento'}
                        </DropdownMenu.Item>
                      )}
                    </DropdownMenu.Content>
                  </DropdownMenu.Portal>
                </DropdownMenu.Root>
              )}
            </motion.li>
          )
        })}
      </AnimatePresence>
    </ul>
  )
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-border" aria-busy="true" aria-label="Carregando">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-5 py-3">
          <div className="shimmer size-9 rounded-xl" />
          <div className="flex-1 space-y-2">
            <div className="shimmer h-3.5 w-2/5 rounded" />
            <div className="shimmer h-3 w-1/4 rounded" />
          </div>
          <div className="shimmer h-4 w-20 rounded" />
        </div>
      ))}
    </div>
  )
}
