import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input } from '@/components/ui/field'
import { ApiError } from '@/lib/api'
import { formatBRL } from '@/lib/money'
import { useCancelTransaction, usePostTransaction } from '@/lib/queries'
import type { Transaction } from '@/types/api'

/** Ações de lançamento com confirmação explícita (cancelamento exige motivo e preserva histórico). */
export function useTransactionActions() {
  const [target, setTarget] = useState<Transaction | null>(null)
  const [reason, setReason] = useState('')
  const cancel = useCancelTransaction()
  const post = usePostTransaction()

  const onPost = async (t: Transaction) => {
    try {
      await post.mutateAsync(t.id)
      toast.success(`“${t.description}” marcado como pago.`)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'Não foi possível efetivar.')
    }
  }

  const transfer = target?.transfer_group_id != null
  const dialog = (
    <Dialog
      open={!!target}
      onOpenChange={(o) => !o && setTarget(null)}
      title={transfer ? 'Cancelar transferência' : 'Cancelar lançamento'}
      description="O registro é mantido no histórico com o motivo informado."
    >
      {target && (
        <form
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault()
            try {
              await cancel.mutateAsync({ id: target.id, reason })
              toast.success(transfer ? 'Transferência cancelada (as duas pernas).' : 'Lançamento cancelado.')
              setTarget(null)
            } catch (err) {
              toast.error(err instanceof ApiError ? err.message : 'Não foi possível cancelar.')
            }
          }}
        >
          <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm">
            {target.description} · <span className="num font-medium">{formatBRL(target.amount_cents)}</span>
            {transfer && <span className="mt-1 block text-xs text-muted">As duas contas da transferência serão ajustadas.</span>}
          </p>
          <Field label="Motivo" hint="Mínimo de 3 caracteres.">
            {(p) => <Input {...p} autoFocus value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />}
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setTarget(null)}>
              Voltar
            </Button>
            <Button type="submit" variant="danger" disabled={reason.trim().length < 3} loading={cancel.isPending}>
              Confirmar cancelamento
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )

  return {
    onCancel: (t: Transaction) => {
      setReason('')
      setTarget(t)
    },
    onPost,
    dialog,
  }
}
