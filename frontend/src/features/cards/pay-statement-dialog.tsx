import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Calendar } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, ApiError } from '@/lib/api'
import { formatBRL } from '@/lib/money'
import { useAccounts, useCards } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select } from '@/components/ui/field'
import { CurrencyInput, CurrencyDisplay } from '@/components/finance/currency'
import type { CardStatement } from '@/types/api'
import { formatDate, formatMonthLong, todayISO } from '@/lib/date'
import { cn, newIdempotencyKey } from '@/lib/utils'

interface PayStatementDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  statement: CardStatement | null
  onSuccess?: () => void
}

export function PayStatementDialog({ open, onOpenChange, statement, onSuccess }: PayStatementDialogProps) {
  const [form, setForm] = useState(() => ({
    account_id: '',
    amount_cents: '',
    paid_on: todayISO(),
  }))
  const [errors, setErrors] = useState<Record<string, string>>({})

  const accounts = useAccounts(false)
  const cards = useCards(true) // include archived to find card for statement

  const card = statement ? cards.data?.find((c) => c.id === statement.card_id) : null
  const total = statement?.total_cents ?? 0
  const paid = statement?.paid_cents ?? 0
  const due = total - paid

  // Obrigatória na API: sem ela o pagamento era sempre recusado (e o erro não aparecia).
  // A mesma chave vale para repetições do mesmo envio (clique duplo); renova a cada abertura.
  const idemKey = useRef(newIdempotencyKey())
  useEffect(() => {
    if (open) idemKey.current = newIdempotencyKey()
  }, [open])

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(`/cards/statements/${statement!.id}/payments`, { method: 'POST', body }),
    onSuccess: (_data, body) => {
      toast.success(`Pagamento de ${formatBRL(body.amount_cents as number)} registrado.`)
      onOpenChange(false)
      onSuccess?.()
    },
    onError: (err: Error & { code?: string; details?: unknown }) => {
      if (err.code === 'validation_error' && err.details) {
        setErrors(err.details as Record<string, string>)
      }
      toast.error(err instanceof ApiError ? err.message : 'Não foi possível registrar o pagamento.')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})

    const payload = {
      statement_id: statement!.id,
      account_id: form.account_id,
      amount_cents: parseInt(form.amount_cents.replace(/\D/g, ''), 10),
      paid_on: form.paid_on,
      idempotency_key: idemKey.current,
    }

    mutation.mutate(payload)
  }

  const selectedAccount = accounts.data?.find((a) => a.id === form.account_id)
  const accountBalance = selectedAccount?.balance_cents ?? 0
  const willOverdraft = parseInt(form.amount_cents.replace(/\D/g, ''), 10) > accountBalance

  if (!statement) return null

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Pagar fatura"
      description={`Fatura de ${card?.name ?? 'cartão'} — ${formatMonthLong(statement.cycle_start_date)}`}
    >
      <div className="space-y-4">
        {/* Resumo da fatura */}
        <div className="rounded-lg border border-border bg-surface-2/50 p-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <p className="text-xs text-muted">Total da fatura</p>
              <CurrencyDisplay cents={total} className="text-lg font-semibold" />
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted">Já pago</p>
              <CurrencyDisplay cents={paid} className="text-lg font-semibold text-positive" />
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted">Saldo devedor</p>
              <CurrencyDisplay cents={due} className="text-lg font-semibold text-negative" />
            </div>
          </div>
          <p className="mt-3 text-xs text-muted flex items-center gap-1">
            <Calendar className="size-3" aria-hidden />
            Vencimento: {formatDate(statement.due_date)}
            {statement.status === 'OVERDUE' && <span className="ml-2 text-negative flex items-center gap-1"><AlertTriangle className="size-3" /> Vencida</span>}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Field label="Conta para débito *" error={errors.account_id}>
            {(props) => (
              <Select
                {...props}
                value={form.account_id}
                onChange={(e) => setForm({ ...form, account_id: e.target.value })}
                required
                disabled={mutation.isPending}
              >
                <option value="">— Selecione a conta —</option>
                {accounts.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.type}) — {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(a.balance_cents / 100)}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Valor do pagamento *"
              error={errors.amount_cents}
              hint={willOverdraft ? '⚠️ Valor excede o saldo da conta' : `Máximo: ${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(due / 100)}`}
            >
              {(props) => (
                <CurrencyInput
                  {...props}
                  valueCents={form.amount_cents ? parseInt(form.amount_cents, 10) : null}
                  onChangeCents={(v) => setForm({ ...form, amount_cents: v ? String(v) : '' })}
                  placeholder={new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(due / 100)}
                  required
                  disabled={mutation.isPending}
                />
              )}
            </Field>

            <Field
              label="Data do pagamento *"
              error={errors.paid_on}
              hint="Data em que o pagamento foi/sairá da conta"
            >
              {(props) => (
                <Input
                  {...props}
                  type="date"
                  value={form.paid_on}
                  onChange={(e) => setForm({ ...form, paid_on: e.target.value })}
                  required
                  disabled={mutation.isPending}
                />
              )}
            </Field>
          </div>

          {selectedAccount && (
            <div className={cn('rounded-lg border p-3 text-sm', willOverdraft ? 'border-negative/30 bg-negative/5' : 'border-border bg-surface-2/50')}>
              <div className="flex items-center justify-between">
                <span className="text-muted">Saldo após pagamento (estimado)</span>
                <CurrencyDisplay
                  cents={accountBalance - parseInt(form.amount_cents.replace(/\D/g, ''), 10)}
                  className={cn('font-semibold', willOverdraft && 'text-negative')}
                />
              </div>
              {willOverdraft && (
                <p className="mt-1 text-xs text-negative flex items-center gap-1">
                  <AlertTriangle className="size-3" />
                  O pagamento deixará a conta com saldo negativo. Confirme se deseja prosseguir.
                </p>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
              Cancelar
            </Button>
            <Button type="submit" loading={mutation.isPending}>
              {mutation.isPending ? 'Processando…' : 'Confirmar pagamento'}
            </Button>
          </div>
        </form>
      </div>
    </Dialog>
  )
}