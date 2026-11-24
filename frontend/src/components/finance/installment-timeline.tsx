import { motion } from 'motion/react'
import { Calendar, CheckCircle2, Clock, CreditCard, Loader2, XCircle } from 'lucide-react'
import { formatRelativeDate } from '@/lib/date'
import { CurrencyDisplay } from './currency'
import { cn } from '@/lib/utils'
import type { CardInstallment, CardPurchase } from '@/types/api'

type InstallmentWithPurchase = CardInstallment & { purchase?: CardPurchase }

interface InstallmentTimelineProps {
  installments: InstallmentWithPurchase[]
  className?: string
  maxItems?: number
  showPurchase?: boolean
}

const STATUS_CONFIG = {
  PAID: { icon: CheckCircle2, color: 'text-positive', bg: 'bg-positive/10', label: 'Paga', animate: true },
  POSTED: { icon: CreditCard, color: 'text-accent', bg: 'bg-accent/10', label: 'Lançada', animate: false },
  PENDING: { icon: Clock, color: 'text-warning', bg: 'bg-warning/10', label: 'Pendente', animate: true },
  REVERSED: { icon: XCircle, color: 'text-negative', bg: 'bg-negative/10', label: 'Estornada', animate: false },
  CANCELLED: { icon: XCircle, color: 'text-muted', bg: 'bg-muted/10', label: 'Cancelada', animate: false },
} as const

export function InstallmentTimeline({ installments, className, maxItems, showPurchase = true }: InstallmentTimelineProps) {
  const visible = maxItems ? installments.slice(0, maxItems) : installments
  const remaining = maxItems && installments.length > maxItems ? installments.length - maxItems : 0

  return (
    <div className={cn('space-y-2.5', className)} role="list" aria-label="Parcelas">
      {visible.map((inst, idx) => (
        <InstallmentItem key={inst.id} inst={inst} index={idx} showPurchase={showPurchase} isLast={idx === visible.length - 1} />
      ))}
      {remaining > 0 && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="flex items-center justify-center gap-2 px-3 py-2 text-sm text-muted border-t border-dashed border-border"
        >
          <span>+ {remaining} parcela{remaining > 1 ? 's' : ''}</span>
        </motion.div>
      )}
    </div>
  )
}

interface InstallmentItemProps {
  inst: InstallmentWithPurchase
  index: number
  showPurchase: boolean
  isLast: boolean
}

function InstallmentItem({ inst, index, showPurchase, isLast }: InstallmentItemProps) {
  const cfg = STATUS_CONFIG[inst.status]
  const Icon = cfg.icon
  const purchaseName = inst.purchase?.description ?? `Compra ${(inst.purchase as CardPurchase & { id: string })?.id?.slice(0, 8) ?? ''}`
  const purchaseMerchant = inst.purchase?.merchant

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0, transition: { delay: index * 0.04 } }}
      className="relative flex items-start gap-3"
      role="listitem"
    >
      <div className="relative flex flex-col items-center shrink-0" aria-hidden>
        <div className={cn('relative z-10 grid size-8 place-items-center rounded-full border-2', cfg.bg, cfg.color)}>
          {inst.status === 'PENDING' && cfg.animate && <Loader2 className="size-4 animate-spin" />}
          {inst.status === 'PAID' && <CheckCircle2 className="size-4" />}
          {(inst.status === 'POSTED' || inst.status === 'REVERSED' || inst.status === 'CANCELLED') && <Icon className="size-4" />}
        </div>
        {!isLast && <div className="absolute top-8 bottom-0 left-3.5 w-0.5 border-l border-dashed border-border" />}
      </div>

      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 min-w-0 flex items-center gap-2">
            <span className={cn('font-medium text-fg truncate', inst.status === 'PAID' && 'line-through text-muted')}>
              {purchaseName}
            </span>
            {purchaseMerchant && (
              <span className="shrink-0 text-xs text-muted/70 px-1.5 py-0.5 rounded bg-surface-2">{purchaseMerchant}</span>
            )}
          </div>
          <CurrencyDisplay cents={inst.amount_cents} className={cn('shrink-0 font-semibold', inst.status === 'PAID' && 'text-muted')} />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className={cn('flex items-center gap-1 px-2 py-0.5 rounded-full', cfg.bg, cfg.color)}>
            <Icon className="size-3" aria-hidden />
            {cfg.label}
          </span>
          <span className="flex items-center gap-1 text-muted">
            <Calendar className="size-3" aria-hidden />
            Parcela {inst.installment_number}
          </span>
          {inst.paid_at && (
            <span className="flex items-center gap-1 text-positive">
              <CheckCircle2 className="size-3" aria-hidden />
              Paga em {formatRelativeDate(inst.paid_at)}
            </span>
          )}
        </div>

        {showPurchase && inst.purchase && (
          <div className="text-xs text-muted/70 flex items-center gap-1">
            <CreditCard className="size-3" aria-hidden />
            <span>Compra em {formatRelativeDate(inst.purchase.purchased_on)}</span>
            {inst.purchase.merchant && <span> · </span>}
            {inst.purchase.merchant && <span>{inst.purchase.merchant}</span>}
          </div>
        )}
      </div>
    </motion.div>
  )
}

interface UpcomingInstallmentsProps {
  installments: InstallmentWithPurchase[]
  className?: string
  limit?: number
}

export function UpcomingInstallments({ installments, className, limit = 10 }: UpcomingInstallmentsProps) {
  const upcoming = installments
    .filter((i) => i.status === 'PENDING' || i.status === 'POSTED')
    .sort((a, b) => a.installment_number - b.installment_number)
    .slice(0, limit)

  if (upcoming.length === 0) {
    return (
      <div className={cn('text-center py-8 text-muted', className)}>
        <CreditCard className="mx-auto size-10 text-muted/30 mb-2" aria-hidden />
        <p>Nenhuma parcela futura</p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-2', className)}>
      {upcoming.map((inst, idx) => (
        <UpcomingItem key={inst.id} inst={inst} index={idx} />
      ))}
    </div>
  )
}

function UpcomingItem({ inst, index }: { inst: InstallmentWithPurchase; index: number }) {
  const purchaseName = inst.purchase?.description ?? 'Compra'
  const purchaseMerchant = inst.purchase?.merchant

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0, transition: { delay: index * 0.05 } }}
      className="flex items-center gap-3 p-3 rounded-xl bg-surface-2/50 border border-border/50 hover:border-border hover:bg-surface-2/80 transition-colors"
    >
      <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent" aria-hidden>
        <CreditCard className="size-5" />
      </div>
      <div className="flex-1 min-w-0 space-y-0.5">
        <p className="font-medium text-fg truncate">{purchaseName}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Parcela {inst.installment_number}</span>
          {purchaseMerchant && <span>· {purchaseMerchant}</span>}
        </div>
      </div>
      <CurrencyDisplay cents={inst.amount_cents} className="shrink-0 font-semibold text-fg" />
    </motion.div>
  )
}