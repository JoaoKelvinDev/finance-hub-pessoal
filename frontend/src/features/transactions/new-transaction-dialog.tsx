import { zodResolver } from '@hookform/resolvers/zod'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { MoneyInput } from '@/components/finance/currency'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { ApiError } from '@/lib/api'
import { todayISO } from '@/lib/date'
import { formatBRL } from '@/lib/money'
import { easeOut } from '@/lib/motion'
import { useAccounts, useCategories, useCreateTransaction, useCreateTransfer, usePeople } from '@/lib/queries'
import { newIdempotencyKey } from '@/lib/utils'
import type { Category } from '@/types/api'

export type NewKind = 'EXPENSE' | 'INCOME' | 'TRANSFER'

const schema = z
  .object({
    kind: z.enum(['EXPENSE', 'INCOME', 'TRANSFER']),
    amount_cents: z.number({ error: 'Informe o valor.' }).int().positive('Informe um valor maior que zero.').nullable(),
    description: z.string().trim().max(160),
    effective_date: z.string().min(10, 'Informe a data.'),
    account_id: z.string().min(1, 'Escolha a conta.'),
    to_account_id: z.string(),
    category_id: z.string(),
    counterparty_id: z.string(),
    status: z.enum(['POSTED', 'PLANNED']),
    notes: z.string().max(2000),
  })
  .superRefine((v, ctx) => {
    if (!v.amount_cents) ctx.addIssue({ code: 'custom', path: ['amount_cents'], message: 'Informe um valor maior que zero.' })
    if (v.kind !== 'TRANSFER' && !v.description)
      ctx.addIssue({ code: 'custom', path: ['description'], message: 'Descreva o lançamento.' })
    if (v.kind === 'TRANSFER') {
      if (!v.to_account_id) ctx.addIssue({ code: 'custom', path: ['to_account_id'], message: 'Escolha o destino.' })
      else if (v.to_account_id === v.account_id)
        ctx.addIssue({ code: 'custom', path: ['to_account_id'], message: 'Origem e destino devem ser diferentes.' })
    }
    if (v.status === 'POSTED' && v.effective_date > todayISO())
      ctx.addIssue({ code: 'custom', path: ['effective_date'], message: 'Data futura: marque como "Previsto".' })
  })

type FormValues = z.infer<typeof schema>

function categoryOptions(cats: Category[], kind: 'INCOME' | 'EXPENSE') {
  const roots = cats.filter((c) => c.kind === kind && !c.parent_id)
  return roots.map((r) => ({ root: r, children: cats.filter((c) => c.parent_id === r.id) }))
}

