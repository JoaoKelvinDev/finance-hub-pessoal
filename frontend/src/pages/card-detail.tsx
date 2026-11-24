import { Plus, CreditCard, Calendar, AlertTriangle, CheckCircle2, Clock, ArrowLeft } from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import { useCard, useCardStatements, useCardPurchases, useUpcomingInstallments } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Card, CardContent, Skeleton } from '@/components/ui/card'
import { EmptyState } from '@/components/finance/states'
import { CurrencyDisplay, CardUtilization } from '@/components/finance/card-utilization'
import { UpcomingInstallments } from '@/components/finance/installment-timeline'
import { NewPurchaseDialog } from '@/features/cards/new-purchase-dialog'
import { PayStatementDialog } from '@/features/cards/pay-statement-dialog'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { formatRelativeDate } from '@/lib/date'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/misc'

const STATUS_CONFIG = {
  OPEN: { label: 'Aberta', color: 'bg-accent/10 text-accent', icon: Clock },
  CLOSED: { label: 'Fechada', color: 'bg-muted/10 text-muted', icon: CheckCircle2 },
  PARTIALLY_PAID: { label: 'Paga parcialmente', color: 'bg-warning/10 text-warning', icon: Clock },
  PAID: { label: 'Paga', color: 'bg-positive/10 text-positive', icon: CheckCircle2 },
  OVERDUE: { label: 'Vencida', color: 'bg-negative/10 text-negative', icon: AlertTriangle },
  CANCELLED: { label: 'Cancelada', color: 'bg-border text-muted', icon: AlertTriangle },
} as const

