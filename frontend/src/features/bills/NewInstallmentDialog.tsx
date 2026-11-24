import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { CurrencyInput } from '@/components/finance/currency'
import type { BillInstallment, Bill, Recurrence } from '@/types/api'

interface NewInstallmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  bill: Bill
  recurrence?: Recurrence | null
  installmentToEdit?: BillInstallment | null
  onSuccess?: () => void
}

const STATUSES = ['PENDING', 'POSTED', 'PAID', 'REVERSED', 'CANCELLED', 'SKIPPED'] as const

export function NewInstallmentDialog({
  open,
  onOpenChange,
  bill,
  recurrence,
  installmentToEdit,
  onSuccess,
}: NewInstallmentDialogProps) {
  const isEditing = !!installmentToEdit
  const [form, setForm] = useState({
    due_date: new Date().toISOString().split('T')[0],
    amount_cents: '',
    status: 'PENDING' as typeof STATUSES[number],
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<BillInstallment>(isEditing ? `/bills/installments/${installmentToEdit!.id}` : '/bills/installments', {
        method: isEditing ? 'PATCH' : 'POST',
        body,
      }),
    onSuccess: () => {
      onOpenChange(false)
      onSuccess?.()
    },
    onError: (err: Error & { code?: string; details?: unknown }) => {
      if (err.code === 'validation_error' && err.details) {
        setErrors(err.details as Record<string, string>)
      }
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})

    const payload: Record<string, unknown> = {
      bill_id: bill.id,
      due_date: form.due_date,
      amount_cents: parseInt(form.amount_cents.replace(/\D/g, ''), 10),
      status: form.status,
      notes: form.notes || undefined,
    }

    if (recurrence) {
      payload.recurrence_id = recurrence.id
    }

    mutation.mutate(payload)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? 'Editar parcela' : 'Nova parcela manual'}
      description={
        isEditing
          ? `Altere a parcela de ${bill.name}.`
          : `Crie uma parcela avulsa para ${bill.name}${recurrence ? ` (recorrência: ${recurrence.frequency})` : ''}.`
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Data de vencimento *" error={errors.due_date}>
            {(props) => (
              <Input
                {...props}
                type="date"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Valor *" error={errors.amount_cents} hint="Valor em centavos (ex: 15000 = R$ 150,00)">
            {(props) => (
              <CurrencyInput
                {...props}
                valueCents={form.amount_cents ? parseInt(form.amount_cents, 10) : (bill.default_amount_cents || null)}
                onChangeCents={(v) => setForm({ ...form, amount_cents: v ? String(v) : '' })}
                placeholder={bill.default_amount_cents ? String(bill.default_amount_cents) : '15000'}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        {!isEditing && (
          <Field label="Status" error={errors.status}>
            {(props) => (
              <Select
                {...props}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as typeof STATUSES[number] })}
                disabled={mutation.isPending}
              >
                <option value="PENDING">Pendente</option>
                <option value="POSTED">Postada</option>
                <option value="PAID">Paga</option>
                <option value="REVERSED">Estornada</option>
                <option value="CANCELLED">Cancelada</option>
                <option value="SKIPPED">Pulada</option>
              </Select>
            )}
          </Field>
        )}

        <Field label="Observações" error={errors.notes}>
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Notas sobre esta parcela (ex: ID de idempotência, motivo, etc.)"
              rows={2}
              disabled={mutation.isPending}
            />
          )}
        </Field>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            {mutation.isPending ? 'Salvando…' : isEditing ? 'Salvar alterações' : 'Criar parcela'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}