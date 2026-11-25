import { Plus, Trash2, Undo2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { CurrencyDisplay, MoneyInput } from '@/components/finance/currency'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { PARTY_STATUS, readApiError } from '@/features/parties/meta'
import { ReasonDialog } from '@/features/parties/dialogs'
import { formatDate } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import { useCancelSplit, useConfirmInstallmentAmount, useCreateSplit, usePeople, useSplit } from '@/lib/queries'
import { cn, newIdempotencyKey } from '@/lib/utils'
import type { BillInstallment, SplitMethod } from '@/types/api'

// ---------- Informar valor real ----------

export function ConfirmAmountDialog({ installment, onClose }: { installment: BillInstallment | null; onClose: () => void }) {
  return (
    <Dialog
      open={!!installment}
      onOpenChange={(o) => !o && onClose()}
      title="Informar valor real"
      description={
        installment
          ? `${installment.bill_name ?? 'Conta'} · vence ${formatDate(installment.due_date)}. A estimativa fica guardada no histórico.`
          : undefined
      }
    >
      {installment && <ConfirmAmountForm key={installment.id} installment={installment} onDone={onClose} />}
    </Dialog>
  )
}

function ConfirmAmountForm({ installment, onDone }: { installment: BillInstallment; onDone: () => void }) {
  const confirm = useConfirmInstallmentAmount()
  const [amount, setAmount] = useState<number | null>(null)
  const [error, setError] = useState<string>()
  const diff = amount ? amount - installment.amount_cents : 0

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!amount) return setError('Informe o valor da conta.')
        try {
          await confirm.mutateAsync({ installmentId: installment.id, amount_cents: amount })
          toast.success('Valor real confirmado.')
          onDone()
        } catch (err) {
          toast.error(readApiError(err).message)
        }
      }}
    >
      <div className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
        <span className="text-muted">Estimativa</span>
        <CurrencyDisplay cents={installment.amount_cents} animated={false} className="font-semibold" />
      </div>
      <Field
        label="Valor real da conta"
        error={error}
        hint={
          amount && diff !== 0
            ? `${diff > 0 ? '+' : '−'}${formatBRL(Math.abs(diff))} em relação à estimativa`
            : undefined
        }
      >
        {(p) => <MoneyInput {...p} autoFocus valueCents={amount} onChangeCents={setAmount} />}
      </Field>
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" loading={confirm.isPending}>
          Confirmar valor
        </Button>
      </div>
    </form>
  )
}

// ---------- Rateio ----------

export function SplitDialog({ installment, onClose }: { installment: BillInstallment | null; onClose: () => void }) {
  return (
    <Dialog
      open={!!installment}
      onOpenChange={(o) => !o && onClose()}
      title={installment?.split_id ? 'Rateio da conta' : 'Ratear conta'}
      description={
        installment
          ? `${installment.bill_name ?? 'Conta'} · ${formatBRL(installment.amount_cents)} · vence ${formatDate(installment.due_date)}`
          : undefined
      }
      className="sm:max-w-xl"
    >
      {installment &&
        (installment.split_id ? (
          <SplitView key={installment.id} installmentId={installment.id} onDone={onClose} />
        ) : (
          <SplitForm key={installment.id} installment={installment} onDone={onClose} />
        ))}
    </Dialog>
  )
}

interface Row {
  person_id: string
  amount: number | null
  percent: string
}

/** Prévia local do rateio — mesma regra do backend (sobra de centavo fica com você). */
function preview(total: number, method: SplitMethod, includeOwner: boolean, rows: Row[]) {
  const n = rows.length
  if (n === 0) return { owner: total, shares: [] as number[], error: undefined as string | undefined }
  if (method === 'EQUAL') {
    const parts = n + (includeOwner ? 1 : 0)
    const base = Math.floor(total / parts)
    const rest = total % parts
    const all = Array.from({ length: parts }, (_, i) => base + (i < rest ? 1 : 0))
    return includeOwner ? { owner: all[0], shares: all.slice(1), error: undefined } : { owner: 0, shares: all, error: undefined }
  }
  if (method === 'FIXED') {
    const shares = rows.map((r) => r.amount ?? 0)
    const owner = total - shares.reduce((a, b) => a + b, 0)
    let error: string | undefined
    if (owner < 0) error = 'A soma das partes passa do total.'
    else if (!includeOwner && owner !== 0) error = `Faltam ${formatBRL(owner)} para fechar o total.`
    return { owner, shares, error }
  }
  const bps = rows.map((r) => Math.round(Number(r.percent.replace(',', '.')) * 100) || 0)
  const totalBp = bps.reduce((a, b) => a + b, 0)
  const shares = bps.map((bp) => Math.floor((total * bp) / 10_000))
  let error: string | undefined
  if (totalBp > 10_000) error = 'Os percentuais somam mais de 100%.'
  else if (!includeOwner && totalBp !== 10_000) error = `Os percentuais somam ${(totalBp / 100).toLocaleString('pt-BR')}%; precisam fechar 100%.`
  if (!includeOwner && !error) {
    // Maior resto, igual ao backend.
    const missing = total - shares.reduce((a, b) => a + b, 0)
    const order = bps.map((bp, i) => [(total * bp) % 10_000, i] as const).sort((a, b) => b[0] - a[0])
    for (let k = 0; k < missing; k++) shares[order[k % n][1]] += 1
  }
  return { owner: total - shares.reduce((a, b) => a + b, 0), shares, error }
}