export function CardDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [newPurchaseOpen, setNewPurchaseOpen] = useState(false)
  const [payStatementOpen, setPayStatementOpen] = useState(false)
  const [selectedStatement, setSelectedStatement] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'faturas' | 'compras' | 'parcelas'>('faturas')

  const { data: card, isLoading: cardLoading, isError: cardError } = useCard(id!)
  const { data: statements } = useCardStatements(id!)
  const { data: upcoming } = useUpcomingInstallments(id!, 20)

  const currentStatement = statements?.find(s => s.id === selectedStatement)
  const { data: purchases } = useCardPurchases(id!, {})

  if (cardError) {
    return (
      <Card>
        <EmptyState
          icon={<CreditCard className="size-6" />}
          title="Erro ao carregar cartão"
          description="Tente novamente ou verifique a conexão."
          action={<Button onClick={() => navigate('/cartoes')}>Voltar</Button>}
        />
      </Card>
    )
  }

  if (cardLoading || !card) {
    return (
      <div className="space-y-4" aria-busy="true">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/cartoes')} aria-label="Voltar">
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{card.name}</h1>
            <p className="text-sm text-muted flex items-center gap-2">
              {card.bank && <span>{card.bank}</span>}
              {card.bank && card.nickname && <span>·</span>}
              {card.nickname && <span>{card.nickname}</span>}
              {card.last_four && <span>**** {card.last_four}</span>}
              <Badge variant="outline" className="text-[10px]">{card.brand}</Badge>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setNewPurchaseOpen(true)}>
            <Plus className="size-4" /> Nova compra
          </Button>
        </div>
      </div>

      {/* Resumo do limite */}
      <Card>
        <CardContent className="p-5">
          <CardUtilization
            used={card.used_limit_cents}
            limit={card.limit_cents}
            color={card.color}
          >
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-xs text-muted">Fechamento</p>
                <p className="font-medium">{card.closing_day}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Vencimento</p>
                <p className="font-medium">{card.due_day}</p>
              </div>
              <div>
                <p className="text-xs text-muted">Disponível</p>
                <CurrencyDisplay cents={card.available_limit_cents} className="font-medium" />
              </div>
            </div>
          </CardUtilization>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'faturas' | 'compras' | 'parcelas')} className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="faturas">Faturas ({statements?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="compras">Compras ({purchases?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="parcelas">Próximas parcelas ({upcoming?.filter(i => i.status === 'PENDING' || i.status === 'POSTED').length ?? 0})</TabsTrigger>
        </TabsList>

        {/* Faturas */}
        <TabsContent value="faturas" className="space-y-3">
          {statements?.length === 0 ? (
            <Card>
              <EmptyState
                icon={<CreditCard className="size-6" />}
                title="Nenhuma fatura ainda"
                description="Faça uma compra no cartão para gerar a primeira fatura."
              />
            </Card>
          ) : (
            <div className="space-y-2">
              {statements?.map((stmt) => (
                <StatementCard
                  key={stmt.id}
                  statement={stmt}
                  onClick={() => { setSelectedStatement(stmt.id); setPayStatementOpen(true) }}
                  onViewDetail={() => { setSelectedStatement(stmt.id); setActiveTab('faturas') }}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Compras */}
        <TabsContent value="compras" className="space-y-3">
          {purchases?.length === 0 ? (
            <Card>
              <EmptyState
                icon={<CreditCard className="size-6" />}
                title="Nenhuma compra registrada"
                description="Registre sua primeira compra no cartão."
                action={<Button size="sm" onClick={() => setNewPurchaseOpen(true)}><Plus /> Nova compra</Button>}
              />
            </Card>
          ) : (
            <div className="space-y-2">
              {purchases?.map((purchase) => (
                <PurchaseCard key={purchase.id} purchase={purchase} />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Parcelas */}
        <TabsContent value="parcelas" className="space-y-3">
          {upcoming?.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Calendar className="size-6" />}
                title="Nenhuma parcela futura"
                description="Compras parceladas aparecerão aqui com suas datas de vencimento."
              />
            </Card>
          ) : (
            <UpcomingInstallments installments={upcoming as any} limit={20} />
          )}
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <NewPurchaseDialog open={newPurchaseOpen} onOpenChange={setNewPurchaseOpen} cardId={id} onSuccess={() => {}} />
      <PayStatementDialog open={payStatementOpen} onOpenChange={setPayStatementOpen} statement={currentStatement || null} onSuccess={() => { setPayStatementOpen(false); setSelectedStatement(null) }} />
    </div>
  )
}

interface StatementCardProps {
  statement: {
    id: string
    cycle_start_date: string
    cycle_end_exclusive: string
    due_date: string
    status: string
    paid_cents: number
    total_cents: number
  }
  onClick: () => void
  onViewDetail: () => void
}

function StatementCard({ statement, onClick, onViewDetail }: StatementCardProps) {
  const cfg = STATUS_CONFIG[statement.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.OPEN
  const Icon = cfg.icon
  const due = statement.total_cents - statement.paid_cents
  const isOverdue = statement.status === 'OVERDUE'

  return (
    <Card className="group hover:border-border hover:bg-surface-2/50 transition-colors cursor-pointer" onClick={onViewDetail}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className={cn('grid size-10 place-items-center rounded-xl', cfg.color.replace('text-', 'bg-').replace('bg-', 'bg-'))} aria-hidden>
              <Icon className="size-5" aria-hidden />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-fg">
                  {new Date(statement.cycle_start_date).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}
                </p>
                <Badge variant="outline" className={cn('text-xs', cfg.color)}>
                  {cfg.label}
                </Badge>
              </div>
              <p className="text-xs text-muted flex items-center gap-1 mt-0.5">
                <Calendar className="size-3" aria-hidden />
                Vence em {new Date(statement.due_date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })}
                {isOverdue && <span className="text-negative">· VENCIDA</span>}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-1 shrink-0">
            <div className="text-right">
              <p className="text-xs text-muted">Total da fatura</p>
              <CurrencyDisplay cents={statement.total_cents} className="text-lg font-semibold" />
            </div>
            {due > 0 && (
              <div className="text-right">
                <p className="text-xs text-muted">Saldo devedor</p>
                <CurrencyDisplay cents={due} className="text-lg font-semibold text-negative" />
              </div>
            )}
            {statement.paid_cents > 0 && (
              <div className="text-right">
                <p className="text-xs text-muted">Já pago</p>
                <CurrencyDisplay cents={statement.paid_cents} className="text-sm font-medium text-positive" />
              </div>
            )}
          </div>
        </div>

        {due > 0 && statement.status !== 'PAID' && statement.status !== 'CANCELLED' && (
          <div className="mt-3 pt-3 border-t border-border flex items-center justify-end">
            <Button size="sm" onClick={(e) => { e.stopPropagation(); onClick() }} variant={isOverdue ? 'danger' : 'primary'}>
              {isOverdue ? <AlertTriangle className="size-3.5 mr-1" /> : <Calendar className="size-3.5 mr-1" />}
              {isOverdue ? 'Pagar fatura vencida' : 'Pagar fatura'}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface PurchaseCardProps {
  purchase: {
    id: string
    description: string
    merchant: string | null
    purchased_on: string
    total_cents: number
    installments_count: number
    category_name: string | null
    category_color: string | null
    status: string
    created_at: string
  }
}

function PurchaseCard({ purchase }: PurchaseCardProps) {
  return (
    <Card className="group hover:border-border hover:bg-surface-2/50 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0 flex items-center gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent" aria-hidden>
              <CreditCard className="size-5" />
            </div>
            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-fg truncate">{purchase.description}</p>
                {purchase.category_name && (
                  <span style={{ borderColor: purchase.category_color ?? undefined, color: purchase.category_color ?? undefined }}>
                    <Badge variant="outline" className="text-xs">
                      {purchase.category_name}
                    </Badge>
                  </span>
                )}
                {purchase.merchant && (
                  <span className="text-xs text-muted/70 px-2 py-0.5 rounded bg-surface-2">{purchase.merchant}</span>
                )}
              </div>
              <p className="text-xs text-muted flex items-center gap-1">
                <Calendar className="size-3" aria-hidden />
                {formatRelativeDate(purchase.purchased_on)}
                <span>·</span>
                {purchase.installments_count === 1 ? 'À vista' : `${purchase.installments_count}x`}
              </p>
            </div>
          </div>
          <CurrencyDisplay cents={purchase.total_cents} className="shrink-0 text-lg font-semibold" />
        </div>
      </CardContent>
    </Card>
  )
}

function CardSkeleton() {
  return (
    <Card>
      <CardContent className="p-5">
        <Skeleton className="h-8 w-1/4" />
        <Skeleton className="h-2 w-full mt-4 rounded-full" />
      </CardContent>
    </Card>
  )
}