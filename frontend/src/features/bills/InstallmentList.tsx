import { Calculator, CalendarClock, Check, ChevronDown, ChevronUp, RotateCcw, SkipForward, Trash2, Users, X } from 'lucide-react'
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { CurrencyDisplay } from '@/components/finance/currency'
import { formatDate } from '@/lib/date'
import { useBillInstallments, useReverseBillInstallment, useSkipBillInstallment, useCancelBillInstallment } from '@/lib/queries'
import { Tooltip } from '@/components/ui/misc'
import { ConfirmAmountDialog, SplitDialog } from '@/features/bills/SplitDialog'
import { PayInstallmentDialog } from '@/features/bills/PayInstallmentDialog'
import { readApiError } from '@/features/parties/meta'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import type { BillInstallment } from '@/types/api'

const STATUS_LABELS: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  PENDING: { label: 'Pendente', color: 'bg-muted text-muted', icon: <CalendarClock className="size-3" /> },
  POSTED: { label: 'Postada', color: 'bg-blue/10 text-blue', icon: <RotateCcw className="size-3" /> },
  PAID: { label: 'Paga', color: 'bg-positive/10 text-positive', icon: <Check className="size-3" /> },
  REVERSED: { label: 'Estornada', color: 'bg-warning/10 text-warning', icon: <RotateCcw className="size-3" /> },
  CANCELLED: { label: 'Cancelada', color: 'bg-negative/10 text-negative', icon: <X className="size-3" /> },
  SKIPPED: { label: 'Pulada', color: 'bg-muted text-muted', icon: <SkipForward className="size-3" /> },
}

interface InstallmentListProps {
  billId?: string
  recurrenceId?: string
  status?: string
  dueFrom?: string
  dueTo?: string
}

export function InstallmentList({
  billId,
  recurrenceId,
  status,
  dueFrom,
  dueTo,
}: InstallmentListProps) {
  const { data, isLoading, isError, error, refetch } = useBillInstallments({
    bill_id: billId,
    recurrence_id: recurrenceId,
    status,
    due_from: dueFrom,
    due_to: dueTo,
    limit: 20,
  })

  const reverseMutation = useReverseBillInstallment()
  const skipMutation = useSkipBillInstallment()
  const cancelMutation = useCancelBillInstallment()

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [confirmAmount, setConfirmAmount] = useState<BillInstallment | null>(null)
  const [splitInstallment, setSplitInstallment] = useState<BillInstallment | null>(null)
  const [payInstallment, setPayInstallment] = useState<BillInstallment | null>(null)

  const allItems = data?.items ?? []
  const total = data?.total ?? 0

  /** Abre o pagamento da parcela — pela tela da própria lista, com todos os dados reais. */
  const handlePay = (installment: BillInstallment) => {
    setPayInstallment(installment)
  }

  /** Executa a ação e sempre dá retorno: sucesso ou o motivo da recusa (ex.: parcela com rateio). */
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn()
      toast.success(ok)
      refetch()
    } catch (err) {
      toast.error(readApiError(err).message)
    }
  }

  const handleReverse = (id: string) =>
    run(() => reverseMutation.mutateAsync({ installmentId: id }), 'Pagamento estornado.')
  const handleSkip = (id: string) => run(() => skipMutation.mutateAsync({ installmentId: id }), 'Parcela pulada.')
  const handleCancel = (id: string) => run(() => cancelMutation.mutateAsync({ installmentId: id }), 'Parcela cancelada.')

  if (isLoading && !allItems.length) {
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <InstallmentSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <Card className="p-6 text-center">
        <p className="text-negative">Erro ao carregar parcelas: {(error as Error).message}</p>
        <Button variant="secondary" size="sm" onClick={() => refetch()} className="mt-2">
          Tentar novamente
        </Button>
      </Card>
    )
  }

  if (!allItems.length) {
    return (
      <Card className="p-6 text-center">
        <CalendarClock className="mx-auto size-12 text-muted/50 mb-3" aria-hidden />
        <p className="text-muted">Nenhuma parcela encontrada.</p>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {allItems.map((installment) => (
        <InstallmentCard
          key={installment.id}
          installment={installment}
          isExpanded={expandedId === installment.id}
          onToggle={() => setExpandedId(expandedId === installment.id ? null : installment.id)}
          onClick={(e) => {
            if (!(e.target as HTMLElement).closest('button') && !(e.target as HTMLElement).closest('a')) {
              if (['PENDING', 'POSTED'].includes(installment.status)) setPayInstallment(installment)
            }
          }}
          onPay={handlePay}
          onReverse={handleReverse}
          onSkip={handleSkip}
          onCancel={handleCancel}
          onConfirmAmount={setConfirmAmount}
          onSplit={setSplitInstallment}
          isReversing={reverseMutation.variables?.installmentId === installment.id && reverseMutation.isPending}
          isSkipping={skipMutation.variables?.installmentId === installment.id && skipMutation.isPending}
          isCancelling={cancelMutation.variables?.installmentId === installment.id && cancelMutation.isPending}
        />
      ))}

      <p className="text-center text-sm text-muted">Total: {total} parcela{total !== 1 ? 's' : ''}</p>

      <ConfirmAmountDialog installment={confirmAmount} onClose={() => setConfirmAmount(null)} />
      <SplitDialog installment={splitInstallment} onClose={() => setSplitInstallment(null)} />
      <PayInstallmentDialog
        key={payInstallment?.id ?? 'none'}
        open={!!payInstallment}
        onOpenChange={(open) => { if (!open) setPayInstallment(null) }}
        installment={payInstallment}
        onSuccess={() => { setPayInstallment(null); refetch() }}
      />
    </div>
  )
}

