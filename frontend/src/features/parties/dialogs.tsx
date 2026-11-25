import { useState } from 'react'
import { toast } from 'sonner'
import { CurrencyDisplay, MoneyInput } from '@/components/finance/currency'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { todayISO } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import {
  useAccounts,
  useAdjustPartyBalance,
  useCreatePartyBalance,
  usePeople,
  useSettlePartyBalance,
} from '@/lib/queries'
import { cn, newIdempotencyKey } from '@/lib/utils'
import type { PartyBalance, PartyOrigin } from '@/types/api'
import { ORIGINS, readApiError } from './meta'

function Actions({ onCancel, pending, label }: { onCancel: () => void; pending: boolean; label: string }) {
  return (
    <div className="flex justify-end gap-2 border-t border-border pt-3">
      <Button variant="ghost" onClick={onCancel} disabled={pending}>
        Cancelar
      </Button>
      <Button type="submit" loading={pending}>
        {label}
      </Button>
    </div>
  )
}

// ---------- Novo registro ----------

export function NewPartyBalanceDialog({
  open,
  onOpenChange,
  defaultPersonId,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  defaultPersonId?: string
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Novo registro com terceiro"
      description="Empréstimos, adiantamentos e dívidas não contam como receita nem despesa."
    >
      {open && <NewPartyBalanceForm defaultPersonId={defaultPersonId} onDone={() => onOpenChange(false)} />}
    </Dialog>
  )
}

