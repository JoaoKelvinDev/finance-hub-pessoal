import { motion } from 'motion/react'
import { Plus, CreditCard, ChevronRight, Archive, RotateCcw } from 'lucide-react'
import { useCards } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardContent, Skeleton } from '@/components/ui/card'
import { EmptyState } from '@/components/finance/states'
import { CurrencyDisplay, UtilizationBadge } from '@/components/finance/card-utilization'
import { NewCardDialog } from '@/features/cards/new-card-dialog'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Tooltip } from '@/components/ui/misc'

export function CardsPage() {
  const [newCardOpen, setNewCardOpen] = useState(false)
  const [editingCard, setEditingCard] = useState<string | null>(null)
  const [includeArchived, setIncludeArchived] = useState(false)

  const { data, isLoading, isError, error, refetch } = useCards(includeArchived)

  const qc = useQueryClient()
  const archiveMutation = useMutation({
    mutationFn: ({ id, archived }: { id: string; archived: boolean }) =>
      api<{ id: string }>(`/cards/${id}`, { method: 'PATCH', body: { archived } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cards'] }),
  })

  if (isError) {
    return (
      <Card>
        <EmptyState
          icon={<CreditCard className="size-6" />}
          title="Erro ao carregar cartões"
          description={(error as Error)?.message}
          action={<Button variant="secondary" onClick={() => refetch()}>Tentar novamente</Button>}
        />
      </Card>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-4" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    )
  }

  const activeCards = data.filter((c) => !c.archived_at)
  const archivedCards = data.filter((c) => c.archived_at)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cartões</h1>
          <p className="text-sm text-muted mt-0.5">
            Gerencie seus cartões de crédito, limites e faturas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIncludeArchived(!includeArchived)}>
            {includeArchived ? <RotateCcw className="size-4 mr-1" /> : <Archive className="size-4 mr-1" />}
            {includeArchived ? 'Ocultar arquivados' : 'Mostrar arquivados'}
          </Button>
          <Button onClick={() => { setEditingCard(null); setNewCardOpen(true) }}>
            <Plus className="size-4" /> Novo cartão
          </Button>
        </div>
      </div>

      {activeCards.length === 0 && !includeArchived ? (
        <Card>
          <EmptyState
            icon={<CreditCard className="size-6" />}
            title="Nenhum cartão cadastrado"
            description="Adicione seu primeiro cartão para começar a acompanhar limites, compras parceladas e faturas."
            action={<Button onClick={() => setNewCardOpen(true)}><Plus /> Cadastrar cartão</Button>}
          />
        </Card>
      ) : (
        <>
          {activeCards.length > 0 && (
            <section aria-label="Cartões ativos" className="space-y-4">
              <h2 className="text-sm font-medium text-muted uppercase tracking-wide">Ativos ({activeCards.length})</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {activeCards.map((card) => (
                  <CardCard key={card.id} card={card} onEdit={() => { setEditingCard(card.id); setNewCardOpen(true) }} onArchive={() => archiveMutation.mutate({ id: card.id, archived: true })} />
                ))}
              </div>
            </section>
          )}

          {archivedCards.length > 0 && includeArchived && (
            <section aria-label="Cartões arquivados" className="space-y-4">
              <h2 className="text-sm font-medium text-muted uppercase tracking-wide">Arquivados ({archivedCards.length})</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {archivedCards.map((card) => (
                  <CardCard
                    key={card.id}
                    card={card}
                    isArchived
                    onEdit={() => { setEditingCard(card.id); setNewCardOpen(true) }}
                    onRestore={() => archiveMutation.mutate({ id: card.id, archived: false })}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <NewCardDialog open={newCardOpen} onOpenChange={setNewCardOpen} cardToEdit={editingCard ? data.find(c => c.id === editingCard) || null : null} onSuccess={() => { setEditingCard(null); refetch() }} />
    </div>
  )
}

interface CardCardProps {
  card: {
    id: string
    name: string
    bank: string | null
    nickname: string | null
    last_four: string | null
    brand: string | null
    type: string
    limit_cents: number
    used_limit_cents: number
    available_limit_cents: number
    color: string
    closing_day: number
    due_day: number
    archived_at: string | null
  }
  isArchived?: boolean
  onEdit: () => void
  onArchive?: () => void
  onRestore?: () => void
}

function CardCard({ card, isArchived, onEdit, onArchive, onRestore }: CardCardProps) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('relative group', isArchived && 'opacity-60')}
    >
      <Card className="h-full overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1" style={{ background: card.color }} aria-hidden />

        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="grid size-9 shrink-0 place-items-center rounded-xl"
                  style={{ background: `${card.color}15` }}
                  aria-hidden
                >
                  <CreditCard className="size-5" style={{ color: card.color }} />
                </span>
                <div className="min-w-0">
                  <h3 className="font-semibold text-fg truncate">{card.name}</h3>
                  <p className="text-xs text-muted flex items-center gap-1">
                    {card.bank && <span>{card.bank}</span>}
                    {card.bank && card.nickname && <span>·</span>}
                    {card.nickname && <span>{card.nickname}</span>}
                    {card.last_four && <span>**** {card.last_four}</span>}
                    {card.brand && <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-surface-2 text-muted">{card.brand}</span>}
                  </p>
                </div>
              </div>
            </div>
            <UtilizationBadge used={card.used_limit_cents} limit={card.limit_cents} color={card.color} size="sm" />
          </div>
        </CardHeader>

        <CardContent className="pt-0 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted">Fechamento</span>
              <span className="font-medium">{card.closing_day}</span>
              <span className="text-muted">/</span>
              <span className="text-muted">Vencimento</span>
              <span className="font-medium">{card.due_day}</span>
            </div>
            <CurrencyDisplay cents={card.used_limit_cents} className="text-lg font-semibold" />
          </div>

          <div className="relative h-2 rounded-full bg-surface-2 overflow-hidden" role="progressbar" aria-valuenow={Math.round((card.used_limit_cents / card.limit_cents) * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min((card.used_limit_cents / card.limit_cents) * 100, 100)}%`,
                background: card.available_limit_cents < 0
                  ? 'linear-gradient(90deg, #EF4444, #F87171)'
                  : card.used_limit_cents / card.limit_cents >= 0.8
                  ? 'linear-gradient(90deg, #F59E0B, #FBBF24)'
                  : `linear-gradient(90deg, ${card.color}, ${card.color}CC)`,
              }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-muted">
            <span>R$ 0</span>
            <span>Limite {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(card.limit_cents / 100)}</span>
          </div>

          <div className="flex gap-2 pt-2 border-t border-border">
            <Button variant="secondary" size="sm" className="flex-1" onClick={() => window.location.href = `/cartoes/${card.id}`}>
              Ver detalhes
              <ChevronRight className="size-3.5 ml-1" />
            </Button>
            <Tooltip content="Editar">
              <Button variant="ghost" size="sm" onClick={onEdit} aria-label="Editar cartão">✎</Button>
            </Tooltip>
            {isArchived ? (
              <Tooltip content="Restaurar">
                <Button variant="ghost" size="sm" onClick={onRestore!} aria-label="Restaurar cartão">
                  <RotateCcw className="size-3.5" />
                </Button>
              </Tooltip>
            ) : (
              <Tooltip content="Arquivar">
                <Button variant="ghost" size="sm" onClick={onArchive!} aria-label="Arquivar cartão">
                  <Archive className="size-3.5" />
                </Button>
              </Tooltip>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.article>
  )
}

function CardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-1/2 mt-2" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-2 w-full mt-2 rounded-full" />
        <div className="flex gap-2 mt-4">
          <Skeleton className="h-9 flex-1" />
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-20" />
        </div>
      </CardContent>
    </Card>
  )
}