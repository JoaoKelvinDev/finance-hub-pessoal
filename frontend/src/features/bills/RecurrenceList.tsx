import { CalendarClock, ChevronDown, ChevronUp, Play, Pause, RotateCcw, Zap } from 'lucide-react'
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { formatDate } from '@/lib/date'
import { useRecurrences, usePostRecurrenceInstallments } from '@/lib/queries'
import { Tooltip } from '@/components/ui/misc'
import { cn } from '@/lib/utils'
import type { Recurrence } from '@/types/api'

const FREQUENCY_LABELS: Record<string, string> = {
  MONTHLY: 'Mensal',
  BIMONTHLY: 'Bimestral',
  QUARTERLY: 'Trimestral',
  SEMIANNUAL: 'Semestral',
  ANNUAL: 'Anual',
  CUSTOM: 'Personalizado',
}

const STATUS_LABELS: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  ACTIVE: { label: 'Ativa', color: 'bg-positive/10 text-positive', icon: <Play className="size-3" /> },
  PAUSED: { label: 'Pausada', color: 'bg-warning/10 text-warning', icon: <Pause className="size-3" /> },
  ENDED: { label: 'Encerrada', color: 'bg-muted text-muted', icon: <RotateCcw className="size-3" /> },
}

interface RecurrenceListProps {
  billId?: string
  status?: string
  onRecurrenceClick?: (recurrence: Recurrence) => void
}

export function RecurrenceList({ billId, status, onRecurrenceClick }: RecurrenceListProps) {
  const { data: recurrences, isLoading, isError, error, refetch } = useRecurrences(billId, status)
  const postInstallments = usePostRecurrenceInstallments()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const handlePostInstallments = async (id: string) => {
    try {
      await postInstallments.mutateAsync({ recurrenceId: id, up_to_date: new Date().toISOString().split('T')[0] })
      refetch()
    } catch {
      // error handled by mutation
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <RecurrenceSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <Card className="p-6 text-center">
        <p className="text-negative">Erro ao carregar recorrências: {(error as Error).message}</p>
        <Button variant="secondary" size="sm" onClick={() => refetch()} className="mt-2">
          Tentar novamente
        </Button>
      </Card>
    )
  }

  if (!recurrences?.length) {
    return (
      <Card className="p-6 text-center">
        <CalendarClock className="mx-auto size-12 text-muted/50 mb-3" aria-hidden />
        <p className="text-muted">Nenhuma recorrência encontrada.</p>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {recurrences.map((recurrence) => (
        <RecurrenceCard
          key={recurrence.id}
          recurrence={recurrence}
          isExpanded={expandedId === recurrence.id}
          onToggle={() => setExpandedId(expandedId === recurrence.id ? null : recurrence.id)}
          onClick={(e) => {
            if (!(e.target as HTMLElement).closest('button')) {
              onRecurrenceClick?.(recurrence)
            }
          }}
          onPostInstallments={handlePostInstallments}
          isPosting={postInstallments.variables?.recurrenceId === recurrence.id && postInstallments.isPending}
        />
      ))}
    </div>
  )
}

interface RecurrenceCardProps {
  recurrence: Recurrence
  isExpanded: boolean
  onToggle: () => void
  onClick: (e: React.MouseEvent) => void
  onPostInstallments: (id: string) => void
  isPosting: boolean
}

function RecurrenceCard({
  recurrence,
  isExpanded,
  onToggle,
  onClick,
  onPostInstallments,
  isPosting,
}: RecurrenceCardProps) {
  const statusInfo = STATUS_LABELS[recurrence.status] || { label: recurrence.status, color: '', icon: null }

  return (
    <Card
      className={cn(
        'group relative cursor-pointer transition-colors',
        'hover:bg-surface-2/60',
        recurrence.status === 'ENDED' && 'opacity-60',
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-4 p-4">
        <span
          className="shrink-0 size-10 rounded-xl flex items-center justify-center"
          style={{ background: (recurrence.bill_color || '#3B82F6') + '20', color: recurrence.bill_color || '#3B82F6' }}
          aria-hidden
        >
          <CalendarClock className="size-5" />
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <h3 className="font-medium truncate">{recurrence.bill_name || 'Conta'}</h3>
              <span className={cn('shrink-0 px-2 py-0.5 text-[10px] font-medium rounded', statusInfo.color)}>
                {statusInfo.icon}
                <span className="ml-1">{statusInfo.label}</span>
              </span>
              {recurrence.auto_post && (
                <Tooltip content="Postagem automática ativada">
                  <Zap className="size-3.5 text-warning" aria-hidden />
                </Tooltip>
              )}
            </div>

            <div className="flex items-center gap-1">
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
            <span className="flex items-center gap-1">
              <CalendarClock className="size-3.5" aria-hidden />
              {FREQUENCY_LABELS[recurrence.frequency] || recurrence.frequency}
              {recurrence.frequency === 'CUSTOM' && recurrence.custom_months_interval && (
                <span>({recurrence.custom_months_interval} meses)</span>
              )}
            </span>
            <span>Dia {recurrence.day_of_month}</span>
            {recurrence.next_due_date && (
              <span className="flex items-center gap-1 font-medium text-fg">
                Próxima: {formatDate(recurrence.next_due_date)}
              </span>
            )}
          </div>

          <div className="mt-1 flex items-center gap-3 text-sm text-muted">
            <span>Início: {formatDate(recurrence.start_date)}</span>
            {recurrence.end_date && <span>Fim: {formatDate(recurrence.end_date)}</span>}
            {recurrence.last_posted_due && (
              <span>Última postada: {formatDate(recurrence.last_posted_due)}</span>
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
                  <p className="font-mono text-sm">{recurrence.id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Status</p>
                  <p className="text-sm capitalize">{recurrence.status.toLowerCase()}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Postagem automática</p>
                  <p className="text-sm">{recurrence.auto_post ? 'Sim' : 'Não'}</p>
                </div>
              </div>

              {recurrence.notes && (
                <div>
                  <p className="text-xs text-muted">Observações</p>
                  <p className="text-sm whitespace-pre-wrap">{recurrence.notes}</p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-border">
                {recurrence.status === 'ACTIVE' && recurrence.auto_post && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); onPostInstallments(recurrence.id); }}
                    loading={isPosting}
                    disabled={isPosting}
                  >
                    <Zap className="size-3.5 mr-1" /> Postar parcelas agora
                  </Button>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); onClick(e); }}
                >
                  Ver parcelas
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

function RecurrenceSkeleton() {
  return (
    <Card className="p-4 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="size-10 rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-3">
          <div className="h-5 w-1/2 bg-surface-2 rounded" />
          <div className="h-4 w-1/3 bg-surface-2 rounded" />
          <div className="h-4 w-2/3 bg-surface-2 rounded" />
        </div>
      </div>
    </Card>
  )
}