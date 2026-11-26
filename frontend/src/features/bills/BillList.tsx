import { ChevronDown, ChevronUp, Home, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { CurrencyDisplay } from '@/components/finance/currency'
import { formatDate } from '@/lib/date'
import { useBills, useArchiveBill, useRestoreBill } from '@/lib/queries'
import { Tooltip } from '@/components/ui/misc'
import { cn } from '@/lib/utils'
import type { Bill } from '@/types/api'

const CATEGORY_LABELS: Record<string, string> = {
  RENT: 'Aluguel',
  WATER: 'Água',
  ELECTRICITY: 'Energia',
  GAS: 'Gás',
  INTERNET: 'Internet',
  PHONE: 'Telefone',
  TV: 'Streaming',
  INSURANCE: 'Seguros',
  CONDO: 'Condomínio',
  EDUCATION: 'Educação',
  HEALTH: 'Saúde',
  OTHER: 'Outros',
}

interface BillListProps {
  includeArchived?: boolean
  onBillClick?: (bill: Bill) => void
}

export function BillList({ includeArchived = false, onBillClick }: BillListProps) {
  const { data: bills, isLoading, isError, error, refetch } = useBills(includeArchived)
  const archiveBill = useArchiveBill()
  const restoreBill = useRestoreBill()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const handleArchive = async (id: string) => {
    try {
      await archiveBill.mutateAsync(id)
      refetch()
    } catch {
      // error handled by mutation
    }
  }

  const handleRestore = async (id: string) => {
    try {
      await restoreBill.mutateAsync(id)
      refetch()
    } catch {
      // error handled by mutation
    }
  }

  const handleClick = (bill: Bill, e: React.MouseEvent) => {
    // Don't trigger if clicking on action buttons
    if (
      (e.target as HTMLElement).closest('button') ||
      (e.target as HTMLElement).closest('a')
    ) {
      return
    }
    if (onBillClick) {
      onBillClick(bill)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <BillSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <Card className="p-6 text-center">
        <p className="text-negative">Erro ao carregar contas: {(error as Error).message}</p>
        <Button variant="secondary" size="sm" onClick={() => refetch()} className="mt-2">
          Tentar novamente
        </Button>
      </Card>
    )
  }

  if (!bills?.length) {
    return (
      <Card className="p-6 text-center">
        <Home className="mx-auto size-12 text-muted/50 mb-3" aria-hidden />
        <p className="text-muted">
          {includeArchived ? 'Nenhuma conta arquivada.' : 'Nenhuma conta cadastrada.'}
        </p>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {bills.map((bill) => (
        <BillCard
          key={bill.id}
          bill={bill}
          isExpanded={expandedId === bill.id}
          onToggle={() => setExpandedId(expandedId === bill.id ? null : bill.id)}
          onClick={(e) => handleClick(bill, e)}
          onOpen={() => onBillClick?.(bill)}
          onArchive={handleArchive}
          onRestore={handleRestore}
          isArchiving={archiveBill.variables === bill.id && archiveBill.isPending}
          isRestoring={restoreBill.variables === bill.id && restoreBill.isPending}
        />
      ))}
    </div>
  )
}

interface BillCardProps {
  bill: Bill
  isExpanded: boolean
  onToggle: () => void
  onClick: (e: React.MouseEvent) => void
  /** Abre a conta. O clique no card ignora botões, então o botão "Ver detalhes" precisa chamar isto direto. */
  onOpen: () => void
  onArchive: (id: string) => void
  onRestore: (id: string) => void
  isArchiving: boolean
  isRestoring: boolean
}

function BillCard({
  bill,
  isExpanded,
  onToggle,
  onClick,
  onOpen,
  onArchive,
  onRestore,
  isArchiving,
  isRestoring,
}: BillCardProps) {
  const isArchived = !!bill.archived_at

  return (
    <Card
      className={cn(
        'group relative cursor-pointer transition-colors',
        'hover:bg-surface-2/60',
        isArchived && 'opacity-60 bg-muted/30',
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-4 p-4">
        <span
          className="shrink-0 size-10 rounded-xl flex items-center justify-center"
          style={{ background: bill.color + '20', color: bill.color }}
          aria-hidden
        >
          <Home className="size-5" />
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <h3 className={cn('font-medium truncate', isArchived && 'line-through')}>
                {bill.name}
              </h3>
              <span
                className="shrink-0 px-2 py-0.5 text-[10px] font-medium rounded bg-surface-2 text-muted"
              >
                {CATEGORY_LABELS[bill.category] || bill.category}
              </span>
              {isArchived && (
                <span className="shrink-0 px-2 py-0.5 text-[10px] font-medium rounded bg-negative/10 text-negative">
                  Arquivada
                </span>
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
              <Tooltip content={isArchived ? 'Restaurar' : 'Arquivar'}>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (isArchived) onRestore(bill.id)
                    else onArchive(bill.id)
                  }}
                  disabled={isArchiving || isRestoring}
                  className="p-1.5 rounded-lg text-muted hover:bg-surface-2 hover:text-negative transition-colors disabled:opacity-50"
                  aria-label={isArchived ? 'Restaurar' : 'Arquivar'}
                >
                  {isArchiving || isRestoring ? (
                    <span className="size-4 animate-spin border-2 border-accent border-t-transparent rounded-full" />
                  ) : (
                    <Trash2 className="size-4" />
                  )}
                </button>
              </Tooltip>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-4 text-sm text-muted">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full" style={{ background: bill.account_color || '#666' }} />
              {bill.account_name}
            </span>
            <span>
              Valor padrão: <CurrencyDisplay cents={bill.default_amount_cents} className="inline font-medium" />
            </span>
          </div>

          {bill.description && (
            <p className="mt-2 text-sm text-muted line-clamp-2">{bill.description}</p>
          )}
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
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="text-xs text-muted">ID</p>
                  <p className="font-mono text-sm">{bill.id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Criada em</p>
                  <p className="text-sm">{formatDate(bill.created_at.split('T')[0])}</p>
                </div>
              </div>

              {bill.notes && (
                <div>
                  <p className="text-xs text-muted">Observações</p>
                  <p className="text-sm whitespace-pre-wrap">{bill.notes}</p>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-border">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); onOpen(); }}
                >
                  Ver detalhes
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

function BillSkeleton() {
  return (
    <Card className="p-4 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="size-10 rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-3">
          <div className="h-5 w-3/4 bg-surface-2 rounded" />
          <div className="h-4 w-1/2 bg-surface-2 rounded" />
          <div className="h-4 w-1/3 bg-surface-2 rounded" />
        </div>
      </div>
    </Card>
  )
}