function SplitForm({ installment, onDone }: { installment: BillInstallment; onDone: () => void }) {
  const people = usePeople()
  const create = useCreateSplit()
  const [key] = useState(newIdempotencyKey)
  const [method, setMethod] = useState<SplitMethod>('EQUAL')
  const [includeOwner, setIncludeOwner] = useState(true)
  const [rows, setRows] = useState<Row[]>([{ person_id: '', amount: null, percent: '' }])
  const [due, setDue] = useState('')
  const total = installment.amount_cents
  const p = useMemo(() => preview(total, method, includeOwner, rows), [total, method, includeOwner, rows])

  const used = new Set(rows.map((r) => r.person_id).filter(Boolean))
  const update = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  if (people.data && people.data.length === 0) {
    return (
      <div className="space-y-3 text-sm">
        <p>Cadastre as pessoas que dividem a conta com você antes de ratear.</p>
        <Link to="/pessoas" className="font-medium text-accent hover:underline">
          Ir para Pessoas →
        </Link>
      </div>
    )
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (rows.some((r) => !r.person_id)) return toast.error('Escolha a pessoa de cada linha.')
        if (p.error) return toast.error(p.error)
        try {
          await create.mutateAsync({
            installmentId: installment.id,
            method,
            include_owner: includeOwner,
            due_date: due || null,
            idempotency_key: key,
            participants: rows.map((r) => ({
              person_id: r.person_id,
              amount_cents: method === 'FIXED' ? r.amount : null,
              percent_bp: method === 'PERCENT' ? Math.round(Number(r.percent.replace(',', '.')) * 100) : null,
            })),
          })
          toast.success('Rateio criado. Os valores a receber já estão em Terceiros.')
          onDone()
        } catch (err) {
          toast.error(readApiError(err).message)
        }
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Forma de dividir"
          layoutId="split-method"
          value={method}
          onChange={setMethod}
          options={[
            { value: 'EQUAL', label: 'Partes iguais' },
            { value: 'FIXED', label: 'Valores' },
            { value: 'PERCENT', label: 'Percentuais' },
          ]}
        />
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-[var(--color-accent)]"
            checked={includeOwner}
            onChange={(e) => setIncludeOwner(e.target.checked)}
          />
          Incluir minha parte
        </label>
      </div>

      <ul className="space-y-2">
        {rows.map((r, i) => (
          <li key={i} className="flex items-end gap-2">
            <Field label={i === 0 ? 'Pessoa' : ''} className="min-w-0 flex-1">
              {(fp) => (
                <Select {...fp} aria-label={`Pessoa ${i + 1}`} value={r.person_id} onChange={(e) => update(i, { person_id: e.target.value })}>
                  <option value="">— Selecione —</option>
                  {people.data
                    ?.filter((x) => !x.archived_at && (x.id === r.person_id || !used.has(x.id)))
                    .map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.display_name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
            {method === 'FIXED' && (
              <Field label={i === 0 ? 'Valor' : ''} className="w-36">
                {(fp) => <MoneyInput {...fp} aria-label={`Valor ${i + 1}`} valueCents={r.amount} onChangeCents={(v) => update(i, { amount: v })} />}
              </Field>
            )}
            {method === 'PERCENT' && (
              <Field label={i === 0 ? '%' : ''} className="w-24">
                {(fp) => (
                  <Input
                    {...fp}
                    aria-label={`Percentual ${i + 1}`}
                    inputMode="decimal"
                    value={r.percent}
                    onChange={(e) => update(i, { percent: e.target.value.replace(/[^\d,.]/g, '') })}
                    placeholder="50"
                  />
                )}
              </Field>
            )}
            {method !== 'FIXED' && method !== 'PERCENT' && (
              <span className="w-28 pb-2.5 text-right text-sm font-medium tabular-nums">{formatBRL(p.shares[i] ?? 0)}</span>
            )}
            <Button
              size="icon-sm"
              variant="ghost"
              className="mb-1"
              onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}
              disabled={rows.length === 1}
              aria-label={`Remover pessoa ${i + 1}`}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
      <Button
        variant="secondary"
        size="sm"
        className="self-start"
        onClick={() => setRows((rs) => [...rs, { person_id: '', amount: null, percent: '' }])}
        disabled={rows.length >= 20}
      >
        <Plus /> Adicionar pessoa
      </Button>

      <div className={cn('rounded-lg border p-3 text-sm', p.error ? 'border-negative/40 bg-negative-soft' : 'border-border bg-surface-2')}>
        <div className="flex justify-between">
          <span className="text-muted">Total da conta</span>
          <span className="font-medium tabular-nums">{formatBRL(total)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Outras pessoas devem</span>
          <span className="font-medium tabular-nums">{formatBRL(p.shares.reduce((a, b) => a + b, 0))}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Sua parte</span>
          <span className="font-semibold tabular-nums">{formatBRL(Math.max(p.owner, 0))}</span>
        </div>
        {p.error && <p className="mt-2 text-xs font-medium text-negative" role="alert">{p.error}</p>}
      </div>

      <Field label="Prazo para receberem (opcional)" hint="Padrão: vencimento da conta. Aparece no calendário e nos alertas.">
        {(fp) => <Input {...fp} type="date" value={due} onChange={(e) => setDue(e.target.value)} />}
      </Field>

      <p className="text-xs text-muted">
        A despesa continua de {formatBRL(total)}. Cada parte vira um valor a receber em Terceiros; repasses não contam como receita.
      </p>

      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" loading={create.isPending} disabled={!!p.error}>
          Criar rateio
        </Button>
      </div>
    </form>
  )
}

function SplitView({ installmentId, onDone }: { installmentId: string; onDone: () => void }) {
  const q = useSplit(installmentId)
  const cancel = useCancelSplit()
  const [cancelling, setCancelling] = useState(false)
  const s = q.data

  if (q.isError) return <p className="text-sm text-negative">{readApiError(q.error).message}</p>
  if (!s) return <div className="shimmer h-40 rounded-lg" />

  const anyReceived = s.received_cents > 0

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label="Despesa bruta" cents={s.total_cents} />
        <Stat label="Já reembolsado" cents={s.received_cents} tone="text-positive" />
        <Stat label="Seu custo líquido" cents={s.net_cost_cents} strong />
      </div>

      <ul className="divide-y divide-border rounded-lg border border-border text-sm">
        <li className="flex items-center gap-3 px-3 py-2">
          <span className="min-w-0 flex-1 font-medium">Você</span>
          <span className="tabular-nums">{formatBRL(s.owner_share_cents)}</span>
        </li>
        {s.parts.map((part) => {
          const st = PARTY_STATUS[part.status]
          return (
            <li key={part.id} className="flex items-center gap-3 px-3 py-2">
              <Link to={`/pessoas/${part.person_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
                {part.person_name}
              </Link>
              <span className={cn('rounded-full px-1.5 py-px text-[11px] font-medium', st.cls)}>{st.label}</span>
              <span className="w-36 text-right tabular-nums">
                {formatBRL(part.share_cents)}
                {part.received_cents > 0 && part.open_cents > 0 && (
                  <span className="block text-[11px] text-muted">falta {formatBRL(part.open_cents)}</span>
                )}
              </span>
            </li>
          )
        })}
      </ul>

      <p className="text-xs text-muted">
        Para registrar um repasse, use <Link to="/terceiros" className="font-medium text-accent hover:underline">Valores com terceiros</Link>.
      </p>

      <div className="flex justify-between gap-2 border-t border-border pt-3">
        <Button
          variant="ghost"
          className="text-negative hover:bg-negative-soft hover:text-negative"
          onClick={() => setCancelling(true)}
          disabled={anyReceived}
          title={anyReceived ? 'Estorne os repasses recebidos antes de desfazer o rateio.' : undefined}
        >
          <Undo2 /> Desfazer rateio
        </Button>
        <Button variant="secondary" onClick={onDone}>
          Fechar
        </Button>
      </div>

      <ReasonDialog
        open={cancelling}
        title="Desfazer rateio"
        description="Os valores a receber deste rateio serão cancelados. A despesa da conta não muda."
        confirmLabel="Desfazer"
        pending={cancel.isPending}
        onClose={() => setCancelling(false)}
        onConfirm={async (reason) => {
          await cancel.mutateAsync({ splitId: s.id, reason })
          toast.success('Rateio desfeito.')
          setCancelling(false)
          onDone()
        }}
      />
    </div>
  )
}

function Stat({ label, cents, tone, strong }: { label: string; cents: number; tone?: string; strong?: boolean }) {
  return (
    <div className="rounded-lg bg-surface-2 px-2 py-2.5">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={cn('mt-0.5 tabular-nums', strong ? 'font-semibold' : 'font-medium', tone)}>{formatBRL(cents)}</p>
    </div>
  )
}