function NewPartyBalanceForm({ defaultPersonId, onDone }: { defaultPersonId?: string; onDone: () => void }) {
  const people = usePeople()
  const accounts = useAccounts()
  const create = useCreatePartyBalance()
  const [key] = useState(newIdempotencyKey)
  const [origin, setOrigin] = useState<PartyOrigin>('LOAN_GIVEN')
  const [personId, setPersonId] = useState(defaultPersonId ?? '')
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState<number | null>(null)
  const [description, setDescription] = useState('')
  const [date, setDate] = useState(todayISO())
  const [due, setDue] = useState('')
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const meta = ORIGINS[origin]
  const activeAccounts = accounts.data?.filter((a) => !a.archived_at) ?? []

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (!personId) errs.person_id = 'Escolha a pessoa.'
    if (!amount) errs.principal_cents = 'Informe o valor.'
    if (!description.trim()) errs.description = 'Descreva o registro.'
    if (meta.cash && !accountId) errs.account_id = 'Escolha a conta.'
    if (due && due < date) errs.due_date = 'O vencimento não pode ser antes da data.'
    setErrors(errs)
    if (Object.keys(errs).length) return
    try {
      await create.mutateAsync({
        person_id: personId,
        origin_type: origin,
        description: description.trim(),
        principal_cents: amount,
        operation_date: date,
        due_date: due || null,
        account_id: meta.cash ? accountId : null,
        notes: notes.trim() || null,
        idempotency_key: key,
      })
      toast.success('Registro criado.')
      onDone()
    } catch (err) {
      const { message, fields } = readApiError(err)
      setErrors(fields)
      toast.error(message)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">O que aconteceu?</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {(Object.keys(ORIGINS) as PartyOrigin[]).map((o) => (
            <label
              key={o}
              className={cn(
                'flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 text-left transition-colors',
                origin === o ? 'border-accent bg-accent-soft/40' : 'border-border hover:bg-surface-2',
              )}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="radio"
                  name="origin"
                  value={o}
                  checked={origin === o}
                  onChange={() => setOrigin(o)}
                  className="accent-[var(--color-accent)]"
                />
                {ORIGINS[o].label}
              </span>
              <span className="text-xs text-muted">{ORIGINS[o].description}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Pessoa" error={errors.person_id} hint={people.data?.length === 0 ? 'Cadastre a pessoa em Pessoas primeiro.' : undefined}>
          {(p) => (
            <Select {...p} value={personId} onChange={(e) => setPersonId(e.target.value)}>
              <option value="">— Selecione —</option>
              {people.data?.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.display_name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Valor" error={errors.principal_cents}>
          {(p) => <MoneyInput {...p} valueCents={amount} onChangeCents={setAmount} />}
        </Field>
      </div>

      <Field label="Descrição" error={errors.description}>
        {(p) => (
          <Input
            {...p}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={160}
            placeholder={origin === 'ADVANCE' ? 'Ex.: Ingresso do show' : 'Ex.: Empréstimo para o conserto do carro'}
          />
        )}
      </Field>

      {meta.cash && (
        <Field
          label={meta.direction === 'RECEIVABLE' ? 'Saiu da conta' : 'Entrou na conta'}
          error={errors.account_id}
        >
          {(p) => (
            <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">— Selecione —</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {formatBRL(a.balance_cents)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Data" error={errors.operation_date}>
          {(p) => <Input {...p} type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Vencimento (opcional)" error={errors.due_date} hint="Aparece no calendário.">
          {(p) => <Input {...p} type="date" value={due} min={date} onChange={(e) => setDue(e.target.value)} />}
        </Field>
      </div>

      <Field label="Observações (opcional)">
        {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} rows={2} />}
      </Field>

      <Actions onCancel={onDone} pending={create.isPending} label="Salvar registro" />
    </form>
  )
}

// ---------- Acerto ----------

export function SettleDialog({ balance, onClose }: { balance: PartyBalance | null; onClose: () => void }) {
  const receivable = balance?.direction === 'RECEIVABLE'
  return (
    <Dialog
      open={!!balance}
      onOpenChange={(o) => !o && onClose()}
      title={receivable ? 'Registrar recebimento' : 'Registrar pagamento'}
      description={
        balance
          ? `${receivable ? 'Recebido de' : 'Pago a'} ${balance.person_name}: ${balance.description}. Não conta como ${receivable ? 'receita' : 'despesa'}.`
          : undefined
      }
    >
      {balance && <SettleForm key={balance.id} balance={balance} onDone={onClose} />}
    </Dialog>
  )
}

function SettleForm({ balance, onDone }: { balance: PartyBalance; onDone: () => void }) {
  const accounts = useAccounts()
  const settle = useSettlePartyBalance()
  const [key] = useState(newIdempotencyKey)
  const [accountId, setAccountId] = useState(balance.account_id ?? '')
  const [amount, setAmount] = useState<number | null>(balance.open_cents)
  const [date, setDate] = useState(todayISO())
  const [errors, setErrors] = useState<Record<string, string>>({})
  const receivable = balance.direction === 'RECEIVABLE'

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (!accountId) errs.account_id = 'Escolha a conta.'
    if (!amount) errs.amount_cents = 'Informe o valor.'
    else if (amount > balance.open_cents) errs.amount_cents = `Máximo: ${formatBRL(balance.open_cents)}.`
    setErrors(errs)
    if (Object.keys(errs).length) return
    try {
      await settle.mutateAsync({ id: balance.id, account_id: accountId, amount_cents: amount, settled_on: date, idempotency_key: key })
      toast.success(amount === balance.open_cents ? 'Quitado!' : 'Acerto registrado.')
      onDone()
    } catch (err) {
      const { message, fields } = readApiError(err)
      setErrors(fields)
      toast.error(message)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
        <span className="text-muted">Saldo em aberto</span>
        <CurrencyDisplay cents={balance.open_cents} className="font-semibold" animated={false} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Valor" error={errors.amount_cents} hint="Pode ser parcial.">
          {(p) => <MoneyInput {...p} valueCents={amount} onChangeCents={setAmount} />}
        </Field>
        <Field label="Data" error={errors.settled_on}>
          {(p) => (
            <Input {...p} type="date" value={date} min={balance.operation_date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />
          )}
        </Field>
      </div>
      <Field label={receivable ? 'Entrou na conta' : 'Saiu da conta'} error={errors.account_id}>
        {(p) => (
          <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="">— Selecione —</option>
            {accounts.data
              ?.filter((a) => !a.archived_at)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {formatBRL(a.balance_cents)}
                </option>
              ))}
          </Select>
        )}
      </Field>
      <Actions onCancel={onDone} pending={settle.isPending} label="Confirmar" />
    </form>
  )
}

// ---------- Juros / desconto ----------

export function AdjustDialog({ balance, onClose }: { balance: PartyBalance | null; onClose: () => void }) {
  return (
    <Dialog
      open={!!balance}
      onOpenChange={(o) => !o && onClose()}
      title="Juros ou desconto"
      description="Ajusta o saldo sem movimentar conta. Para perdoar a dívida, dê desconto do valor total."
    >
      {balance && <AdjustForm key={balance.id} balance={balance} onDone={onClose} />}
    </Dialog>
  )
}

function AdjustForm({ balance, onDone }: { balance: PartyBalance; onDone: () => void }) {
  const adjust = useAdjustPartyBalance()
  const [key] = useState(newIdempotencyKey)
  const [kind, setKind] = useState<'CHARGE' | 'DISCOUNT'>('CHARGE')
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState(todayISO())
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (!amount) errs.amount_cents = 'Informe o valor.'
    else if (kind === 'DISCOUNT' && amount > balance.open_cents) errs.amount_cents = `Máximo: ${formatBRL(balance.open_cents)}.`
    if (reason.trim().length < 3) errs.reason = 'Explique o motivo (mín. 3 letras).'
    setErrors(errs)
    if (Object.keys(errs).length) return
    try {
      await adjust.mutateAsync({ id: balance.id, kind, amount_cents: amount, applied_on: date, reason: reason.trim(), idempotency_key: key })
      toast.success(kind === 'CHARGE' ? 'Encargo lançado.' : 'Desconto aplicado.')
      onDone()
    } catch (err) {
      const { message, fields } = readApiError(err)
      setErrors(fields)
      toast.error(message)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tipo de ajuste">
        {(
          [
            ['CHARGE', 'Juros / multa', 'Aumenta o saldo'],
            ['DISCOUNT', 'Desconto / perdão', 'Reduz o saldo'],
          ] as const
        ).map(([v, label, hint]) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={kind === v}
            onClick={() => setKind(v)}
            className={cn(
              'rounded-lg border p-3 text-left',
              kind === v ? 'border-accent bg-accent-soft/40' : 'border-border hover:bg-surface-2',
            )}
          >
            <span className="block text-sm font-medium">{label}</span>
            <span className="text-xs text-muted">{hint}</span>
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Valor" error={errors.amount_cents}>
          {(p) => <MoneyInput {...p} valueCents={amount} onChangeCents={setAmount} />}
        </Field>
        <Field label="Data" error={errors.applied_on}>
          {(p) => <Input {...p} type="date" value={date} min={balance.operation_date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
      </div>
      {kind === 'DISCOUNT' && balance.open_cents > 0 && (
        <Button variant="secondary" size="sm" className="self-start" onClick={() => setAmount(balance.open_cents)}>
          Perdoar o saldo todo ({formatBRL(balance.open_cents)})
        </Button>
      )}
      <Field label="Motivo" error={errors.reason}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />}
      </Field>
      <Actions onCancel={onDone} pending={adjust.isPending} label="Aplicar" />
    </form>
  )
}

// ---------- Motivo (cancelar / estornar) ----------

export function ReasonDialog({
  open,
  title,
  description,
  confirmLabel,
  pending,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  pending: boolean
  onConfirm: (reason: string) => Promise<void>
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string>()
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setReason('')
          setError(undefined)
          onClose()
        }
      }}
      title={title}
      description={description}
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault()
          if (reason.trim().length < 3) return setError('Explique o motivo (mín. 3 letras).')
          try {
            await onConfirm(reason.trim())
            setReason('')
            setError(undefined)
          } catch (err) {
            toast.error(readApiError(err).message)
          }
        }}
      >
        <Field label="Motivo" error={error}>
          {(p) => <Input {...p} autoFocus value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />}
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Voltar
          </Button>
          <Button type="submit" variant="danger" loading={pending}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