interface InstallmentCardProps {
  installment: BillInstallment
  isExpanded: boolean
  onToggle: () => void
  onClick: (e: React.MouseEvent) => void
  onPay: (installment: BillInstallment) => void
  onReverse: (id: string) => void
  onSkip: (id: string) => void
  onCancel: (id: string) => void
  onConfirmAmount: (installment: BillInstallment) => void
  onSplit: (installment: BillInstallment) => void
  isReversing: boolean
  isSkipping: boolean
  isCancelling: boolean
}

function InstallmentCard({
  installment,
  isExpanded,
  onToggle,
  onClick,
  onPay,
  onReverse,
  onSkip,
  onCancel,
  onConfirmAmount,
  onSplit,
  isReversing,
  isSkipping,
  isCancelling,
}: InstallmentCardProps) {
  const statusInfo = STATUS_LABELS[installment.status] || { label: installment.status, color: '', icon: null }
  const isPaid = installment.status === 'PAID'
  const isReversible = installment.status === 'PAID'
  const isSkippable = ['PENDING', 'POSTED'].includes(installment.status)
  const isCancellable = ['PENDING', 'POSTED', 'SKIPPED'].includes(installment.status)
  const isPayable = ['PENDING', 'POSTED'].includes(installment.status)
  // O rateio só faz sentido com o valor confirmado e a parcela em aberto.
  const isSplittable = !installment.is_estimate && !['CANCELLED', 'SKIPPED', 'REVERSED'].includes(installment.status)

  return (
    <Card
      className={cn(
        'group relative cursor-pointer transition-colors',
        'hover:bg-surface-2/60',
        isPaid && 'opacity-70',
        installment.status === 'CANCELLED' && 'opacity-50 line-through',
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-4 p-4">
        <span
          className="shrink-0 size-10 rounded-xl flex items-center justify-center"
          style={{ background: (installment.bill_color || '#EF4444') + '20', color: installment.bill_color || '#EF4444' }}
          aria-hidden
        >
          <CalendarClock className="size-5" />
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <h3 className="font-medium truncate">{installment.bill_name || 'Parcela'}</h3>
              <span className={cn('shrink-0 px-2 py-0.5 text-[10px] font-medium rounded', statusInfo.color)}>
                {statusInfo.icon}
                <span className="ml-1">{statusInfo.label}</span>
              </span>
              {installment.is_estimate && (
                <span className="shrink-0 rounded bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-muted">
                  Estimado
                </span>
              )}
              {installment.split_id && (
                <span className="shrink-0 rounded bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-muted">
                  Rateado
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <CurrencyDisplay cents={installment.amount_cents} className="font-medium text-lg shrink-0" />
              <Tooltip content={isExpanded ? 'Recolher' : 'Expandir'}>
                <button
                  onClick={(e) => { e.stopPropagation(); onToggle(); }}
                  className="p-1.5 rounded-lg text-muted hover:bg-surface-2 hover:text-fg transition-colors"
                  aria-label={isExpanded ? 'Recolher' : 'Expandir'}
                >
                  {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </button>
              </Tooltip>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted">
            <span>Vence: <strong>{formatDate(installment.due_date)}</strong></span>
            {installment.paid_at && (
              <span className="text-positive">Paga em {formatDate(installment.paid_at.split('T')[0])}</span>
            )}
            {installment.recurrence_id && (
              <span className="px-2 py-0.5 text-[10px] font-medium rounded bg-surface-2">
                Recorrência
              </span>
            )}
          </div>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border bg-surface-2/50"
          >
            <div className="p-4 space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-muted">ID</p>
                  <p className="font-mono text-sm">{installment.id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Conta</p>
                  <p className="text-sm">{installment.bill_name || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Status</p>
                  <p className="text-sm capitalize">{installment.status.toLowerCase()}</p>
                </div>
              </div>

              {installment.is_estimate && (
                <p className="text-xs text-muted">
                  Valor estimado: <CurrencyDisplay cents={installment.amount_cents} animated={false} className="inline" />.
                  Informe o valor real para ratear; se pagar com outro valor, ele vira o real.
                </p>
              )}

              {installment.notes && (
                <div>
                  <p className="text-xs text-muted">Observações</p>
                  <p className="text-sm whitespace-pre-wrap">{installment.notes}</p>
                </div>
              )}

              <div className="flex flex-wrap justify-end gap-2 pt-2 border-t border-border">
                {installment.is_estimate && isPayable && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onConfirmAmount(installment); }}
                  >
                    <Calculator className="size-3.5 mr-1" /> Informar valor real
                  </Button>
                )}
                {isSplittable && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onSplit(installment); }}
                  >
                    <Users className="size-3.5 mr-1" /> {installment.split_id ? 'Ver rateio' : 'Ratear'}
                  </Button>
                )}
                {isSkippable && !isPaid && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onSkip(installment.id); }}
                    loading={isSkipping}
                    disabled={isSkipping}
                  >
                    <SkipForward className="size-3.5 mr-1" /> Pular
                  </Button>
                )}
                {isCancellable && !isPaid && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onCancel(installment.id); }}
                    loading={isCancelling}
                    disabled={isCancelling}
                  >
                    <Trash2 className="size-3.5 mr-1" /> Cancelar
                  </Button>
                )}
                {isPayable && (
                  <Button
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onPay(installment); }}
                  >
                    Pagar
                  </Button>
                )}
                {isReversible && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onReverse(installment.id); }}
                    loading={isReversing}
                    disabled={isReversing}
                  >
                    <RotateCcw className="size-3.5 mr-1" /> Estornar
                  </Button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

function InstallmentSkeleton() {
  return (
    <Card className="p-4 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="size-10 rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-3">
          <div className="flex justify-between">
            <div className="h-5 w-1/2 bg-surface-2 rounded" />
            <div className="h-7 w-20 bg-surface-2 rounded" />
          </div>
          <div className="h-4 w-1/3 bg-surface-2 rounded" />
        </div>
      </div>
    </Card>
  )
}