export function NewTransactionDialog({
  open,
  onOpenChange,
  initialKind = 'EXPENSE',
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  initialKind?: NewKind
}) {
  const accounts = useAccounts()
  const categories = useCategories()
  const people = usePeople()
  const createTx = useCreateTransaction()
  const createTransfer = useCreateTransfer()
  const [advanced, setAdvanced] = useState(false)
  // A mesma chave vale para tentativas repetidas do mesmo envio (clique duplo, retry).
  const idemKey = useRef(newIdempotencyKey())

  const defaults: FormValues = useMemo(
    () => ({
      kind: initialKind,
      amount_cents: null,
      description: '',
      effective_date: todayISO(),
      account_id: '',
      to_account_id: '',
      category_id: '',
      counterparty_id: '',
      status: 'POSTED',
      notes: '',
    }),
    [initialKind],
  )

  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: defaults })
  const { register, control, handleSubmit, watch, setValue, reset, formState } = form
  const kind = watch('kind')
  const fromId = watch('account_id')

  useEffect(() => {
    if (open) {
      const preferred = accounts.data?.find((a) => a.type === 'CHECKING') ?? accounts.data?.[0]
      reset({ ...defaults, account_id: preferred?.id ?? '' })
      idemKey.current = newIdempotencyKey()
      setAdvanced(false)
    }
  }, [open, defaults, reset, accounts.data])

  useEffect(() => {
    setValue('category_id', '')
  }, [kind, setValue])

  const onSubmit = handleSubmit(async (v) => {
    try {
      if (v.kind === 'TRANSFER') {
        await createTransfer.mutateAsync({
          from_account_id: v.account_id,
          to_account_id: v.to_account_id,
          amount_cents: v.amount_cents,
          effective_date: v.effective_date,
          description: v.description || 'Transferência entre contas',
          idempotency_key: idemKey.current,
        })
        toast.success(`Transferência de ${formatBRL(v.amount_cents!)} registrada.`)
      } else {
        await createTx.mutateAsync({
          account_id: v.account_id,
          kind: v.kind,
          amount_cents: v.amount_cents,
          status: v.status,
          effective_date: v.effective_date,
          description: v.description,
          category_id: v.category_id || null,
          counterparty_id: v.counterparty_id || null,
          notes: v.notes || null,
          idempotency_key: idemKey.current,
        })
        toast.success(`${v.kind === 'INCOME' ? 'Receita' : 'Despesa'} de ${formatBRL(v.amount_cents!)} registrada.`)
      }
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Não foi possível salvar.')
    }
  })

  const noAccounts = accounts.isSuccess && accounts.data.length === 0
  const activeKind = kind === 'TRANSFER' ? null : kind

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Novo lançamento" description="Registro rápido; detalhes opcionais ficam recolhidos.">
      {noAccounts ? (
        <p className="py-6 text-center text-sm text-muted">Cadastre uma conta em “Contas e carteiras” antes de lançar.</p>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <Controller
            control={control}
            name="kind"
            render={({ field }) => (
              <Segmented
                label="Tipo de lançamento"
                layoutId="new-tx-kind"
                value={field.value}
                onChange={field.onChange}
                className="w-full [&>button]:flex-1"
                options={[
                  { value: 'EXPENSE', label: 'Despesa' },
                  { value: 'INCOME', label: 'Receita' },
                  { value: 'TRANSFER', label: 'Transferência' },
                ]}
              />
            )}
          />

          <Field label="Valor" error={formState.errors.amount_cents?.message}>
            {(p) => (
              <Controller
                control={control}
                name="amount_cents"
                render={({ field }) => (
                  <MoneyInput {...p} autoFocus valueCents={field.value} onChangeCents={field.onChange} />
                )}
              />
            )}
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={kind === 'TRANSFER' ? 'De (origem)' : 'Conta'} error={formState.errors.account_id?.message}>
              {(p) => (
                <Select {...p} {...register('account_id')}>
                  {accounts.data?.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} · {formatBRL(a.balance_cents)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {kind === 'TRANSFER' ? (
              <Field label="Para (destino)" error={formState.errors.to_account_id?.message}>
                {(p) => (
                  <Select {...p} {...register('to_account_id')}>
                    <option value="">Escolha…</option>
                    {accounts.data
                      ?.filter((a) => a.id !== fromId)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                  </Select>
                )}
              </Field>
            ) : (
              <Field label="Categoria">
                {(p) => (
                  <Select {...p} {...register('category_id')}>
                    <option value="">Sem categoria</option>
                    {activeKind &&
                      categoryOptions(categories.data ?? [], activeKind).map(({ root, children }) =>
                        children.length ? (
                          <optgroup key={root.id} label={root.name}>
                            <option value={root.id}>{root.name} (geral)</option>
                            {children.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </optgroup>
                        ) : (
                          <option key={root.id} value={root.id}>
                            {root.name}
                          </option>
                        ),
                      )}
                  </Select>
                )}
              </Field>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Descrição" error={formState.errors.description?.message}>
              {(p) => (
                <Input
                  {...p}
                  {...register('description')}
                  placeholder={kind === 'TRANSFER' ? 'Transferência entre contas' : 'Ex.: Mercado do mês'}
                  maxLength={160}
                />
              )}
            </Field>
            <Field label="Data" error={formState.errors.effective_date?.message}>
              {(p) => <Input {...p} type="date" {...register('effective_date')} />}
            </Field>
          </div>

          {kind !== 'TRANSFER' && (
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <div className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2">
                  <span className="text-sm text-muted">
                    {field.value === 'POSTED' ? 'Já aconteceu: altera o saldo agora.' : 'Previsto: só entra em projeções.'}
                  </span>
                  <Segmented
                    label="Situação"
                    layoutId="new-tx-status"
                    value={field.value}
                    onChange={field.onChange}
                    options={[
                      { value: 'POSTED', label: 'Efetivado' },
                      { value: 'PLANNED', label: 'Previsto' },
                    ]}
                  />
                </div>
              )}
            />
          )}

          {kind !== 'TRANSFER' && (
            <div>
              <button
                type="button"
                onClick={() => setAdvanced((v) => !v)}
                aria-expanded={advanced}
                className="flex items-center gap-1 text-sm font-medium text-muted hover:text-fg"
              >
                <motion.span animate={{ rotate: advanced ? 180 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronDown className="size-4" />
                </motion.span>
                Mais detalhes
              </button>
              <AnimatePresence initial={false}>
                {advanced && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1, transition: { duration: 0.24, ease: easeOut } }}
                    exit={{ height: 0, opacity: 0, transition: { duration: 0.16 } }}
                    className="overflow-hidden"
                  >
                    <div className="grid gap-4 pt-3">
                      <Field label="Pessoa relacionada" hint="Contato de referência; não cria valor a receber.">
                        {(p) => (
                          <Select {...p} {...register('counterparty_id')}>
                            <option value="">Nenhuma</option>
                            {people.data?.map((x) => (
                              <option key={x.id} value={x.id}>
                                {x.display_name}
                              </option>
                            ))}
                          </Select>
                        )}
                      </Field>
                      <Field label="Observações">{(p) => <Textarea {...p} {...register('notes')} />}</Field>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" loading={formState.isSubmitting}>
              Salvar
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
