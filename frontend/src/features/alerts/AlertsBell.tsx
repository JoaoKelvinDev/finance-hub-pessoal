import { Popover } from 'radix-ui'
import { AlertTriangle, Bell, BellOff, CircleAlert, Info, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/misc'
import { CurrencyDisplay } from '@/components/finance/currency'
import { formatDate } from '@/lib/date'
import { useAlerts, useDismissAlert } from '@/lib/queries'
import { cn } from '@/lib/utils'
import type { AlertKind, AppAlert } from '@/types/api'

const SEVERITY: Record<AppAlert['severity'], { label: string; icon: typeof Info; cls: string }> = {
  danger: { label: 'Urgente', icon: AlertTriangle, cls: 'text-negative' },
  warning: { label: 'Atenção', icon: CircleAlert, cls: 'text-warning' },
  info: { label: 'Informativo', icon: Info, cls: 'text-muted' },
}

const KIND_LABEL: Record<AlertKind, string> = {
  DUE_SOON: 'Vence em breve',
  DUE_TODAY: 'Vence hoje',
  OVERDUE: 'Vencido',
  RECEIVABLE_OVERDUE: 'Recebível vencido',
  CARD_UTILIZATION: 'Limite do cartão',
  ESTIMATE_PENDING: 'Valor a confirmar',
}

/** Sino de alertas: mostra o que precisa de atenção agora e leva direto à tela do item. */
export function AlertsBell() {
  const alerts = useAlerts()
  const dismiss = useDismissAlert()
  const navigate = useNavigate()

  const items = alerts.data?.items ?? []
  const counts = alerts.data?.counts
  const total = counts?.total ?? 0
  const badge = total > 0 ? (counts?.danger ? counts.danger : total) : 0

  return (
    <Popover.Root>
      <Tooltip content={total > 0 ? `${total} alerta(s)` : 'Nenhum alerta'}>
        <Popover.Trigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Alertas${total > 0 ? `: ${total} pendente(s)` : ''}`}>
            <span className="relative">
              <Bell className="size-[18px]" />
              {badge > 0 && (
                <span
                  className="absolute -top-1 -right-1 grid min-w-4 place-items-center rounded-full bg-negative px-1 text-[10px] font-semibold text-bg"
                  aria-hidden
                >
                  {badge > 9 ? '9+' : badge}
                </span>
              )}
            </span>
          </Button>
        </Popover.Trigger>
      </Tooltip>

      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          align="end"
          className="z-50 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-border bg-surface shadow-pop focus:outline-none"
        >
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold tracking-tight">Alertas</h2>
            {total > 0 && (
              <span className="text-xs text-muted">
                {counts?.danger ?? 0} urgente(s) · {counts?.warning ?? 0} atenção · {counts?.info ?? 0} info
              </span>
            )}
          </header>

          <div className="max-h-[60vh] overflow-y-auto">
            {alerts.isLoading && !items.length && (
              <div className="space-y-2 p-4" aria-busy="true">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="shimmer h-12 rounded-lg" />
                ))}
              </div>
            )}

            {alerts.isError && (
              <div className="p-4 text-sm">
                <p className="text-negative">Não foi possível carregar os alertas.</p>
                <Button variant="secondary" size="sm" className="mt-2" onClick={() => alerts.refetch()}>
                  Tentar novamente
                </Button>
              </div>
            )}

            {!alerts.isLoading && !alerts.isError && !items.length && (
              <div className="px-4 py-8 text-center">
                <BellOff className="mx-auto mb-2 size-8 text-muted/50" aria-hidden />
                <p className="text-sm text-muted">Nada pendente. Seus contas, cartões e recebíveis estão em dia.</p>
              </div>
            )}

            <ul className="divide-y divide-border">
              {items.map((a) => {
                const sev = SEVERITY[a.severity]
                const Icon = sev.icon
                return (
                  <li key={a.key} className="group relative flex items-start gap-3 px-4 py-3">
                    <Icon className={cn('mt-0.5 size-4 shrink-0', sev.cls)} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] leading-tight font-medium">
                        <span className={cn('mr-1.5 font-semibold', sev.cls)}>[{sev.label}]</span>
                        {a.title}
                      </p>
                      <p className="mt-1 text-xs text-muted">{a.message}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-muted">
                        <span>{KIND_LABEL[a.kind]}</span>
                        {a.date && <span>· {formatDate(a.date)}</span>}
                        {a.amount_cents != null && (
                          <span>· <CurrencyDisplay cents={a.amount_cents} animated={false} className="inline" /></span>
                        )}
                      </p>
                      {a.link && (
                        <button
                          onClick={() => navigate(a.link)}
                          className="mt-1.5 text-xs font-medium text-accent hover:underline"
                        >
                          Ver item →
                        </button>
                      )}
                    </div>
                    <button
                      onClick={() =>
                        dismiss.mutate(a.key, {
                          onSuccess: () => toast.success('Alerta dispensado.'),
                          onError: () => toast.error('Não foi possível dispensar o alerta.'),
                        })
                      }
                      className="rounded-lg p-1 text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-surface-2 hover:text-fg focus-visible:opacity-100"
                      aria-label={`Dispensar alerta: ${a.title}`}
                      title="Dispensar"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>

          <footer className="border-t border-border px-4 py-2">
            <p className="text-[11px] text-muted">
              Alertas são calculados na hora a partir do calendário. Dispensar esconde até o alerta mudar de estágio.
            </p>
          </footer>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
