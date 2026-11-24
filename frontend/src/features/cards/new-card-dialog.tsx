import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAccounts } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { CurrencyInput } from '@/components/finance/currency'
import { Tooltip } from '@/components/ui/misc'
import { Info } from 'lucide-react'
import type { CreditCard } from '@/types/api'

interface NewCardDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cardToEdit?: CreditCard | null
  onSuccess?: () => void
}

const CARD_TYPES = ['CREDIT', 'DEBIT', 'PREPAID'] as const
const CARD_BRANDS = ['VISA', 'MASTERCARD', 'ELO', 'AMEX', 'HIPERCARD', 'OTHER'] as const
const BOUNDARY_POLICIES = ['INCLUSIVE', 'EXCLUSIVE'] as const

export function NewCardDialog({ open, onOpenChange, cardToEdit, onSuccess }: NewCardDialogProps) {
  const isEditing = !!cardToEdit
  const [form, setForm] = useState({
    name: '',
    bank: '',
    nickname: '',
    last_four: '',
    brand: 'VISA' as typeof CARD_BRANDS[number],
    type: 'CREDIT' as typeof CARD_TYPES[number],
    limit_cents: '',
    closing_day: 10,
    due_day: 5,
    due_month_offset: 1,
    purchase_boundary_policy: 'EXCLUSIVE' as typeof BOUNDARY_POLICIES[number],
    default_payment_account_id: '',
    color: '#3B82F6',
    notes: '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const accounts = useAccounts(true) // include archived to show all for payment account selection

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<CreditCard>(isEditing ? `/cards/${cardToEdit!.id}` : '/cards', {
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
      bank: form.bank || undefined,
      nickname: form.nickname || undefined,
      last_four: form.last_four || undefined,
      brand: form.brand,
      type: form.type,
      limit_cents: parseInt(form.limit_cents.replace(/\D/g, ''), 10),
      closing_day: form.closing_day,
      due_day: form.due_day,
      due_month_offset: form.due_month_offset,
      purchase_boundary_policy: form.purchase_boundary_policy,
      default_payment_account_id: form.default_payment_account_id || undefined,
      color: form.color,
      notes: form.notes || undefined,
    }

    mutation.mutate(payload)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? 'Editar cartão' : 'Novo cartão'}
      description={isEditing ? 'Altere os dados do cartão.' : 'Cadastre um novo cartão de crédito.'}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome do cartão *" error={errors.name}>
            {(props) => (
              <Input
                {...props}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Nubank, Itaú, C6"
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Banco" error={errors.bank}>
            {(props) => (
              <Input
                {...props}
                value={form.bank}
                onChange={(e) => setForm({ ...form, bank: e.target.value })}
                placeholder="Ex: Nubank, Itaú, Bradesco"
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Apelido" error={errors.nickname}>
            {(props) => (
              <Input
                {...props}
                value={form.nickname}
                onChange={(e) => setForm({ ...form, nickname: e.target.value })}
                placeholder="Ex: Pessoal, Trabalho"
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Últimos 4 dígitos" error={errors.last_four}>
            {(props) => (
              <Input
                {...props}
                value={form.last_four}
                onChange={(e) => setForm({ ...form, last_four: e.target.value.replace(/\D/g, '').slice(0, 4) })}
                placeholder="1234"
                maxLength={4}
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Bandeira" error={errors.brand}>
            {(props) => (
              <Select
                {...props}
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value as typeof CARD_BRANDS[number] })}
                disabled={mutation.isPending}
              >
                {CARD_BRANDS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Tipo" error={errors.type}>
            {(props) => (
              <Select
                {...props}
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as typeof CARD_TYPES[number] })}
                disabled={mutation.isPending}
              >
                {CARD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field
            label="Limite *"
            error={errors.limit_cents}
            hint="Limite total do cartão em centavos (ex: 500000 = R$ 5.000,00)"
          >
            {(props) => (
              <CurrencyInput
                {...props}
                valueCents={form.limit_cents ? parseInt(form.limit_cents, 10) : null}
                onChangeCents={(v) => setForm({ ...form, limit_cents: v ? String(v) : '' })}
                placeholder="500000"
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

        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            label="Dia do fechamento *"
            error={errors.closing_day}
            hint="Dia do mês em que a fatura fecha (1-28)"
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                value={form.closing_day}
                onChange={(e) => setForm({ ...form, closing_day: Math.min(28, Math.max(1, parseInt(e.target.value) || 1)) })}
                min={1}
                max={28}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field
            label="Dia do vencimento *"
            error={errors.due_day}
            hint="Dia do mês em que a fatura vence (1-28)"
          >
            {(props) => (
              <Input
                {...props}
                type="number"
                value={form.due_day}
                onChange={(e) => setForm({ ...form, due_day: Math.min(28, Math.max(1, parseInt(e.target.value) || 1)) })}
                min={1}
                max={28}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field
            label="Vencimento"
            error={errors.due_month_offset}
            hint="0 = mesmo mês do fechamento, 1 = mês seguinte"
          >
            {(props) => (
              <Select
                {...props}
                value={form.due_month_offset}
                onChange={(e) => setForm({ ...form, due_month_offset: parseInt(e.target.value, 10) })}
                disabled={mutation.isPending}
              >
                <option value={0}>Mês do fechamento (0)</option>
                <option value={1}>Mês seguinte (1)</option>
              </Select>
            )}
          </Field>
        </div>

        <Field
          label="Regra do dia do fechamento"
          error={errors.purchase_boundary_policy}
        >
          {(props) => (
            <div className="flex items-center gap-3">
              <Select
                {...props}
                value={form.purchase_boundary_policy}
                onChange={(e) => setForm({ ...form, purchase_boundary_policy: e.target.value as typeof BOUNDARY_POLICIES[number] })}
                className="w-44"
                disabled={mutation.isPending}
              >
                <option value="EXCLUSIVE">Exclusivo (compra no dia entra na próxima)</option>
                <option value="INCLUSIVE">Inclusivo (compra no dia entra na atual)</option>
              </Select>
              <Tooltip content="Define se uma compra feita no dia do fechamento entra na fatura atual ou na próxima.">
                <button type="button" className="text-muted/70 hover:text-fg" aria-label="Ajuda">
                  <Info className="size-4" />
                </button>
              </Tooltip>
            </div>
          )}
        </Field>

        <Field
          label="Conta padrão para pagamento"
          error={errors.default_payment_account_id}
          hint="Conta bancária usada por padrão ao pagar a fatura"
        >
          {(props) => (
            <Select
              {...props}
              value={form.default_payment_account_id}
              onChange={(e) => setForm({ ...form, default_payment_account_id: e.target.value })}
              disabled={mutation.isPending}
            >
              <option value="">— Selecione —</option>
              {accounts.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.type})
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Observações" error={errors.notes}>
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Notas internas sobre este cartão"
              rows={3}
              disabled={mutation.isPending}
            />
          )}
        </Field>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            {mutation.isPending ? 'Salvando…' : isEditing ? 'Salvar alterações' : 'Cadastrar cartão'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}