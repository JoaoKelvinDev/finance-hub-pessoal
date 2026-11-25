import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAccounts } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { CurrencyInput } from '@/components/finance/currency'
import type { Bill } from '@/types/api'

const BILL_CATEGORIES = [
  'RENT',
  'WATER',
  'ELECTRICITY',
  'GAS',
  'INTERNET',
  'PHONE',
  'TV',
  'INSURANCE',
  'CONDO',
  'EDUCATION',
  'HEALTH',
  'OTHER',
] as const

const CATEGORY_LABELS: Record<string, string> = {
  RENT: 'Aluguel / Condomínio',
  WATER: 'Água / Esgoto',
  ELECTRICITY: 'Energia elétrica',
  GAS: 'Gás',
  INTERNET: 'Internet / TV a cabo',
  PHONE: 'Telefone / Celular',
  TV: 'Streaming / TV',
  INSURANCE: 'Seguros',
  CONDO: 'Condomínio',
  EDUCATION: 'Educação',
  HEALTH: 'Saúde / Planos',
  OTHER: 'Outros',
}

interface NewBillDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  billToEdit?: Bill | null
  onSuccess?: () => void
}

export function NewBillDialog({ open, onOpenChange, billToEdit, onSuccess }: NewBillDialogProps) {
  const isEditing = !!billToEdit
  const [form, setForm] = useState({
    name: '',
    category: 'INTERNET' as typeof BILL_CATEGORIES[number],
    description: '',
    account_id: '',
    default_amount_cents: '',
    variable_amount: false,
    color: '#EF4444',
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const accounts = useAccounts(true)

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Bill>(isEditing ? `/bills/${billToEdit!.id}` : '/bills', {
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

    const payload = {
      name: form.name,
      category: form.category,
      description: form.description || undefined,
      account_id: form.account_id,
      default_amount_cents: parseInt(form.default_amount_cents.replace(/\D/g, ''), 10),
      variable_amount: form.variable_amount,
      color: form.color,
      notes: form.notes || undefined,
    }

    mutation.mutate(payload)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? 'Editar conta da casa' : 'Nova conta da casa'}
      description={isEditing ? 'Altere os dados da conta.' : 'Cadastre uma nova conta recorrente da casa (aluguel, água, internet, etc.).'}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome da conta *" error={errors.name}>
            {(props) => (
              <Input
                {...props}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Aluguel, Internet, Água"
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Categoria *" error={errors.category}>
            {(props) => (
              <Select
                {...props}
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value as typeof BILL_CATEGORIES[number] })}
                disabled={mutation.isPending}
              >
                {BILL_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABELS[c]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Conta bancária *" error={errors.account_id}>
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
                    {a.name} ({a.type})
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Valor padrão *" error={errors.default_amount_cents} hint={form.variable_amount ? 'Use a média dos últimos meses; vira estimativa até você informar o real.' : 'Valor cobrado todo período.'}>
            {(props) => (
              <CurrencyInput
                {...props}
                valueCents={form.default_amount_cents ? parseInt(form.default_amount_cents, 10) : null}
                onChangeCents={(v) => setForm({ ...form, default_amount_cents: v ? String(v) : '' })}
                placeholder="15000"
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Cor" error={errors.color}>
            {(props) => (
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  {...props}
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  className="size-10 rounded-lg border border-border cursor-pointer"
                  disabled={mutation.isPending}
                />
                <Input
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  disabled={mutation.isPending}
                />
              </div>
            )}
          </Field>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 hover:bg-surface-2">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-[var(--color-accent)]"
            checked={form.variable_amount}
            onChange={(e) => setForm({ ...form, variable_amount: e.target.checked })}
            disabled={mutation.isPending}
          />
          <span>
            <span className="block text-sm font-medium">Valor varia todo mês</span>
            <span className="block text-xs text-muted">
              Luz, água, gás… As parcelas nascem como estimativa e você confirma o valor real quando a conta chegar.
            </span>
          </span>
        </label>

        <Field label="Descrição" error={errors.description}>
          {(props) => (
            <Textarea
              {...props}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Detalhes opcionais (ex: nome do condomínio, operadora, etc.)"
              rows={3}
              disabled={mutation.isPending}
            />
          )}
        </Field>

        <Field label="Observações internas" error={errors.notes}>
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Notas para sua referência"
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
            {mutation.isPending ? 'Salvando…' : isEditing ? 'Salvar alterações' : 'Cadastrar conta'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}