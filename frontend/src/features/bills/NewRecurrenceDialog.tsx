import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import type { Recurrence } from '@/types/api'

const FREQUENCIES = [
  'MONTHLY',
  'BIMONTHLY',
  'QUARTERLY',
  'SEMIANNUAL',
  'ANNUAL',
  'CUSTOM',
] as const

const FREQUENCY_LABELS: Record<string, string> = {
  MONTHLY: 'Mensal',
  BIMONTHLY: 'Bimestral (a cada 2 meses)',
  QUARTERLY: 'Trimestral (a cada 3 meses)',
  SEMIANNUAL: 'Semestral (a cada 6 meses)',
  ANNUAL: 'Anual',
  CUSTOM: 'Personalizado (intervalo em meses)',
}

type RecurrenceStatus = 'ACTIVE' | 'PAUSED' | 'ENDED'

interface NewRecurrenceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  billId: string
  billName: string
  recurrenceToEdit?: Recurrence | null
  onSuccess?: () => void
}

export function NewRecurrenceDialog({
  open,
  onOpenChange,
  billId,
  billName,
  recurrenceToEdit,
  onSuccess,
}: NewRecurrenceDialogProps) {
  const isEditing = !!recurrenceToEdit
  const [form, setForm] = useState({
    frequency: 'MONTHLY' as typeof FREQUENCIES[number],
    day_of_month: 10,
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    custom_months_interval: '',
    auto_post: true,
    status: 'ACTIVE' as RecurrenceStatus,
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [showCustomInterval, setShowCustomInterval] = useState(false)

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Recurrence>(isEditing ? `/bills/recurrences/${recurrenceToEdit!.id}` : '/bills/recurrences', {
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
      bill_id: billId,
      frequency: form.frequency,
      day_of_month: form.day_of_month,
      start_date: form.start_date,
      end_date: form.end_date || undefined,
      auto_post: form.auto_post,
      status: form.status,
      notes: form.notes || undefined,
    }

    if (form.frequency === 'CUSTOM') {
      payload.custom_months_interval = parseInt(form.custom_months_interval, 10)
    }

    mutation.mutate(payload)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? 'Editar recorrência' : 'Nova recorrência'}
      description={
        isEditing
          ? `Altere a recorrência para ${billName}.`
          : `Configure a recorrência automática de parcelas para ${billName}.`
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Frequência *" error={errors.frequency}>
            {(props) => (
              <Select
                {...props}
                value={form.frequency}
                onChange={(e) => {
                  const val = e.target.value as typeof FREQUENCIES[number]
                  setForm({ ...form, frequency: val })
                  setShowCustomInterval(val === 'CUSTOM')
                }}
                disabled={mutation.isPending}
              >
                {FREQUENCIES.map((f) => (
                  <option key={f} value={f}>
                    {FREQUENCY_LABELS[f]}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Dia do vencimento *" error={errors.day_of_month} hint="Dia do mês (1-31). Meses sem esse dia usam o último dia.">
            {(props) => (
              <Input
                {...props}
                type="number"
                value={form.day_of_month}
                onChange={(e) => setForm({ ...form, day_of_month: Math.min(31, Math.max(1, parseInt(e.target.value) || 1)) })}
                min={1}
                max={31}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        {showCustomInterval && (
          <Field label="Intervalo em meses *" error={errors.custom_months_interval} hint="Ex: 4 = a cada 4 meses">
            {(props) => (
              <Input
                {...props}
                type="number"
                value={form.custom_months_interval}
                onChange={(e) => setForm({ ...form, custom_months_interval: e.target.value })}
                min={1}
                max={24}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Data de início *" error={errors.start_date}>
            {(props) => (
              <Input
                {...props}
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Data de fim" error={errors.end_date} hint="Opcional. Deixe vazio para recorrência indefinida.">
            {(props) => (
              <Input
                {...props}
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Status *" error={errors.status}>
            {(props) => (
              <Select
                {...props}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as RecurrenceStatus })}
                disabled={mutation.isPending}
              >
                <option value="ACTIVE">Ativa</option>
                <option value="PAUSED">Pausada</option>
                <option value="ENDED">Encerrada</option>
              </Select>
            )}
          </Field>

          <Field label="Postagem automática" error={errors.auto_post}>
            {(props) => (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  {...props}
                  checked={form.auto_post}
                  onChange={(e) => setForm({ ...form, auto_post: e.target.checked })}
                  className="size-4 rounded border-border text-accent focus:ring-accent/20"
                  disabled={mutation.isPending}
                />
                <label className="text-sm text-fg cursor-pointer">Gerar parcelas automaticamente</label>
              </div>
            )}
          </Field>
        </div>

        <Field label="Observações" error={errors.notes}>
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Notas internas sobre esta recorrência"
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
            {mutation.isPending ? 'Salvando…' : isEditing ? 'Salvar alterações' : 'Criar recorrência'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}