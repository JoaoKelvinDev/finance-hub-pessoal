import { useEffect, useRef, useState } from 'react'
import { CreditCard, Minus, Plus } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, ApiError } from '@/lib/api'
import { formatBRL } from '@/lib/money'
import { newIdempotencyKey } from '@/lib/utils'
import { useCards, useCategories, usePeople } from '@/lib/queries'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { CurrencyInput } from '@/components/finance/currency'
import { todayISO } from '@/lib/date'

interface NewPurchaseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  cardId?: string
  onSuccess?: () => void
}

export function NewPurchaseDialog({ open, onOpenChange, cardId, onSuccess }: NewPurchaseDialogProps) {
  const [form, setForm] = useState(() => ({
    card_id: cardId || '',
    description: '',
    merchant: '',
    purchased_on: todayISO(),
    total_cents: '',
    installments_count: 1,
    category_id: '',
    person_id: '',
    notes: '',
  }))
  const [installmentPreview, setInstallmentPreview] = useState<number[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [showInstallments, setShowInstallments] = useState(false)

  const cards = useCards(false)
  const categories = useCategories()
  const people = usePeople(false)

  const expenseCategories = categories.data?.filter((c) => c.kind === 'EXPENSE') || []

  // Clique duplo ou nova tentativa não duplicam a compra; renova a cada abertura.
  const idemKey = useRef(newIdempotencyKey())
  useEffect(() => {
    if (open) idemKey.current = newIdempotencyKey()
  }, [open])

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api('/cards/purchases', { method: 'POST', body }),
    onSuccess: (_data, body) => {
      const n = body.installments_count as number
      toast.success(`Compra de ${formatBRL(body.total_cents as number)}${n > 1 ? ` em ${n}x` : ''} registrada.`)
      onOpenChange(false)
      onSuccess?.()
    },
    onError: (err: Error & { code?: string; details?: unknown }) => {
      if (err.code === 'validation_error' && err.details) {
        setErrors(err.details as Record<string, string>)
      }
      toast.error(err instanceof ApiError ? err.message : 'Não foi possível registrar a compra.')
    },
  })

  // Preview installments when total or count changes
  const updateInstallmentPreview = () => {
    const total = parseInt(form.total_cents.replace(/\D/g, ''), 10) || 0
    const count = form.installments_count
    if (total > 0 && count > 0) {
      const base = Math.floor(total / count)
      const remainder = total % count
      const amounts = Array.from({ length: count }, (_, i) => base + (i < remainder ? 1 : 0))
      setInstallmentPreview(amounts)
      setShowInstallments(true)
    } else {
      setInstallmentPreview([])
      setShowInstallments(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrors({})

    const payload = {
      card_id: form.card_id,
      description: form.description,
      merchant: form.merchant || undefined,
      purchased_on: form.purchased_on,
      total_cents: parseInt(form.total_cents.replace(/\D/g, ''), 10),
      installments_count: form.installments_count,
      category_id: form.category_id || undefined,
      person_id: form.person_id || undefined,
      notes: form.notes || undefined,
      idempotency_key: idemKey.current,
    }

    mutation.mutate(payload)
  }

  const handleInstallmentsChange = (count: number) => {
    setForm({ ...form, installments_count: count })
    updateInstallmentPreview()
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Nova compra no cartão"
      description="Registre uma compra à vista ou parcelada. As parcelas vão para a fatura correspondente."
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {cardId ? null : (
          <Field label="Cartão *" error={errors.card_id}>
            {(props) => (
              <Select
                {...props}
                value={form.card_id}
                onChange={(e) => setForm({ ...form, card_id: e.target.value })}
                required
                disabled={mutation.isPending}
              >
                <option value="">— Selecione o cartão —</option>
                {cards.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.nickname ? `(${c.nickname})` : ''} · {c.last_four ? `**** ${c.last_four}` : ''}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Descrição *" error={errors.description}>
            {(props) => (
              <Input
                {...props}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Ex: Supermercado, Uber, Netflix"
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field label="Estabelecimento" error={errors.merchant}>
            {(props) => (
              <Input
                {...props}
                value={form.merchant}
                onChange={(e) => setForm({ ...form, merchant: e.target.value })}
                placeholder="Opcional: nome do comerciante"
                disabled={mutation.isPending}
              />
            )}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            label="Data da compra *"
            error={errors.purchased_on}
            hint="Não pode ser futura"
          >
            {(props) => (
              <Input
                {...props}
                type="date"
                value={form.purchased_on}
                onChange={(e) => setForm({ ...form, purchased_on: e.target.value })}
                max={todayISO()}
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field
            label="Valor total *"
            error={errors.total_cents}
            hint="Valor total da compra (será dividido nas parcelas)"
          >
            {(props) => (
              <CurrencyInput
                {...props}
                valueCents={form.total_cents ? parseInt(form.total_cents, 10) : null}
                onChangeCents={(v) => {
                  setForm({ ...form, total_cents: v ? String(v) : '' })
                  updateInstallmentPreview()
                }}
                placeholder="15000"
                required
                disabled={mutation.isPending}
              />
            )}
          </Field>

          <Field
            label="Parcelas *"
            error={errors.installments_count}
          >
            {(props) => (
              <div className="flex items-center gap-2">
                <Select
                  {...props}
                  value={form.installments_count}
                  onChange={(e) => handleInstallmentsChange(parseInt(e.target.value, 10))}
                  className="w-24"
                  disabled={mutation.isPending}
                >
                  {Array.from({ length: 24 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>
                      {n}x
                    </option>
                  ))}
                </Select>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleInstallmentsChange(Math.min(24, form.installments_count + 1))}
                  disabled={mutation.isPending || form.installments_count >= 24}
                  aria-label="Aumentar parcelas"
                >
                  <Plus className="size-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleInstallmentsChange(Math.max(1, form.installments_count - 1))}
                  disabled={mutation.isPending || form.installments_count <= 1}
                  aria-label="Diminuir parcelas"
                >
                  <Minus className="size-4" />
                </Button>
              </div>
            )}
          </Field>
        </div>

        {showInstallments && installmentPreview.length > 0 && (
          <div className="rounded-lg border border-border bg-surface-2/50 p-3">
            <p className="text-sm font-medium text-fg mb-2 flex items-center gap-2">
              <CreditCard className="size-4 text-accent" aria-hidden />
              Prévia das {installmentPreview.length} parcela{installmentPreview.length > 1 ? 's' : ''}
            </p>
            <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-4 max-h-40 overflow-y-auto">
              {installmentPreview.map((amt, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm px-2 py-1 rounded bg-surface border border-border/50">
                  <span className="text-muted">Parcela {idx + 1}</span>
                  <span className="font-medium">
                    {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(amt / 100)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Categoria" error={errors.category_id} hint="Apenas categorias de despesa">
            {(props) => (
              <Select
                {...props}
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                disabled={mutation.isPending}
              >
                <option value="">— Sem categoria —</option>
                {expenseCategories.map((c) => (
                  <option key={c.id} value={c.id} style={{ borderLeft: `4px solid ${c.color}` }}>
                    {c.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Pessoa" error={errors.person_id}>
            {(props) => (
              <Select
                {...props}
                value={form.person_id}
                onChange={(e) => setForm({ ...form, person_id: e.target.value })}
                disabled={mutation.isPending}
              >
                <option value="">— Nenhuma —</option>
                {people.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <Field label="Observações" error={errors.notes}>
          {(props) => (
            <Textarea
              {...props}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="Detalhes adicionais"
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
            {mutation.isPending ? 'Salvando…' : 'Registrar compra'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}