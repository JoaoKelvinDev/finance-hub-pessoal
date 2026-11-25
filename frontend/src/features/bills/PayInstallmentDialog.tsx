import { useState } from 'react'
import { toast } from 'sonner'
import { useAccounts, usePayBillInstallment } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select } from '@/components/ui/field'
import { CurrencyDisplay, CurrencyInput } from '@/components/finance/currency'
import { formatDate, todayISO } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import type { BillInstallment, Account } from '@/types/api'

interface PayInstallmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  installment: BillInstallment | null
  onSuccess?: () => void
}

export function PayInstallmentDialog({ open, onOpenChange, installment, onSuccess }: PayInstallmentDialogProps) {
  const [form, setForm] = useState({
    account_id: '',
    paid_on: todayISO(),
    amount_cents: '',
    idempotency_key: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const accounts = useAccounts()
  const mutation = usePayBillInstallment()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})
    if (!form.account_id) {
      setErrors({ account_id: 'Selecione a conta de pagamento.' })
      return
    }

    const typed = parseInt(form.amount_cents.replace(/\D/g, ''), 10)
    mutation.mutate(
      {
        installmentId: installment!.id,
        account_id: form.account_id,
        paid_on: form.paid_on,
        // Campo vazio = valor da parcela (padrão do backend).
        ...(Number.isFinite(typed) && typed > 0 ? { amount_cents: typed } : {}),
        ...(form.idempotency_key ? { idempotency_key: form.idempotency_key } : {}),
      },
      {
        onSuccess: () => {
          toast.success('Pagamento registrado.')
          onOpenChange(false)
          onSuccess?.()
        },
        onError: (err: Error & { code?: string; details?: unknown }) => {
          if (err.code === 'validation_error' && Array.isArray(err.details)) {
            setErrors(
              Object.fromEntries((err.details as { field: string; message: string }[]).map((d) => [d.field, d.message])),
            )
          } else {
            toast.error(err.message || 'Não foi possível registrar o pagamento.')
          }
        },
      },
    )
  }

  if (!installment) return null

  const defaultAmount = installment.amount_cents

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Pagar parcela"
      description={`Registrar pagamento da parcela de ${installment.bill_name ?? 'conta'} vencida em ${formatDate(installment.due_date)}.`}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="space-y-2 text-sm text-muted">
          <p><strong>Conta:</strong> {installment.bill_name}</p>
          <p><strong>Vencimento:</strong> {formatDate(installment.due_date)}</p>
          <p><strong>Valor da parcela:</strong> <CurrencyDisplay cents={installment.amount_cents} className="inline font-medium" /></p>
        </div>

        <Field label="Conta de pagamento *" error={errors.account_id}>
          {(props) => (
            <Select
              {...props}
              value={form.account_id}
              onChange={(e) => setForm({ ...form, account_id: e.target.value })}
              required
              disabled={mutation.isPending}
            >
              <option value="">— Selecione a conta —</option>
              {accounts.data?.map((a: Account) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.type}) · {formatBRL(a.balance_cents)}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Data do pagamento *" error={errors.paid_on}>
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

          <Field label="Valor pago *" error={errors.amount_cents} hint={defaultAmount > 0 ? `Padrão: ${formatBRL(defaultAmount)}` : undefined}>
            {(props) => (
              <CurrencyInput
                {...props}
                valueCents={form.amount_cents ? parseInt(form.amount_cents, 10) : defaultAmount}
                onChangeCents={(v) => setForm({ ...form, amount_cents: v ? String(v) : '' })}
                placeholder={defaultAmount ? String(defaultAmount) : '15000'}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        <Field label="Chave de idempotência" error={errors.idempotency_key} hint="Opcional. Use para evitar pagamentos duplicados em retentativas.">
          {(props) => (
            <Input
              {...props}
              value={form.idempotency_key}
              onChange={(e) => setForm({ ...form, idempotency_key: e.target.value })}
              placeholder="Ex: pay-bill-123-2024-01"
              maxLength={100}
              disabled={mutation.isPending}
            />
          )}
        </Field>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            {mutation.isPending ? 'Processando…' : 'Confirmar pagamento'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}