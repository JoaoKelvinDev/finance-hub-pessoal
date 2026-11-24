import { motion } from 'motion/react'
import { AlertTriangle, CheckCircle2, Clock, RotateCw, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { easeOut } from '@/lib/motion'
import { cn } from '@/lib/utils'
import type { TxStatus } from '@/types/api'

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
  className?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: easeOut }}
      className={cn('flex flex-col items-center justify-center gap-3 px-6 py-10 text-center', className)}
    >
      <span className="grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent [&_svg]:size-6" aria-hidden>
        {icon}
      </span>
      <div>
        <p className="font-semibold">{title}</p>
        <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{description}</p>
      </div>
      {action}
    </motion.div>
  )
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-negative-soft text-negative" aria-hidden>
        <AlertTriangle className="size-6" />
      </span>
      <div>
        <p className="font-semibold">Não foi possível carregar</p>
        <p className="mt-1 text-sm text-muted">{message ?? 'Verifique se a API está em execução.'}</p>
      </div>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RotateCw /> Tentar novamente
      </Button>
    </div>
  )
}

const STATUS: Record<TxStatus | 'OVERDUE', { label: string; icon: typeof Clock; cls: string }> = {
  POSTED: { label: 'Efetivado', icon: CheckCircle2, cls: 'bg-positive-soft text-positive' },
  PLANNED: { label: 'Previsto', icon: Clock, cls: 'bg-accent-soft text-accent' },
  OVERDUE: { label: 'Vencido', icon: AlertTriangle, cls: 'bg-negative-soft text-negative' },
  CANCELLED: { label: 'Cancelado', icon: XCircle, cls: 'bg-surface-2 text-muted line-through' },
}

/** Status com ícone + texto (nunca só cor). */
export function StatusBadge({ status, overdue }: { status: TxStatus; overdue?: boolean }) {
  const s = STATUS[overdue && status === 'PLANNED' ? 'OVERDUE' : status]
  const Icon = s.icon
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium', s.cls)}>
      <Icon className="size-3" aria-hidden />
      {s.label}
    </span>
  )
}
